from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from drip.catalog.service import eligible_product_page, price_state_for_variant, product_detail
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


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def one_or_none(self):
        return self.values[0] if self.values else None


class CatalogReadSessionProbe:
    """In-memory result double; it performs no SQL or database connection."""

    def __init__(self, product, price, publication):
        self.product = product
        self.price = price
        self.publication = publication
        self.statements = []
        self.publication_status = publication.status

    async def scalars(self, statement):
        self.statements.append(statement)
        return Rows([self.product])

    async def scalar(self, statement):
        self.statements.append(statement)
        sql = str(statement)
        if "drip_catalog.publications.id" in sql:
            return self.publication.id if self.publication_status == "applied" else None
        if "drip_catalog.prices.id" in sql:
            values = statement.compile().params.values()
            return self.price.id if self.price.variant_id in values else None
        return self.product

    async def execute(self, statement):
        self.statements.append(statement)
        values = statement.compile().params.values()
        if self.price.variant_id not in values:
            return Rows([])
        return Rows([(self.price, self.publication_status)])

    async def get(self, model, identifier):
        if model is CatalogPublication:
            return self.publication
        if model is PriceRecord and identifier == self.price.id:
            return self.price
        return None


def _run_immediate(coroutine):
    if not inspect.iscoroutine(coroutine):
        raise TypeError("Expected a coroutine.")
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        if coroutine.cr_await is not None:
            coroutine.close()
    raise AssertionError("Read-session test double unexpectedly suspended on external I/O.")


def _published_catalog():
    now = datetime.now(UTC)
    publication = CatalogPublication(
        id=new_uuid7(),
        merchant_id=new_uuid7(),
        request_key=uuid4(),
        manifest_sha256="a" * 64,
        schema_version=1,
        reviewer_ref="test-reviewer",
        approval_ref="protected-approval-ref",
        status="applied",
        applied_at=now,
        change_summary={},
    )
    brand = Brand(
        id=new_uuid7(), slug="approved-source-brand", display_name="Approved Source Brand",
        status="active", source_ref="protected-brand-source", reviewer_ref="test-reviewer",
    )
    merchant = Merchant(
        id=publication.merchant_id, slug="approved-source-merchant", display_name="Approved Merchant",
        status="active", purchase_mode="external_redirect",
        allowed_destination_hosts=["shop.example"], allowed_image_hosts=["images.example"],
        source_ref="protected-merchant-source", reviewer_ref="test-reviewer",
    )
    product = CanonicalProduct(
        id=new_uuid7(), brand_id=brand.id, canonical_key="approved-source-key",
        title="Source-backed title", description="Source-backed description", category_code="tops",
        status="published", last_publication_id=publication.id, revision=1,
    )
    product.brand = brand
    listing = MerchantListing(
        id=new_uuid7(), product_id=product.id, merchant_id=merchant.id,
        source_listing_key="approved-listing-key", destination_url="https://shop.example/item",
        status="published", last_publication_id=publication.id, revision=1,
    )
    listing.merchant = merchant
    variants = [
        ListingVariant(
            id=new_uuid7(), listing_id=listing.id, source_variant_key="source-variant-m",
            size_label="M", color_label="Navy", color_family="blue",
            image_url="https://images.example/m.jpg", image_alt="Approved navy image",
            image_rights_ref="protected-image-rights", status="active",
            last_publication_id=publication.id, revision=1,
        ),
        ListingVariant(
            id=new_uuid7(), listing_id=listing.id, source_variant_key="source-variant-l",
            size_label="L", color_label="White", color_family="white",
            image_url="https://images.example/l.jpg", image_alt="Approved white image",
            image_rights_ref="protected-image-rights", status="active",
            last_publication_id=publication.id, revision=1,
        ),
    ]
    listing.variants = variants
    product.listings = [listing]
    price = PriceRecord(
        id=new_uuid7(), variant_id=variants[0].id, publication_id=publication.id,
        amount_minor=9_007_199_254_740_993, currency="INR", observed_at=now - timedelta(minutes=1),
        valid_until=now + timedelta(hours=3), recorded_at=now,
    )
    return product, publication, price


def test_public_discovery_filters_to_same_eligible_variant_and_serializes_paise_exactly():
    product, publication, price = _published_catalog()
    session = CatalogReadSessionProbe(product, price, publication)
    items, next_id = _run_immediate(
        eligible_product_page(
            session,
            query="Source-backed",
            category="tops",
            brand_id=product.brand_id,
            size="M",
            color="Navy",
            limit=1,
        )
    )
    assert next_id is None
    assert len(items) == 1
    assert items[0].representative["variant_id"] == product.listings[0].variants[0].id
    assert items[0].price.money.amount_minor == "9007199254740993"
    assert items[0].inventory is None
    compiled = str(session.statements[0].compile().params)
    assert "Source-backed" in compiled and "tops" in compiled


def test_public_detail_excludes_internal_rights_and_publication_fields():
    product, publication, price = _published_catalog()
    session = CatalogReadSessionProbe(product, price, publication)
    detail = _run_immediate(product_detail(session, product.id))
    assert detail is not None
    assert detail.listings[0].merchant["name"] == "Approved Merchant"
    assert detail.listings[0].destination_url == "https://shop.example/item"
    assert detail.listings[0].variants[0].price.money.amount_minor == "9007199254740993"
    serialized = str(detail.model_dump())
    assert "image_rights_ref" not in serialized
    assert "protected-image-rights" not in serialized
    assert "manifest_sha256" not in serialized


def test_revoked_latest_price_is_not_replaced_by_an_older_record():
    product, publication, price = _published_catalog()
    publication.status = "revoked"
    session = CatalogReadSessionProbe(product, price, publication)
    result = _run_immediate(price_state_for_variant(session, price.variant_id, datetime.now(UTC)))
    assert result == ("missing", None)
    query = str(session.statements[0])
    assert "recorded_at DESC" in query
    assert "id DESC" in query


def test_expired_latest_applied_price_is_reported_stale():
    product, publication, price = _published_catalog()
    price.valid_until = datetime.now(UTC) - timedelta(seconds=1)
    session = CatalogReadSessionProbe(product, price, publication)
    result = _run_immediate(price_state_for_variant(session, price.variant_id, datetime.now(UTC)))
    assert result == ("stale", None)
