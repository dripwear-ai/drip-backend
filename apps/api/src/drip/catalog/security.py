"""Fail-closed integration point for DRIP-side catalog administration grants."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from drip.core.errors import ServiceUnavailableException


@dataclass(frozen=True, slots=True)
class CatalogAdminActor:
    """Trusted service output. Never constructed from request fields or token roles."""

    user_id: UUID
    can_write: bool
    can_publish: bool


async def require_catalog_admin() -> CatalogAdminActor:
    """Deny until the approved Auth0/session/admin-grant provider is wired."""
    raise ServiceUnavailableException("Catalog administrator authorization is not configured.")


async def get_catalog_writer_session() -> AsyncGenerator[AsyncSession]:
    """Deny mutations until a separately provisioned catalog-writer role is configured."""
    raise ServiceUnavailableException("Catalog writer database access is not configured.")
    yield  # pragma: no cover - preserves the async-generator dependency contract


