from __future__ import annotations

import ipaddress
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from drip.catalog.contracts import (
    MoneyDTO,
    ProductCard,
    PublicListing,
    PublicPrice,
    PublicProduct,
    PublicVariant,
)
from drip.models.catalog import (
    Brand,
    CanonicalProduct,
    CatalogPublication,
    ListingVariant,
    MerchantListing,
    PriceRecord,
)


def _url_allowed(value: str, allowed_hosts: list[str]) -> bool:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if hostname is None:
            return False
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return False
        return (
            parsed.scheme == "https"
            and hostname.lower() in allowed_hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


async def price_state_for_variant(
    session: AsyncSession, variant_id: UUID, now: datetime
) -> tuple[str, PriceRecord | None]:
    latest_id = (
        select(PriceRecord.id)
        .where(PriceRecord.variant_id == variant_id)
        .order_by(PriceRecord.recorded_at.desc(), PriceRecord.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    result = await session.execute(
        select(PriceRecord, CatalogPublication.status)
        .join(CatalogPublication, CatalogPublication.id == PriceRecord.publication_id)
        .where(PriceRecord.id == latest_id)
    )
    row = result.one_or_none()
    if row is None or row[1] != "applied":
        return "missing", None
    price = row[0]
    if price.observed_at > now:
        return "missing", None
    if price.valid_until <= now:
        return "stale", None
    return "current", price


async def current_price_for_variant(
    session: AsyncSession, variant_id: UUID, now: datetime
) -> PriceRecord | None:
    state, price = await price_state_for_variant(session, variant_id, now)
    return price if state == "current" else None


async def _publication_applied(session: AsyncSession, publication_id: UUID | None) -> bool:
    if publication_id is None:
        return False
    return await session.scalar(
        select(CatalogPublication.id).where(
            CatalogPublication.id == publication_id,
            CatalogPublication.status == "applied",
        )
    ) is not None


async def eligible_product_page(
    session: AsyncSession,
    *,
    query: str | None = None,
    category: str | None = None,
    brand_id: UUID | None = None,
    size: str | None = None,
    color: str | None = None,
    limit: int = 1,
    after_id: UUID | None = None,
    brand_ids: list[UUID] | None = None,
    categories: list[str] | None = None,
    sizes: list[str] | None = None,
    colors: list[str] | None = None,
    min_price_minor: int | None = None,
    max_price_minor: int | None = None,
    exclude_brand_id: UUID | None = None,
    exclude_ids: list[UUID] | None = None,
    product_id: UUID | None = None,
) -> tuple[list[ProductCard], UUID | None]:
    statement = (
        select(CanonicalProduct)
        .join(Brand)
        .options(
            selectinload(CanonicalProduct.brand),
            selectinload(CanonicalProduct.listings)
            .selectinload(MerchantListing.merchant),
            selectinload(CanonicalProduct.listings)
            .selectinload(MerchantListing.variants),
        )
        .where(CanonicalProduct.status == "published", Brand.status == "active")
        .order_by(CanonicalProduct.id)
    )
    if brand_id is not None:
        statement = statement.where(CanonicalProduct.brand_id == brand_id)
    if brand_ids:
        statement = statement.where(CanonicalProduct.brand_id.in_(brand_ids))
    if categories:
        statement = statement.where(CanonicalProduct.category_code.in_(categories))
    if exclude_brand_id is not None:
        statement = statement.where(CanonicalProduct.brand_id != exclude_brand_id)
    if exclude_ids:
        statement = statement.where(CanonicalProduct.id.not_in(exclude_ids))
    if product_id is not None:
        statement = statement.where(CanonicalProduct.id == product_id)
    if after_id is not None:
        statement = statement.where(CanonicalProduct.id > after_id)
    if category and not categories:
        statement = statement.where(CanonicalProduct.category_code == category)
    if query:
        escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            CanonicalProduct.title.ilike(f"%{escaped_query}%", escape="\\")
            | CanonicalProduct.category_code.ilike(f"%{escaped_query}%", escape="\\")
            | Brand.display_name.ilike(f"%{escaped_query}%", escape="\\")
        )
    candidates = (await session.scalars(statement.limit(201))).all()
    products = candidates[:200]
    now = datetime.now(UTC)
    cards: list[ProductCard] = []
    for product in products:
        if not await _publication_applied(session, product.last_publication_id):
            continue
        choices: list[tuple[MerchantListing, ListingVariant, PriceRecord]] = []
        for listing in product.listings:
            merchant = listing.merchant
            if listing.status != "published" or merchant.status != "active":
                continue
            if not await _publication_applied(session, listing.last_publication_id):
                continue
            for variant in listing.variants:
                if variant.status != "active":
                    continue
                if not await _publication_applied(session, variant.last_publication_id):
                    continue
                if size and variant.size_label != size:
                    continue
                if sizes and variant.size_label not in sizes:
                    continue
                if color and variant.color_label != color:
                    continue
                if colors and variant.color_label not in colors:
                    continue
                if not _url_allowed(variant.image_url, merchant.allowed_image_hosts):
                    continue
                price = await current_price_for_variant(session, variant.id, now)
                if (
                    price is not None
                    and (min_price_minor is None or price.amount_minor >= min_price_minor)
                    and (max_price_minor is None or price.amount_minor <= max_price_minor)
                ):
                    choices.append((listing, variant, price))
        if not choices:
            continue
        listing, variant, price = min(choices, key=lambda row: (row[2].amount_minor, str(row[0].id), str(row[1].id)))
        cards.append(
            ProductCard(
                id=product.id,
                brand={"id": product.brand.id, "name": product.brand.display_name},
                title=product.title,
                category_code=product.category_code,
                image={"url": variant.image_url, "alt": variant.image_alt},
                representative={"listing_id": listing.id, "variant_id": variant.id},
                price=PublicPrice(
                    money=MoneyDTO(amount_minor=str(price.amount_minor)),
                    observed_at=price.observed_at,
                    valid_until=price.valid_until,
                ),
                price_is_from=len({row[2].amount_minor for row in choices}) > 1,
                inventory=None,
            )
        )
        if len(cards) > limit:
            break
    if len(cards) > limit:
        page = cards[:limit]
        next_after = page[-1].id
    elif len(candidates) > 200 and products:
        page = cards
        next_after = products[-1].id
    else:
        page = cards
        next_after = None
    return page, next_after


async def eligible_products(
    session: AsyncSession,
    *,
    query: str | None = None,
    category: str | None = None,
    brand_id: UUID | None = None,
    size: str | None = None,
    color: str | None = None,
    limit: int = 1,
) -> list[ProductCard]:
    """Compatibility helper for bounded internal callers that need one page only."""
    items, _ = await eligible_product_page(
        session,
        query=query,
        category=category,
        brand_id=brand_id,
        size=size,
        color=color,
        limit=limit,
    )
    return items


async def product_detail(session: AsyncSession, product_id: UUID) -> PublicProduct | None:
    product = await session.scalar(
        select(CanonicalProduct)
        .join(Brand)
        .options(
            selectinload(CanonicalProduct.brand),
            selectinload(CanonicalProduct.listings)
            .selectinload(MerchantListing.merchant),
            selectinload(CanonicalProduct.listings)
            .selectinload(MerchantListing.variants),
        )
        .where(
            CanonicalProduct.id == product_id,
            CanonicalProduct.status == "published",
            Brand.status == "active",
        )
    )
    if product is None:
        return None
    if product.last_publication_id is None:
        return None
    product_publication = await session.get(CatalogPublication, product.last_publication_id)
    if product_publication is None or product_publication.status != "applied":
        return None
    result_listings: list[PublicListing] = []
    now = datetime.now(UTC)
    for listing in product.listings[:10]:
        merchant = listing.merchant
        if listing.status != "published" or merchant.status != "active":
            continue
        if not await _publication_applied(session, listing.last_publication_id):
            continue
        public_variants: list[PublicVariant] = []
        for variant in listing.variants[:100]:
            if variant.status != "active" or not _url_allowed(variant.image_url, merchant.allowed_image_hosts):
                continue
            if not await _publication_applied(session, variant.last_publication_id):
                continue
            state, price_row = await price_state_for_variant(session, variant.id, now)
            price = None
            if state == "current" and price_row is not None:
                price = PublicPrice(
                    money=MoneyDTO(amount_minor=str(price_row.amount_minor)),
                    observed_at=price_row.observed_at,
                    valid_until=price_row.valid_until,
                )
            public_variants.append(
                PublicVariant(
                    id=variant.id,
                    size_label=variant.size_label,
                    color_label=variant.color_label,
                    image_url=variant.image_url,
                    image_alt=variant.image_alt,
                    price=price,
                    price_state=state,
                    inventory=None,
                )
            )
        if public_variants:
            destination = listing.destination_url if _url_allowed(listing.destination_url, merchant.allowed_destination_hosts) else None
            result_listings.append(PublicListing(
                id=listing.id,
                merchant={"id": merchant.id, "name": merchant.display_name},
                destination_url=destination,
                variants=public_variants,
            ))
    if not result_listings:
        return None
    return PublicProduct(
        id=product.id,
        brand={"id": product.brand.id, "name": product.brand.display_name},
        title=product.title,
        description=product.description,
        category_code=product.category_code,
        listings=result_listings[:10],
    )
