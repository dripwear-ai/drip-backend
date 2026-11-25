from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from drip.catalog.abuse import require_public_catalog_rate_limit
from drip.catalog.security import (
    CatalogAdminActor,
    get_catalog_writer_session,
    require_catalog_admin,
)
from drip.catalog.service import eligible_product_page
from drip.core.database import get_db_session
from drip.core.errors import ConflictException, DripException, NotFoundException
from drip.models.catalog import Brand, CanonicalProduct
from drip.models.outfit import Outfit, OutfitItem, OutfitPublication
from drip.outfit.contracts import (
    OutfitArchiveInput,
    OutfitDraftInput,
    OutfitPage,
    OutfitPreviewInput,
    OutfitPublishInput,
    OutfitUpdateInput,
    PublicOutfit,
)
from drip.outfit.service import (
    _public_image,
    decode_cursor,
    encode_cursor,
    get_public_outfit,
    list_public_outfits,
)

router = APIRouter(tags=["Outfits"])
admin = APIRouter(prefix="/admin/ootd", tags=["Outfit administration"])
ReadSession = Annotated[AsyncSession, Depends(get_db_session)]
WriterSession = Annotated[AsyncSession, Depends(get_catalog_writer_session)]
AdminActor = Annotated[CatalogAdminActor, Depends(require_catalog_admin)]


def _require_write(actor: CatalogAdminActor) -> None:
    if not actor.can_write:
        raise DripException("Outfit administration is not permitted.", "FORBIDDEN", 403)


def _require_publish(actor: CatalogAdminActor) -> None:
    if not actor.can_publish:
        raise DripException("Outfit publication is not permitted.", "FORBIDDEN", 403)


async def _get_admin_outfit(session: AsyncSession, outfit_id: UUID, *, lock: bool = False) -> Outfit:
    statement = select(Outfit).options(selectinload(Outfit.items), selectinload(Outfit.brand)).where(Outfit.id == outfit_id)
    if lock:
        statement = statement.with_for_update()
    outfit = await session.scalar(statement)
    if outfit is None:
        raise NotFoundException("Outfit was not found.")
    return outfit


def _outfit_digest(outfit: Outfit, actor: CatalogAdminActor, *, action: str) -> str:
    payload = {
        "action": action,
        "outfit_id": str(outfit.id),
        "brand_id": str(outfit.brand_id),
        "actor_id": str(actor.user_id),
        "title": outfit.title,
        "caption": outfit.caption,
        "image_url": outfit.image_url,
        "image_alt": outfit.image_alt,
        "rights_ref": outfit.rights_ref,
        "approval_ref": outfit.approval_ref,
        "product_ids": [str(row.product_id) for row in sorted(outfit.items, key=lambda item: item.position)],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _publication_errors(session: AsyncSession, outfit: Outfit) -> list[str]:
    errors: list[str] = []
    if _public_image(outfit.image_url, outfit.image_alt) is None:
        errors.append("An approved HTTPS editorial image is required.")
    if not outfit.rights_ref.strip() or not outfit.approval_ref.strip():
        errors.append("Editorial rights and approval references are required.")
    if outfit.brand.status != "active":
        errors.append("An active approved brand is required.")
    if not 2 <= len(outfit.items) <= 8:
        errors.append("A published outfit must contain between two and eight products.")
    for item in outfit.items:
        eligible, _ = await eligible_product_page(session, product_id=item.product_id, limit=1)
        if not eligible:
            errors.append("Every outfit component must remain publicly eligible.")
            break
    return errors


def _publication_record(
    outfit: Outfit,
    *,
    actor: CatalogAdminActor,
    request_key: UUID,
    action: str,
    approval_ref: str,
    digest: str,
    prior_revision: int | None,
    next_revision: int,
) -> OutfitPublication:
    return OutfitPublication(
        outfit_id=outfit.id,
        request_key=request_key,
        manifest_sha256=digest,
        actor_ref=str(actor.user_id),
        approval_ref=approval_ref,
        prior_revision=prior_revision,
        next_revision=next_revision,
        action=action,
    )


@router.get(
    "/ootd",
    response_model=OutfitPage,
    dependencies=[Depends(require_public_catalog_rate_limit)],
)
async def ootd_feed(
    response: Response,
    session: ReadSession,
    limit: int = Query(default=5, ge=1, le=10),
    cursor: str | None = Query(default=None, max_length=512),
) -> OutfitPage:
    response.headers["Cache-Control"] = "no-store"
    try:
        position = decode_cursor(cursor) if cursor is not None else None
    except ValueError:
        raise DripException("OOTD cursor is invalid.", "INVALID_CURSOR", 422) from None
    items, next_position = await list_public_outfits(
        session, limit=limit, cursor=position
    )
    return OutfitPage(
        items=items,
        next_cursor=encode_cursor(next_position) if next_position is not None else None,
    )


@router.get(
    "/ootd/{outfit_id}",
    response_model=PublicOutfit,
    dependencies=[Depends(require_public_catalog_rate_limit)],
)
async def ootd_detail(
    outfit_id: UUID, response: Response, session: ReadSession
) -> PublicOutfit:
    response.headers["Cache-Control"] = "no-store"
    outfit = await get_public_outfit(session, outfit_id)
    if outfit is None:
        raise NotFoundException("Outfit was not found.")
    return outfit


@admin.post("", status_code=201)
async def create_outfit_draft(payload: OutfitDraftInput, actor: AdminActor, session: WriterSession) -> dict[str, object]:
    _require_write(actor)
    async with session.begin():
        brand = await session.get(Brand, payload.brand_id)
        if brand is None or brand.status != "active":
            raise ConflictException("An active approved brand is required.")
        found = set(
            (
                await session.scalars(
                    select(CanonicalProduct.id).where(CanonicalProduct.id.in_(payload.product_ids))
                )
            ).all()
        ) if payload.product_ids else set()
        if found != set(payload.product_ids):
            raise ConflictException("Every referenced product must exist in the catalogue.")
        outfit = Outfit(
            brand_id=payload.brand_id,
            title=payload.title,
            caption=payload.caption,
            image_url=payload.image_url,
            image_alt=payload.image_alt,
            rights_ref=payload.rights_ref,
            approval_ref=payload.approval_ref,
            status="draft",
        )
        outfit.items = [OutfitItem(position=index, product_id=product_id) for index, product_id in enumerate(payload.product_ids, start=1)]
        session.add(outfit)
        await session.flush()
    return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}


@admin.put("/{outfit_id}")
async def update_outfit_draft(
    outfit_id: UUID, payload: OutfitUpdateInput, actor: AdminActor, session: WriterSession
) -> dict[str, object]:
    _require_write(actor)
    async with session.begin():
        outfit = await _get_admin_outfit(session, outfit_id, lock=True)
        if outfit.status != "draft" or outfit.revision != payload.expected_revision:
            raise ConflictException("Outfit changed or is no longer an editable draft.")
        brand = await session.get(Brand, payload.brand_id)
        if brand is None or brand.status != "active":
            raise ConflictException("An active approved brand is required.")
        found = set(
            (
                await session.scalars(
                    select(CanonicalProduct.id).where(CanonicalProduct.id.in_(payload.product_ids))
                )
            ).all()
        ) if payload.product_ids else set()
        if found != set(payload.product_ids):
            raise ConflictException("Every referenced product must exist in the catalogue.")
        outfit.title = payload.title
        outfit.brand_id = payload.brand_id
        outfit.caption = payload.caption
        outfit.image_url = payload.image_url
        outfit.image_alt = payload.image_alt
        outfit.rights_ref = payload.rights_ref
        outfit.approval_ref = payload.approval_ref
        outfit.items.clear()
        await session.flush()
        outfit.items.extend([
            OutfitItem(position=index, product_id=product_id)
            for index, product_id in enumerate(payload.product_ids, start=1)
        ])
        outfit.revision += 1
        outfit.updated_at = datetime.now(UTC)
        await session.flush()
    return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}


@admin.post("/{outfit_id}/preview")
async def preview_outfit(
    outfit_id: UUID, payload: OutfitPreviewInput, actor: AdminActor, session: WriterSession
) -> dict[str, object]:
    _require_write(actor)
    outfit = await _get_admin_outfit(session, outfit_id)
    if outfit.status != "draft" or outfit.revision != payload.expected_revision:
        raise ConflictException("Outfit changed or is no longer a previewable draft.")
    errors = await _publication_errors(session, outfit)
    return {
        "id": outfit.id,
        "status": outfit.status,
        "revision": outfit.revision,
        "digest": _outfit_digest(outfit, actor, action="publish") if not errors else None,
        "errors": errors,
    }


@admin.post("/{outfit_id}/publish")
async def publish_outfit(
    outfit_id: UUID, payload: OutfitPublishInput, actor: AdminActor, session: WriterSession
) -> dict[str, object]:
    _require_publish(actor)
    async with session.begin():
        lock_key = int.from_bytes(hashlib.sha256(payload.request_key.bytes).digest()[:8], "big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        existing = await session.scalar(
            select(OutfitPublication).where(OutfitPublication.request_key == payload.request_key).with_for_update()
        )
        outfit = await _get_admin_outfit(session, outfit_id, lock=True)
        if existing is not None:
            digest = _outfit_digest(outfit, actor, action="publish")
            if existing.outfit_id != outfit.id or existing.manifest_sha256 != digest:
                raise ConflictException("Outfit publication request key conflicts with another operation.")
            return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}
        if outfit.status != "draft" or outfit.revision != payload.expected_revision:
            raise ConflictException("Outfit changed or is no longer publishable.")
        errors = await _publication_errors(session, outfit)
        if errors:
            raise ConflictException("Outfit is not eligible for publication.")
        digest = _outfit_digest(outfit, actor, action="publish")
        if payload.preview_digest != digest:
            raise ConflictException("Outfit content changed after preview.")
        prior_revision = outfit.revision
        now = datetime.now(UTC)
        outfit.status = "published"
        outfit.published_at = now
        outfit.updated_at = now
        outfit.revision += 1
        session.add(_publication_record(
            outfit, actor=actor, request_key=payload.request_key, action="publish",
            approval_ref=outfit.approval_ref, digest=digest,
            prior_revision=prior_revision, next_revision=outfit.revision,
        ))
        await session.flush()
    return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}


@admin.post("/{outfit_id}/archive")
async def archive_outfit(
    outfit_id: UUID, payload: OutfitArchiveInput, actor: AdminActor, session: WriterSession
) -> dict[str, object]:
    _require_publish(actor)
    async with session.begin():
        lock_key = int.from_bytes(hashlib.sha256(payload.request_key.bytes).digest()[:8], "big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
        existing = await session.scalar(
            select(OutfitPublication).where(OutfitPublication.request_key == payload.request_key).with_for_update()
        )
        outfit = await _get_admin_outfit(session, outfit_id, lock=True)
        digest = _outfit_digest(outfit, actor, action="archive")
        if existing is not None:
            if existing.outfit_id != outfit.id or existing.manifest_sha256 != digest:
                raise ConflictException("Outfit archive request key conflicts with another operation.")
            return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}
        if outfit.status != "published" or outfit.revision != payload.expected_revision:
            raise ConflictException("Outfit changed or is no longer publishable for archive.")
        prior_revision = outfit.revision
        outfit.status = "archived"
        outfit.updated_at = datetime.now(UTC)
        outfit.revision += 1
        session.add(_publication_record(
            outfit, actor=actor, request_key=payload.request_key, action="archive",
            approval_ref=payload.approval_ref, digest=digest,
            prior_revision=prior_revision, next_revision=outfit.revision,
        ))
        await session.flush()
    return {"id": outfit.id, "status": outfit.status, "revision": outfit.revision}


router.include_router(admin)
