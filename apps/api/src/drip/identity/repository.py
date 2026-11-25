"""Internal identity persistence through the reviewed database capabilities.

This module is not a route or an authorization grant. It accepts only a verified
external principal, returns an internal identity record, and never consumes email.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from drip.core.identifiers import new_uuid7
from drip.identity.contracts import ExternalPrincipal, InternalUserId

IdentityStatus = Literal["active", "disabled", "deletion_pending"]
_MAX_REGISTRATION_ATTEMPTS = 3


class IdentityPersistenceFailed(RuntimeError):
    """Fixed, credential-free failure for an identity storage operation."""

    def __init__(self) -> None:
        super().__init__("Identity storage could not be completed safely.")


class IdentityOutcomeUnknown(IdentityPersistenceFailed):
    """A commit may have succeeded; callers must not report or retry creation."""

    def __init__(self) -> None:
        RuntimeError.__init__(self, "Identity storage outcome could not be confirmed.")


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    user_id: InternalUserId
    status: IdentityStatus
    created_at: datetime
    updated_at: datetime


_LOOKUP = text(
    "SELECT id, status, created_at, updated_at "
    "FROM drip_identity.lookup_identity(:provider, :issuer, :subject)"
)
_REGISTER = text(
    "SELECT id, status, created_at, updated_at "
    "FROM drip_identity.register_identity(:candidate_user_id, :provider, :issuer, :subject)"
)


def _parameters(principal: ExternalPrincipal) -> dict[str, object]:
    if not isinstance(principal, ExternalPrincipal):
        raise TypeError("Identity resolution requires a verified external principal.")
    identity = principal.identity
    return {
        "provider": identity.provider.value,
        "issuer": identity.issuer,
        "subject": identity.subject,
    }


def _record(row: object) -> IdentityRecord:
    if not isinstance(row, Mapping):
        raise IdentityPersistenceFailed() from None
    try:
        user_id = row["id"]
        status = row["status"]
        created_at = row["created_at"]
        updated_at = row["updated_at"]
    except (KeyError, TypeError):
        raise IdentityPersistenceFailed() from None
    if (
        not isinstance(user_id, UUID)
        or user_id.version != 7
        or status not in ("active", "disabled", "deletion_pending")
        or not isinstance(created_at, datetime)
        or not isinstance(updated_at, datetime)
        or created_at.tzinfo is None
        or updated_at.tzinfo is None
    ):
        raise IdentityPersistenceFailed()
    return IdentityRecord(
        user_id=InternalUserId(user_id),
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )


async def _lookup(
    session: AsyncSession, parameters: dict[str, object]
) -> IdentityRecord | None:
    result = await session.execute(_LOOKUP, parameters)
    row = result.mappings().one_or_none()
    return None if row is None else _record(row)


async def lookup_identity(
    session_factory: async_sessionmaker[AsyncSession], principal: ExternalPrincipal
) -> IdentityRecord | None:
    """Perform an exact verified `(issuer, subject)` lookup; never use email."""
    parameters = _parameters(principal)
    try:
        async with session_factory() as session:
            return await _lookup(session, parameters)
    except IdentityPersistenceFailed:
        raise
    except Exception:
        raise IdentityPersistenceFailed() from None


def _sqlstate_is_unique_conflict(error: IntegrityError) -> bool:
    original = error.orig
    code = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    cause = getattr(original, "__cause__", None)
    if code is None and cause is not None:
        code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    return code == "23505"


async def _lookup_after_write(
    session_factory: async_sessionmaker[AsyncSession], parameters: dict[str, object]
) -> IdentityRecord | None:
    try:
        async with session_factory() as session:
            async with session.begin():
                return await _lookup(session, parameters)
    except Exception:
        return None


async def resolve_or_register_identity(
    session_factory: async_sessionmaker[AsyncSession], principal: ExternalPrincipal
) -> IdentityRecord:
    """Resolve an existing pair or atomically register one disabled user.

    A unique conflict gets a fresh exact lookup and at most three candidate IDs.
    Other database errors are reconciled read-only once; absence after an uncertain
    write is not retried because commit may have an unknown outcome.
    """
    parameters = _parameters(principal)
    for attempt in range(_MAX_REGISTRATION_ATTEMPTS):
        candidate_user_id = new_uuid7()
        if candidate_user_id.version != 7:
            raise IdentityPersistenceFailed()
        try:
            async with session_factory() as session:
                async with session.begin():
                    existing = await _lookup(session, parameters)
                    if existing is not None:
                        return existing
                    result = await session.execute(
                        _REGISTER,
                        {**parameters, "candidate_user_id": candidate_user_id},
                    )
                    row = result.mappings().one()
                    registered = _record(row)
                return registered
        except IntegrityError as error:
            if not _sqlstate_is_unique_conflict(error):
                raise IdentityPersistenceFailed() from None
            winner = await _lookup_after_write(session_factory, parameters)
            if winner is not None:
                return winner
            if attempt + 1 < _MAX_REGISTRATION_ATTEMPTS:
                continue
            raise IdentityPersistenceFailed() from None
        except IdentityPersistenceFailed:
            raise
        except Exception:
            confirmed = await _lookup_after_write(session_factory, parameters)
            if confirmed is not None:
                return confirmed
            raise IdentityOutcomeUnknown() from None
    raise IdentityPersistenceFailed()
