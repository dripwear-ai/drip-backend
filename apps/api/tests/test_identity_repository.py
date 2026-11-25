from __future__ import annotations

from datetime import UTC, datetime

import pytest
from drip.core.identifiers import new_uuid7
from drip.identity.contracts import (
    AuthenticationContext,
    AuthenticationProvider,
    ExternalIdentity,
    ExternalPrincipal,
)
from drip.identity.repository import (
    IdentityOutcomeUnknown,
    lookup_identity,
    resolve_or_register_identity,
)
from sqlalchemy.exc import IntegrityError

_NOW = datetime.now(UTC)


def _principal() -> ExternalPrincipal:
    return ExternalPrincipal(
        identity=ExternalIdentity(
            AuthenticationProvider.AUTH0,
            "https://drip.example/",
            "auth0|synthetic-subject",
        ),
        authentication=AuthenticationContext(
            audiences=("https://api.example/",),
            expires_at=2_000_000_000,
            issued_at=None,
            not_before=None,
        ),
    )


class _Result:
    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def one_or_none(self):
        return self.value

    def one(self):
        if self.value is None:
            raise AssertionError("Expected a returned identity record.")
        return self.value


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Session:
    def __init__(self, store, *, register_error=None):
        self.store = store
        self.register_error = register_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def begin(self):
        return _Transaction()

    async def execute(self, statement, params):
        sql = str(statement)
        if "lookup_identity" in sql:
            assert set(params) == {"provider", "issuer", "subject"}
            assert params["provider"] == "auth0"
            return _Result(self.store.get((params["issuer"], params["subject"])))
        if "register_identity" in sql:
            assert "email" not in params
            if self.register_error is not None:
                error = self.register_error
                self.register_error = None
                raise error
            row = {
                "id": params["candidate_user_id"],
                "status": "disabled",
                "created_at": _NOW,
                "updated_at": _NOW,
            }
            self.store[(params["issuer"], params["subject"])] = row
            return _Result(row)
        raise AssertionError("Unexpected identity database function.")


def _factory(store, *, register_error=None):
    calls = 0

    def create_session():
        nonlocal calls
        calls += 1
        error = register_error if calls == 1 else None
        return _Session(store, register_error=error)

    return create_session


@pytest.mark.asyncio
async def test_identity_registration_uses_exact_verified_pair_and_disabled_status():
    store = {}
    record = await resolve_or_register_identity(_factory(store), _principal())

    assert record.user_id.value.version == 7
    assert record.status == "disabled"
    assert set(store) == {("https://drip.example/", "auth0|synthetic-subject")}


@pytest.mark.asyncio
async def test_existing_identity_is_resolved_without_another_registration():
    user_id = new_uuid7()
    store = {
        ("https://drip.example/", "auth0|synthetic-subject"): {
            "id": user_id,
            "status": "disabled",
            "created_at": _NOW,
            "updated_at": _NOW,
        }
    }

    record = await resolve_or_register_identity(_factory(store), _principal())

    assert record.user_id.value == user_id
    assert record.status == "disabled"
    assert len(store) == 1


@pytest.mark.asyncio
async def test_lookup_returns_internal_identity_without_email_keying():
    user_id = new_uuid7()
    store = {
        ("https://drip.example/", "auth0|synthetic-subject"): {
            "id": user_id,
            "status": "active",
            "created_at": _NOW,
            "updated_at": _NOW,
        }
    }

    result = await lookup_identity(_factory(store), _principal())

    assert result is not None
    assert result.user_id.value == user_id
    assert result.status == "active"


@pytest.mark.asyncio
async def test_unique_conflict_reconciles_with_fresh_exact_lookup():
    winner_id = new_uuid7()
    winner = {
        "id": winner_id,
        "status": "disabled",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    store = {}

    class UniqueViolation(Exception):
        sqlstate = "23505"

    def create_session():
        if store:
            return _Session(store)
        session = _Session(store, register_error=IntegrityError("statement", {}, UniqueViolation()))
        original_execute = session.execute

        async def execute(statement, params):
            if "register_identity" in str(statement):
                store[(params["issuer"], params["subject"])] = winner
            return await original_execute(statement, params)

        session.execute = execute
        return session

    record = await resolve_or_register_identity(create_session, _principal())

    assert record.user_id.value == winner_id
    assert record.status == "disabled"


@pytest.mark.asyncio
async def test_unknown_write_outcome_is_not_retried_or_reported_as_success():
    attempts = 0

    class _UnknownWriteSession(_Session):
        async def execute(self, statement, params):
            nonlocal attempts
            if "lookup_identity" in str(statement):
                return _Result(None)
            attempts += 1
            raise RuntimeError("synthetic transport failure")

    def create_session():
        return _UnknownWriteSession({})

    with pytest.raises(IdentityOutcomeUnknown):
        await resolve_or_register_identity(create_session, _principal())

    assert attempts == 1
