"""Eligibility-filtered, guest-accessible OOTD feed and signed paging cursor."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from drip.catalog.contracts import PublicProduct
from drip.catalog.service import eligible_product_page, product_detail
from drip.core.config import settings
from drip.models.outfit import Outfit
from drip.outfit.contracts import OutfitImage, OutfitProduct, PublicOutfit

MAX_OUTFIT_SCAN = 100


@dataclass(frozen=True, slots=True)
class OutfitCursor:
    published_at: datetime
    outfit_id: UUID


def encode_cursor(value: OutfitCursor) -> str:
    body = json.dumps(
        {"v": 1, "published_at": value.published_at.isoformat(), "id": str(value.outfit_id)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), body, hashlib.sha256).digest()
    return f"{_encode(body)}.{_encode(signature)}"


def decode_cursor(token: str) -> OutfitCursor:
    try:
        if len(token) > 512 or token.count(".") != 1:
            raise ValueError
        body_part, signature_part = token.split(".", maxsplit=1)
        body = _decode(body_part)
        signature = _decode(signature_part)
        expected = hmac.new(settings.SECRET_KEY.encode("utf-8"), body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(body)
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or not isinstance(payload.get("published_at"), str)
            or not isinstance(payload.get("id"), str)
        ):
            raise ValueError
        published_at = datetime.fromisoformat(payload["published_at"])
        if published_at.tzinfo is None:
            raise ValueError
        return OutfitCursor(published_at, UUID(payload["id"]))
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Invalid OOTD cursor.") from None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("Non-canonical OOTD cursor encoding.")
    return decoded


def _public_image(url: str, alt: str) -> OutfitImage | None:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if host is None:
            return None
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return None
        if (
            parsed.scheme != "https"
            or "." not in host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
        ):
            return None
        return OutfitImage(url=url, alt=alt)
    except ValueError:
        return None


async def public_outfit(session: AsyncSession, outfit: Outfit) -> PublicOutfit | None:
    """Return an outfit only when every required product remains public."""
    if (
        outfit.status != "published"
        or outfit.published_at is None
        or outfit.brand.status != "active"
        or not outfit.rights_ref.strip()
        or not outfit.approval_ref.strip()
        or len(outfit.items) < 2
        or len(outfit.items) > 8
    ):
        return None
    image = _public_image(outfit.image_url, outfit.image_alt)
    if image is None:
        return None

    products: list[OutfitProduct] = []
    for item in sorted(outfit.items, key=lambda row: row.position):
        eligible, _ = await eligible_product_page(
            session, product_id=item.product_id, limit=1
        )
        if not eligible:
            return None
        detail: PublicProduct | None = await product_detail(session, item.product_id)
        if detail is None:
            return None
        eligible_variant_id = eligible[0].representative["variant_id"]
        variant = next(
            (
                variant
                for listing in detail.listings
                for variant in listing.variants
                if variant.id == eligible_variant_id
            ),
            None,
        )
        if variant is None:
            return None
        product_image = _public_image(variant.image_url, variant.image_alt)
        if product_image is None:
            return None
        products.append(OutfitProduct(id=detail.id, title=detail.title, image=product_image))
    return PublicOutfit(
        id=outfit.id,
        title=outfit.title,
        caption=outfit.caption,
        brand={"id": outfit.brand.id, "name": outfit.brand.display_name},
        image=image,
        products=products,
    )


async def list_public_outfits(
    session: AsyncSession, *, limit: int, cursor: OutfitCursor | None
) -> tuple[list[PublicOutfit], OutfitCursor | None]:
    statement = (
        select(Outfit)
        .options(selectinload(Outfit.items), selectinload(Outfit.brand))
        .where(Outfit.status == "published", Outfit.published_at.is_not(None))
        .order_by(Outfit.published_at.desc(), Outfit.id.desc())
        .limit(MAX_OUTFIT_SCAN + 1)
    )
    if cursor is not None:
        statement = statement.where(
            or_(
                Outfit.published_at < cursor.published_at,
                and_(Outfit.published_at == cursor.published_at, Outfit.id < cursor.outfit_id),
            )
        )
    candidates = (await session.scalars(statement)).all()
    scanned = candidates[:MAX_OUTFIT_SCAN]
    page: list[PublicOutfit] = []
    next_cursor: OutfitCursor | None = None
    last_scanned: Outfit | None = None
    for index, outfit in enumerate(scanned):
        last_scanned = outfit
        item = await public_outfit(session, outfit)
        if item is not None:
            page.append(item)
            if len(page) == limit:
                if index + 1 < len(candidates) and outfit.published_at is not None:
                    next_cursor = OutfitCursor(outfit.published_at, outfit.id)
                break
    else:
        if (
            len(candidates) > MAX_OUTFIT_SCAN
            and last_scanned is not None
            and last_scanned.published_at is not None
        ):
            next_cursor = OutfitCursor(last_scanned.published_at, last_scanned.id)
    return page, next_cursor


async def get_public_outfit(
    session: AsyncSession, outfit_id: UUID
) -> PublicOutfit | None:
    """Load one public outfit without revealing draft or ineligible records."""
    outfit = await session.scalar(
        select(Outfit)
        .options(selectinload(Outfit.items), selectinload(Outfit.brand))
        .where(Outfit.id == outfit_id)
    )
    if outfit is None:
        return None
    return await public_outfit(session, outfit)
