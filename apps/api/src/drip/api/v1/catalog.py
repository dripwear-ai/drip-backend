from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from drip.catalog.abuse import require_public_catalog_rate_limit
from drip.catalog.contracts import (
    AdditionalListingInput,
    BrandInput,
    DiscoveryPage,
    DiscoveryRequest,
    MerchantInput,
    ProductCard,
    ProductDraftInput,
    ProductUpdateInput,
    PublicationPreviewInput,
    PublicProduct,
    PublishInput,
    WithdrawInput,
)
from drip.catalog.discovery_cursor import (
    MAX_SEEN,
    decode_discovery_cursor,
    encode_discovery_cursor,
)
from drip.catalog.pagination import decode_cursor, encode_cursor, filter_fingerprint
from drip.catalog.security import (
    CatalogAdminActor,
    get_catalog_writer_session,
    require_catalog_admin,
)
from drip.catalog.service import (
    _url_allowed,
    eligible_product_page,
    eligible_products,
    product_detail,
)
from drip.core.config import settings
from drip.core.database import get_db_session
from drip.core.errors import (
    ConflictException,
    DripException,
    NotFoundException,
    ServiceUnavailableException,
)
from drip.models.catalog import (
    Brand,
    CanonicalProduct,
    CatalogPublication,
    ListingVariant,
    Merchant,
    MerchantListing,
    PriceRecord,
)

router = APIRouter(tags=["Catalog"])
admin = APIRouter(prefix="/admin/catalog", tags=["Catalog administration"])
ReadSession = Annotated[AsyncSession, Depends(get_db_session)]
WriterSession = Annotated[AsyncSession, Depends(get_catalog_writer_session)]
AdminActor = Annotated[CatalogAdminActor, Depends(require_catalog_admin)]


@router.post(
    "/discover",
    response_model=DiscoveryPage,
    dependencies=[Depends(require_public_catalog_rate_limit)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": DiscoveryRequest.model_json_schema()}},
        }
    },
)
async def discover(
    request: Request, response: Response, session: ReadSession
) -> DiscoveryPage:
    """Return a single eligible card and a short-lived, signed continuation cursor."""
    response.headers["Cache-Control"] = "no-store"
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise DripException("Discovery request is malformed.", "VALIDATION_ERROR", 422) from None
    if not isinstance(body, dict):
        raise DripException("Discovery request is malformed.", "VALIDATION_ERROR", 422)
    has_cursor = "cursor" in body
    try:
        payload = DiscoveryRequest.model_validate(body)
    except ValidationError:
        code = "INVALID_CURSOR" if has_cursor else "VALIDATION_ERROR"
        message = "Discovery cursor is invalid." if has_cursor else "Discovery request is invalid."
        raise DripException(message, code, 422) from None
    filters: dict[str, object]
    seen: list[UUID]
    after_id: UUID | None
    cursor_mode = "next"
    cursor_anchor: UUID | None = None
    if payload.cursor is None:
        filters = payload.normalized_filters()
        seen = []
        after_id = None
        query = payload
    else:
        try:
            cursor_state = decode_discovery_cursor(payload.cursor)
        except TimeoutError:
            raise DripException("Discovery cursor has expired.", "CURSOR_EXPIRED", 422) from None
        except ValueError:
            raise DripException("Discovery cursor is invalid.", "INVALID_CURSOR", 422) from None
        filters = cursor_state.filters
        seen = list(cursor_state.seen_ids)
        after_id = cursor_state.last_id
        if payload.anchor_product_id is not None and payload.anchor_product_id not in cursor_state.seen_ids:
            raise DripException("Discovery cursor is invalid.", "INVALID_CURSOR", 422) from None
        try:
            query = DiscoveryRequest.model_validate(filters)
        except ValidationError:
            raise DripException("Discovery cursor is invalid.", "INVALID_CURSOR", 422) from None
        if payload.intent in {"similar", "different_brand"}:
            cursor_mode = payload.intent
            cursor_anchor = payload.anchor_product_id
            after_id = None
        else:
            cursor_mode = cursor_state.mode
            cursor_anchor = cursor_state.anchor_id

    if len(seen) >= MAX_SEEN:
        return DiscoveryPage(items=[], next_cursor=None, empty_reason="exhausted", catalog_as_of=datetime.now(UTC))

    brand_ids = query.brand_id if payload.cursor is not None else payload.brand_id
    categories = query.category if payload.cursor is not None else payload.category
    colors = query.color if payload.cursor is not None else payload.color
    sizes = query.size if payload.cursor is not None else payload.size
    effective_categories = list(categories or [])
    effective_colors = list(colors or [])
    exclude_brand_id: UUID | None = None
    no_matching_anchor_filters = False

    if payload.cursor is not None and cursor_mode in {"similar", "different_brand"}:
        assert cursor_anchor is not None
        anchor = await product_detail(session, cursor_anchor)
        if anchor is None:
            raise DripException(
                "Discovery must be reset because the selected product is no longer available.",
                "DISCOVERY_RESET_REQUIRED",
                409,
            )
        anchor_cards, _ = await eligible_product_page(
            session,
            query=query.q,
            brand_ids=query.brand_id,
            categories=query.category,
            sizes=query.size,
            colors=query.color,
            min_price_minor=int(query.min_price_minor) if query.min_price_minor is not None else None,
            max_price_minor=int(query.max_price_minor) if query.max_price_minor is not None else None,
            product_id=cursor_anchor,
            limit=1,
        )
        if not anchor_cards:
            raise DripException(
                "Discovery must be reset because the selected product is no longer eligible.",
                "DISCOVERY_RESET_REQUIRED",
                409,
            )
        if cursor_mode == "similar":
            effective_categories = [anchor.category_code] if not effective_categories else [
                category for category in effective_categories if category == anchor.category_code
            ]
            anchor_variant_id = anchor_cards[0].representative["variant_id"]
            anchor_color = next(
                (variant.color_label for listing in anchor.listings for variant in listing.variants
                 if variant.id == anchor_variant_id),
                None,
            )
            if not any(variant.id == anchor_variant_id for listing in anchor.listings for variant in listing.variants):
                raise DripException("Discovery must be reset because the selected product is no longer available.", "DISCOVERY_RESET_REQUIRED", 409)
            if anchor_color is not None:
                effective_colors = [anchor_color] if not effective_colors else [
                    color for color in effective_colors if color == anchor_color
                ]
            no_matching_anchor_filters = not effective_categories or not effective_colors
        else:
            brand_id = anchor.brand["id"]
            if not isinstance(brand_id, UUID):
                raise DripException("Discovery must be reset because the selected product is no longer available.", "DISCOVERY_RESET_REQUIRED", 409)
            exclude_brand_id = brand_id

    if no_matching_anchor_filters:
        items: list[ProductCard] = []
        next_id: UUID | None = None
    else:
        items, next_id = await eligible_product_page(
            session,
            query=query.q,
            brand_ids=brand_ids,
            categories=effective_categories or None,
            sizes=sizes,
            colors=effective_colors or None,
            min_price_minor=int(query.min_price_minor) if query.min_price_minor is not None else None,
            max_price_minor=int(query.max_price_minor) if query.max_price_minor is not None else None,
            exclude_brand_id=exclude_brand_id,
            exclude_ids=seen,
            limit=1,
            after_id=after_id,
        )
    if items:
        seen.append(items[0].id)
    cursor_after_id = next_id or (items[0].id if items else None)
    next_cursor = (
        encode_discovery_cursor(
            filters,
            seen,
            cursor_after_id,
            mode=cursor_mode if not items else "next",
            anchor_id=cursor_anchor if not items else None,
        )
        if cursor_after_id is not None and len(seen) < MAX_SEEN else None
    )
    empty_reason = None
    if not items:
        if next_cursor is not None:
            empty_reason = "no_eligible_products"
        elif cursor_mode == "similar":
            empty_reason = "no_similar_candidate"
        elif cursor_mode == "different_brand":
            empty_reason = "no_different_brand"
        elif payload.cursor is not None:
            empty_reason = "exhausted"
        else:
            empty_reason = "no_eligible_products"
    return DiscoveryPage(items=items, next_cursor=next_cursor, empty_reason=empty_reason, catalog_as_of=datetime.now(UTC))


@router.get("/catalog/products", dependencies=[Depends(require_public_catalog_rate_limit)])
async def list_products(
    response: Response,
    session: ReadSession,
    q: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, max_length=40),
    brand_id: UUID | None = None,
    size: str | None = Query(default=None, max_length=80),
    color: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=1, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    filters = {
        "q": q,
        "category": category,
        "brand_id": str(brand_id) if brand_id is not None else None,
        "size": size,
        "color": color,
        "limit": str(limit),
    }
    fingerprint = filter_fingerprint(filters)
    try:
        after_id = decode_cursor(cursor, fingerprint) if cursor is not None else None
    except ValueError:
        from drip.core.errors import DripException

        raise DripException("Catalog cursor is invalid.", "INVALID_CURSOR", 422) from None
    items, next_id = await eligible_product_page(
        session,
        query=q,
        category=category,
        brand_id=brand_id,
        size=size,
        color=color,
        limit=limit,
        after_id=after_id,
    )
    return {
        "items": items,
        "next_cursor": encode_cursor(next_id, fingerprint) if next_id is not None else None,
        "empty_reason": "no_eligible_products" if not items and next_id is None else None,
        "catalog_as_of": datetime.now(UTC),
    }


@router.get("/catalog/products/{product_id}", dependencies=[Depends(require_public_catalog_rate_limit)])
async def get_product(
    product_id: UUID, response: Response, session: ReadSession
) -> PublicProduct:
    response.headers["Cache-Control"] = "no-store"
    item = await product_detail(session, product_id)
    if item is None:
        raise NotFoundException("Product was not found.")
    return item


@router.get("/catalog/facets", dependencies=[Depends(require_public_catalog_rate_limit)])
async def catalog_facets(response: Response, session: ReadSession) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    cards = await eligible_products(session, limit=200)
    brands = {str(card.brand["id"]): card.brand["name"] for card in cards}
    categories = {card.category_code for card in cards}
    colors: set[str] = set()
    sizes: set[str] = set()
    for card in cards:
        detail = await product_detail(session, card.id)
        if detail is None:
            continue
        for listing in detail.listings:
            for variant in listing.variants:
                if variant.price_state != "current":
                    continue
                if variant.color_label:
                    colors.add(variant.color_label)
                if variant.size_label:
                    sizes.add(variant.size_label)
    return {
        "brands": [{"id": UUID(identifier), "name": name} for identifier, name in sorted(brands.items(), key=lambda item: item[1])[:50]],
        "categories": [{"code": value, "label": value} for value in sorted(categories)[:20]],
        "colors": [{"code": value, "label": value} for value in sorted(colors)[:50]],
        "sizes": sorted(sizes)[:50],
    }


def _need_write(actor: CatalogAdminActor) -> None:
    if not actor.can_write:
        from drip.core.errors import DripException

        raise DripException("Catalog administration is not permitted.", "FORBIDDEN", 403)


def _need_publish(actor: CatalogAdminActor) -> None:
    if not actor.can_publish:
        from drip.core.errors import DripException

        raise DripException("Catalog publication is not permitted.", "FORBIDDEN", 403)


def _publication_digest(
    product: CanonicalProduct,
    payload: PublishInput | PublicationPreviewInput,
    merchant_id: UUID,
    actor_id: UUID,
) -> str:
    body = {
        "environment": settings.ENVIRONMENT,
        "product_id": str(product.id),
        "merchant_id": str(merchant_id),
        "actor_id": str(actor_id),
        "database_fingerprint": hashlib.sha256(settings.DATABASE_URL.encode()).hexdigest(),
        "publication": payload.model_dump(
            mode="json", exclude={"request_key", "preview_digest"}
        ),
    }
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@admin.post("/brands", status_code=status.HTTP_201_CREATED)
async def create_brand(
    payload: BrandInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    brand = Brand(slug=payload.slug, display_name=payload.display_name, source_ref=payload.source_ref, reviewer_ref=str(actor.user_id))
    async with session.begin():
        duplicate = await session.scalar(select(Brand.id).where(Brand.slug == payload.slug))
        if duplicate is not None:
            raise ConflictException("Brand slug already exists.")
        session.add(brand)
        await session.flush()
    return {"id": brand.id, "slug": brand.slug, "display_name": brand.display_name, "status": brand.status}


@admin.post("/merchants", status_code=status.HTTP_201_CREATED)
async def create_merchant(
    payload: MerchantInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    merchant = Merchant(
        slug=payload.slug, display_name=payload.display_name,
        allowed_destination_hosts=payload.allowed_destination_hosts,
        allowed_image_hosts=payload.allowed_image_hosts,
        source_ref=payload.source_ref, reviewer_ref=str(actor.user_id),
    )
    async with session.begin():
        duplicate = await session.scalar(select(Merchant.id).where(Merchant.slug == payload.slug))
        if duplicate is not None:
            raise ConflictException("Merchant slug already exists.")
        session.add(merchant)
        await session.flush()
    return {"id": merchant.id, "slug": merchant.slug, "display_name": merchant.display_name, "purchase_mode": merchant.purchase_mode}


@admin.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product_draft(
    payload: ProductDraftInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    async with session.begin():
        brand = await session.get(Brand, payload.brand_id)
        merchant = await session.get(Merchant, payload.listing.merchant_id)
        if brand is None or brand.status != "active" or merchant is None or merchant.status != "active":
            raise ConflictException("Approved brand and merchant records are required.")
        duplicate = await session.scalar(
            select(CanonicalProduct.id).where(
                CanonicalProduct.brand_id == brand.id,
                CanonicalProduct.canonical_key == payload.canonical_key,
            )
        )
        if duplicate is not None:
            raise ConflictException("Canonical product key already exists for this brand.")
        if not _url_allowed(payload.listing.destination_url, merchant.allowed_destination_hosts):
            raise ConflictException("Retailer destination is not allowed for this merchant.")
        for variant in payload.listing.variants:
            if not _url_allowed(variant.image_url, merchant.allowed_image_hosts):
                raise ConflictException("Product image host is not allowed for this merchant.")
        product = CanonicalProduct(
            brand_id=brand.id, canonical_key=payload.canonical_key, title=payload.title,
            description=payload.description, category_code=payload.category_code, status="draft",
        )
        listing = MerchantListing(
            product=product, merchant_id=merchant.id, source_listing_key=payload.listing.source_listing_key,
            destination_url=payload.listing.destination_url, status="draft",
        )
        listing.variants = [
            ListingVariant(
                source_variant_key=v.source_variant_key, size_label=v.size_label, color_label=v.color_label,
                color_family=v.color_family, image_url=v.image_url, image_alt=v.image_alt,
                image_rights_ref=v.image_rights_ref, status="active",
            ) for v in payload.listing.variants
        ]
        session.add(product)
        await session.flush()
    return {"id": product.id, "status": product.status, "revision": product.revision}


@admin.post("/products/{product_id}/listings", status_code=status.HTTP_201_CREATED)
async def add_product_listing(
    product_id: UUID,
    payload: AdditionalListingInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    async with session.begin():
        product = await session.get(CanonicalProduct, product_id, with_for_update=True)
        merchant = await session.get(Merchant, payload.merchant_id)
        if product is None:
            raise NotFoundException("Product was not found.")
        if product.status not in {"draft", "published"} or product.revision != payload.expected_revision:
            raise ConflictException("Product changed or cannot accept another listing.")
        if merchant is None or merchant.status != "active":
            raise ConflictException("An approved active merchant is required.")
        duplicate = await session.scalar(
            select(MerchantListing.id).where(
                MerchantListing.merchant_id == merchant.id,
                MerchantListing.source_listing_key == payload.source_listing_key,
            )
        )
        if duplicate is not None:
            raise ConflictException("Source listing key already exists for this merchant.")
        if not _url_allowed(payload.destination_url, merchant.allowed_destination_hosts):
            raise ConflictException("Retailer destination is not allowed for this merchant.")
        if any(not _url_allowed(variant.image_url, merchant.allowed_image_hosts) for variant in payload.variants):
            raise ConflictException("Product image host is not allowed for this merchant.")
        listing = MerchantListing(
            product_id=product.id,
            merchant_id=merchant.id,
            source_listing_key=payload.source_listing_key,
            destination_url=payload.destination_url,
            status="draft",
        )
        listing.variants = [
            ListingVariant(
                source_variant_key=variant.source_variant_key,
                size_label=variant.size_label,
                color_label=variant.color_label,
                color_family=variant.color_family,
                image_url=variant.image_url,
                image_alt=variant.image_alt,
                image_rights_ref=variant.image_rights_ref,
                status="active",
            )
            for variant in payload.variants
        ]
        session.add(listing)
        product.revision += 1
        await session.flush()
    return {"id": listing.id, "product_id": product.id, "status": listing.status, "revision": product.revision}


@admin.put("/products/{product_id}")
async def edit_product_draft(
    product_id: UUID,
    payload: ProductUpdateInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    async with session.begin():
        product = await session.get(CanonicalProduct, product_id, with_for_update=True)
        if product is None:
            raise NotFoundException("Product was not found.")
        if product.status != "draft" or product.revision != payload.expected_revision:
            raise ConflictException("Product changed or is no longer an editable draft.")
        product.title = payload.title
        product.description = payload.description
        product.category_code = payload.category_code
        product.revision += 1
        await session.flush()
    return {"id": product.id, "status": product.status, "revision": product.revision}


@admin.post("/products/{product_id}/preview")
async def preview_product(
    product_id: UUID,
    payload: PublicationPreviewInput,
    actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_write(actor)
    product = await session.scalar(
        select(CanonicalProduct).options(selectinload(CanonicalProduct.listings).selectinload(MerchantListing.variants))
        .where(CanonicalProduct.id == product_id)
    )
    if product is None:
        raise NotFoundException("Product was not found.")
    if product.status not in {"draft", "published"} or product.revision != payload.expected_revision:
        raise ConflictException("Product changed or cannot accept a publication.")
    selected_ids = set(payload.listing_ids)
    selected = [listing for listing in product.listings if listing.id in selected_ids]
    if len(selected) != len(payload.listing_ids):
        raise ConflictException("One or more selected listings do not belong to this product.")
    merchant_ids = {listing.merchant_id for listing in selected}
    if len(merchant_ids) != 1:
        raise ConflictException("A publication must contain listings for one merchant.")
    variant_ids = {
        variant.id
        for listing in selected
        for variant in listing.variants
        if variant.status == "active"
    }
    price_ids = [row.variant_id for row in payload.prices]
    if not variant_ids or len(set(price_ids)) != len(price_ids) or set(price_ids) != variant_ids:
        raise ConflictException("A current source price is required for each active selected variant.")
    merchant_id = next(iter(merchant_ids))
    return {
        "id": product.id,
        "status": product.status,
        "revision": product.revision,
        "changes": {"title": product.title, "category_code": product.category_code},
        "digest": _publication_digest(product, payload, merchant_id, actor.user_id),
        "errors": [],
    }


@admin.post("/products/{product_id}/publish")
async def publish_product(
    product_id: UUID, payload: PublishInput, actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_publish(actor)
    if settings.CATALOG_PRICE_FRESHNESS_HOURS is None or settings.CATALOG_MAX_PRICE_MINOR is None:
        raise ServiceUnavailableException("Catalog price eligibility policy is not configured.")
    allowed_categories = {value.strip() for value in settings.CATALOG_ALLOWED_CATEGORIES.split(",") if value.strip()}
    if not allowed_categories:
        raise ServiceUnavailableException("Catalog taxonomy is not configured.")
    async with session.begin():
        product = await session.scalar(
            select(CanonicalProduct).options(
                selectinload(CanonicalProduct.brand),
                selectinload(CanonicalProduct.listings).selectinload(MerchantListing.merchant),
                selectinload(CanonicalProduct.listings).selectinload(MerchantListing.variants),
            ).where(CanonicalProduct.id == product_id).with_for_update()
        )
        if product is None:
            raise NotFoundException("Product was not found.")
        selected_ids = set(payload.listing_ids)
        selected = [listing for listing in product.listings if listing.id in selected_ids]
        if len(selected) != len(payload.listing_ids):
            raise ConflictException("One or more selected listings do not belong to this product.")
        merchant_ids = {listing.merchant_id for listing in selected}
        if len(merchant_ids) != 1:
            raise ConflictException("A publication must contain listings for one merchant.")
        merchant_id = next(iter(merchant_ids))

        lock_key = int.from_bytes(
            hashlib.sha256(payload.request_key.bytes).digest()[:8], "big", signed=True
        )
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        digest = _publication_digest(product, payload, merchant_id, actor.user_id)
        if digest != payload.preview_digest:
            raise ConflictException("Publication payload no longer matches the reviewed preview.")
        existing = await session.scalar(
            select(CatalogPublication)
            .where(CatalogPublication.request_key == payload.request_key)
            .with_for_update()
        )
        if existing is not None:
            if existing.manifest_sha256 != digest:
                raise ConflictException("Publication request key conflicts with an existing operation.")
            return {"publication_id": existing.id, "status": existing.status}

        if product.status not in {"draft", "published"} or product.revision != payload.expected_revision:
            raise ConflictException("Product changed or cannot accept a publication.")
        if product.category_code not in allowed_categories:
            raise ConflictException("Product category is not in the configured catalog taxonomy.")
        if product.brand.status != "active":
            raise ConflictException("Brand is not eligible for publication.")
        variants = [v for listing in selected for v in listing.variants if v.status == "active"]
        prices = {row.variant_id: row.price for row in payload.prices}
        if not variants or len(prices) != len(payload.prices) or set(prices) != {v.id for v in variants}:
            raise ConflictException("A current source price is required for each active selected variant.")
        now = datetime.now(UTC)
        for listing in selected:
            if not _url_allowed(listing.destination_url, listing.merchant.allowed_destination_hosts):
                raise ConflictException("Retailer destination is not allowed for this merchant.")
            if listing.merchant.status != "active":
                raise ConflictException("Merchant is not eligible for publication.")
            for variant in listing.variants:
                if variant.status == "active" and not _url_allowed(variant.image_url, listing.merchant.allowed_image_hosts):
                    raise ConflictException("Image host is not allowed for this merchant.")
        publication = CatalogPublication(
            merchant_id=merchant_id, request_key=payload.request_key, manifest_sha256=digest,
            schema_version=1, reviewer_ref=str(actor.user_id), approval_ref=payload.approval_ref,
            status="applied",
            change_summary={
                "product_id": str(product.id),
                "from_revision": product.revision,
                "to_revision": product.revision + 1,
                "listing_ids": [str(listing.id) for listing in selected],
                "variant_count": len(variants),
                "changed_fields": ["status", "last_publication_id", "prices"],
            },
        )
        session.add(publication)
        await session.flush()
        for listing in selected:
            listing.status = "published"
            listing.last_publication_id = publication.id
            listing.revision += 1
            for variant in listing.variants:
                variant.last_publication_id = publication.id
                data = prices[variant.id]
                if data.observed_at > now or data.valid_until <= now:
                    raise ConflictException("Price observation is not currently eligible.")
                if data.valid_until - data.observed_at > timedelta(hours=settings.CATALOG_PRICE_FRESHNESS_HOURS):
                    raise ConflictException("Price validity exceeds the configured freshness policy.")
                if int(data.amount_minor) > settings.CATALOG_MAX_PRICE_MINOR:
                    raise ConflictException("Price exceeds the configured catalog ceiling.")
                session.add(PriceRecord(
                    variant_id=variant.id, publication_id=publication.id,
                    amount_minor=int(data.amount_minor), currency="INR",
                    observed_at=data.observed_at, valid_until=data.valid_until,
                ))
        product.status = "published"
        product.last_publication_id = publication.id
        product.revision += 1
        await session.flush()
    return {"publication_id": publication.id, "status": publication.status, "product_id": product.id}


@admin.post("/products/{product_id}/withdraw")
async def withdraw_product(
    product_id: UUID, payload: WithdrawInput, actor: AdminActor,
    session: WriterSession,
) -> dict[str, object]:
    _need_publish(actor)
    async with session.begin():
        product = await session.scalar(
            select(CanonicalProduct).options(selectinload(CanonicalProduct.listings))
            .where(CanonicalProduct.id == product_id).with_for_update()
        )
        if product is None:
            raise NotFoundException("Product was not found.")
        if product.revision != payload.expected_revision or product.status != "published":
            raise ConflictException("Product changed or is not published.")
        publication_ids = {listing.last_publication_id for listing in product.listings if listing.last_publication_id is not None}
        if product.last_publication_id is not None:
            publication_ids.add(product.last_publication_id)
        if not publication_ids:
            raise ConflictException("Current publication state is inconsistent.")
        now = datetime.now(UTC)
        for publication_id in publication_ids:
            publication = await session.get(CatalogPublication, publication_id, with_for_update=True)
            if publication is None or publication.status != "applied":
                raise ConflictException("Current publication state is inconsistent.")
            publication.status = "revoked"
            publication.revoked_at = now
            publication.revocation_audit = {
                "operator_ref": str(actor.user_id),
                "reason_category": payload.reason_category,
                "approval_ref": payload.approval_ref,
            }
        for listing in product.listings:
            listing.status = "withdrawn"
            listing.revision += 1
        product.status = "withdrawn"
        product.revision += 1
        await session.flush()
    return {"id": product.id, "status": product.status, "revision": product.revision}


router.include_router(admin)
