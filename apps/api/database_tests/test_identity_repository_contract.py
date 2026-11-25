from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from drip.core.identifiers import new_uuid7
from drip.identity.contracts import (
    AuthenticationContext,
    AuthenticationProvider,
    ExternalIdentity,
    ExternalPrincipal,
)
from drip.identity.repository import (
    _LOOKUP,
    _REGISTER,
    IdentityPersistenceFailed,
    _parameters,
    _record,
    _sqlstate_is_unique_conflict,
)


def _principal() -> ExternalPrincipal:
    return ExternalPrincipal(
        identity=ExternalIdentity(
            AuthenticationProvider.AUTH0,
            "https://drip.example/",
            "auth0|opaque-subject",
        ),
        authentication=AuthenticationContext(
            audiences=("https://api.example/",),
            expires_at=2_000_000_000,
            issued_at=None,
            not_before=None,
        ),
    )


def test_identity_parameters_preserve_issuer_and_subject_without_email():
    values = _parameters(_principal())

    assert values == {
        "provider": "auth0",
        "issuer": "https://drip.example/",
        "subject": "auth0|opaque-subject",
    }
    assert "email" not in values


def test_identity_record_accepts_only_uuidv7_and_known_lifecycle_values():
    now = datetime.now(UTC)
    record = _record(
        {
            "id": new_uuid7(),
            "status": "disabled",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert record.user_id.value.version == 7
    assert record.status == "disabled"

    with pytest.raises(IdentityPersistenceFailed):
        _record(
            {
                "id": uuid4(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        )


def test_repository_sql_calls_only_exact_private_identity_functions():
    lookup = str(_LOOKUP).lower()
    register = str(_REGISTER).lower()

    assert "drip_identity.lookup_identity(:provider, :issuer, :subject)" in lookup
    assert "drip_identity.register_identity(:candidate_user_id, :provider, :issuer, :subject)" in register
    assert "email" not in lookup + register
    assert "user_id" not in lookup


def test_repository_recognizes_only_postgresql_unique_violation_for_retry():
    class UniqueViolation(Exception):
        sqlstate = "23505"

    class OtherViolation(Exception):
        sqlstate = "23514"

    assert _sqlstate_is_unique_conflict(IntegrityError("insert", {}, UniqueViolation()))
    assert not _sqlstate_is_unique_conflict(IntegrityError("insert", {}, OtherViolation()))
