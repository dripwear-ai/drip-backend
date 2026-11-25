from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from drip.api.v1.catalog import (
    create_product_draft,
    edit_product_draft,
    preview_product,
    publish_product,
    withdraw_product,
)
from drip.catalog.contracts import (
    ProductDraftInput,
    ProductUpdateInput,
    PublicationPreviewInput,
    PublishInput,
    WithdrawInput,
)
from drip.catalog.security import CatalogAdminActor
from drip.core.config import settings
from drip.core.errors import ConflictException
from drip.core.identifiers import new_uuid7
from drip.models.catalog import (
    Brand,
    CanonicalProduct,
    CatalogPublication,
    ListingVariant,
    Merchant,
    MerchantListing,
    PriceRecord,
)


class TransactionProbe:
    def __init__(self) -> None:
        self.rolled_back = False

    async def __aenter__(self) -> TransactionProbe:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        self.rolled_back = exc_type is not None
        return False


class SessionProbe:
    """Database-free session double for endpoint control-flow tests only."""

    def __init__(self, records: dict[tuple[type, object], object]) -> None:
        self.records = records
        self.added: list[object] = []
        self.scalar_results: list[object | None] = []
        self.transactions: list[TransactionProbe] = []

    def begin(self) -> TransactionProbe:
        transaction = TransactionProbe()
        self.transactions.append(transaction)
        return transaction

    async def get(self, model: type, identifier: object, **kwargs):
        return self.records.get((model, identifier))

    async def scalar(self, statement):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    async def execute(self, statement):
        return None

    def add(self, value: object) -> None:
        self.added.append(value)
        self._assign_defaults(value)

    def _assign_defaults(self, value: object) -> None:
        if getattr(value, "id", None) is None and hasattr(value, "id"):
            value.id = new_uuid7()
        if isinstance(value, CanonicalProduct) and value.revision is None:
            value.revision = 1
        if isinstance(value, MerchantListing) and value.revision is None:
            value.revision = 1
        if isinstance(value, ListingVariant) and value.revision is None:
            value.revision = 1
        if isinstance(value, CanonicalProduct):
            for listing in value.listings:
                self._assign_defaults(listing)
        if isinstance(value, MerchantListing):
            for variant in value.variants:
                self._assign_defaults(variant)

    async def flush(self) -> None:
        for value in self.added:
            self._assign_defaults(value)


def _seeded_registry() -> tuple[Brand, Merchant, CatalogAdminActor, SessionProbe]:
    brand = Brand(
        id=new_uuid7(), slug="approved-brand", display_name="Approved Brand",
        status="active", source_ref="rights-record", reviewer_ref="test-admin",
    )
    merchant = Merchant(
        id=new_uuid7(), slug="approved-merchant", display_name="Approved Merchant",
        status="active", purchase_mode="external_redirect",
        allowed_destination_hosts=["shop.example"], allowed_image_hosts=["images.example"],
        source_ref="merchant-approval", reviewer_ref="test-admin",
    )
    actor = CatalogAdminActor(user_id=new_uuid7(), can_write=True, can_publish=True)
    session = SessionProbe({(Brand, brand.id): brand, (Merchant, merchant.id): merchant})
    return brand, merchant, actor, session


def _draft_payload(brand: Brand, merchant: Merchant) -> ProductDraftInput:
    return ProductDraftInput.model_validate(
        {
            "brand_id": str(brand.id),
            "canonical_key": "approved-style-key",
            "title": "Approved source title",
            "description": "Source-backed description",
            "category_code": "tops",
            "listing": {
                "merchant_id": str(merchant.id),
                "source_listing_key": "merchant-listing-key",
                "destination_url": "https://shop.example/item",
                "variants": [
                    {
                        "source_variant_key": "merchant-variant-key",
                        "size_label": "M",
                        "color_label": "Blue",
                        "color_family": "blue",
                        "image_url": "https://images.example/item.jpg",
                        "image_alt": "Source-approved product image",
                        "image_rights_ref": "protected-rights-record",
                    }
                ],
            },
        }
    )


def test_controlled_admin_principal_can_create_edit_preview_publish_and_withdraw():
    brand, merchant, actor, session = _seeded_registry()
    created = _run_immediate(create_product_draft(_draft_payload(brand, merchant), actor, session))
    product = next(value for value in session.added if isinstance(value, CanonicalProduct))
    listing = product.listings[0]
    variant = listing.variants[0]
    product.brand = brand
    listing.merchant = merchant
    session.records[(CanonicalProduct, product.id)] = product

    edited = _run_immediate(edit_product_draft(
        product.id,
        ProductUpdateInput(
            expected_revision=1, title="Reviewed source title", description="Source-backed description",
            category_code="tops",
        ),
        actor,
        session,
    ))
    assert created["status"] == "draft"
    assert edited["revision"] == 2
    assert product.title == "Reviewed source title"

    now = datetime.now(UTC)
    plan = {
        "approval_ref": "protected-approval-record",
        "expected_revision": 2,
        "listing_ids": [str(listing.id)],
        "prices": [
            {
                "variant_id": str(variant.id),
                "price": {
                    "amount_minor": "9007199254740993",
                    "observed_at": (now - timedelta(minutes=1)).isoformat(),
                    "valid_until": (now + timedelta(hours=1)).isoformat(),
                },
            }
        ],
    }
    session.scalar_results = [product]
    preview = _run_immediate(
        preview_product(product.id, PublicationPreviewInput.model_validate(plan), actor, session)
    )
    publish_input = PublishInput.model_validate(
        {
            **plan,
            "request_key": str(uuid4()),
            "preview_digest": preview["digest"],
        }
    )
    monkeypatch_values = {
        "CATALOG_PRICE_FRESHNESS_HOURS": 24,
        "CATALOG_MAX_PRICE_MINOR": 9_223_372_036_854_775_807,
        "CATALOG_ALLOWED_CATEGORIES": "tops",
    }
    originals = {name: getattr(settings, name) for name in monkeypatch_values}
    try:
        for name, value in monkeypatch_values.items():
            setattr(settings, name, value)
        session.scalar_results = [product, None]
        published = _run_immediate(publish_product(product.id, publish_input, actor, session))
        assert published["status"] == "applied"
        assert product.status == "published"
        publication = next(value for value in session.added if isinstance(value, CatalogPublication))
        assert listing.status == "published"
        assert next(value for value in session.added if isinstance(value, PriceRecord)).amount_minor == 9_007_199_254_740_993

        session.scalar_results = [product, publication]
        retry = _run_immediate(publish_product(product.id, publish_input, actor, session))
        assert retry == {"publication_id": publication.id, "status": "applied"}
        assert len([value for value in session.added if isinstance(value, PriceRecord)]) == 1

        session.records[(CatalogPublication, publication.id)] = publication
        session.scalar_results = [product]
        withdrawn = _run_immediate(withdraw_product(
            product.id,
            WithdrawInput(
                reason_category="source-rights-review",
                approval_ref="protected-withdrawal-record",
                expected_revision=3,
            ),
            actor,
            session,
        ))
        assert withdrawn["status"] == "withdrawn"
        assert publication.status == "revoked"
        assert listing.status == "withdrawn"
        assert session.transactions and all(not tx.rolled_back for tx in session.transactions)
    finally:
        for name, value in originals.items():
            setattr(settings, name, value)


def test_publication_payload_changed_after_preview_is_rejected_and_transaction_aborts():
    brand, merchant, actor, session = _seeded_registry()
    _run_immediate(create_product_draft(_draft_payload(brand, merchant), actor, session))
    product = next(value for value in session.added if isinstance(value, CanonicalProduct))
    listing = product.listings[0]
    variant = listing.variants[0]
    product.brand = brand
    listing.merchant = merchant
    now = datetime.now(UTC)
    plan = PublicationPreviewInput(
        approval_ref="protected-approval-record",
        expected_revision=1,
        listing_ids=[listing.id],
        prices=[
            {
                "variant_id": variant.id,
                "price": {
                    "amount_minor": "1200",
                    "observed_at": now - timedelta(minutes=1),
                    "valid_until": now + timedelta(hours=1),
                },
            }
        ],
    )
    session.scalar_results = [product]
    preview = _run_immediate(preview_product(product.id, plan, actor, session))
    product.revision += 1
    publish = PublishInput(
        **plan.model_dump(), request_key=uuid4(), preview_digest=preview["digest"]
    )
    originals = {
        "CATALOG_PRICE_FRESHNESS_HOURS": settings.CATALOG_PRICE_FRESHNESS_HOURS,
        "CATALOG_MAX_PRICE_MINOR": settings.CATALOG_MAX_PRICE_MINOR,
        "CATALOG_ALLOWED_CATEGORIES": settings.CATALOG_ALLOWED_CATEGORIES,
    }
    try:
        settings.CATALOG_PRICE_FRESHNESS_HOURS = 24
        settings.CATALOG_MAX_PRICE_MINOR = 100_000
        settings.CATALOG_ALLOWED_CATEGORIES = "tops"
        session.scalar_results = [product]
        with pytest.raises(ConflictException, match="changed or cannot accept a publication"):
            _run_immediate(publish_product(product.id, publish, actor, session))
        assert session.transactions[-1].rolled_back
        assert not any(isinstance(value, CatalogPublication) for value in session.added)
    finally:
        for name, value in originals.items():
            setattr(settings, name, value)


def _run_immediate(coroutine):
    """Run a database-free coroutine whose awaited test doubles complete inline."""
    if not inspect.iscoroutine(coroutine):
        raise TypeError("Expected a coroutine.")
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        if coroutine.cr_await is not None:
            coroutine.close()
    raise AssertionError("Test double unexpectedly suspended on external I/O.")
