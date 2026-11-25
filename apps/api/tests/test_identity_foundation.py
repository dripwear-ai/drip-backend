import dataclasses
import json
import sys
from uuid import RFC_4122, UUID

import pytest
from drip.core.identifiers import new_uuid7
from drip.identity.config import Auth0VerifierConfig
from drip.identity.contracts import (
    AuthenticationContext,
    AuthenticationProvider,
    AuthorizationContext,
    ExternalIdentity,
    ExternalPrincipal,
    InternalUserId,
)


def test_uuid7_version_variant_uniqueness_and_serialization():
    values = [new_uuid7() for _ in range(2048)]
    assert len(set(values)) == 2048
    for value in values:
        assert isinstance(value, UUID)
        assert value.version == 7
        assert value.version != 4
        assert value.variant == RFC_4122
        assert (value.int >> 76) & 15 == 7
        assert (value.int >> 62) & 3 == 2
        assert UUID(json.loads(json.dumps(str(value)))) == value


def test_uuid7_uses_native_supported_runtime():
    from drip.core import identifiers

    assert sys.version_info[:2] == (3, 14)
    assert identifiers.uuid7.__module__ == "uuid"


def test_internal_and_external_ids_are_distinct():
    internal = InternalUserId(new_uuid7())
    external = ExternalIdentity(
        AuthenticationProvider.AUTH0, "https://tenant.invalid/", "auth0|Case"
    )
    assert internal != external
    assert external.subject == "auth0|Case"
    assert AuthorizationContext(internal).permissions == frozenset()
    with pytest.raises(TypeError):
        InternalUserId(external.subject)
    with pytest.raises(TypeError):
        AuthorizationContext(external)
    with pytest.raises(TypeError):
        ExternalPrincipal(None, None)
    assert "email" not in {item.name for item in dataclasses.fields(ExternalIdentity)}


def test_contracts_preserve_subject_without_normalizing_or_promoting_roles():
    identity = ExternalIdentity(
        AuthenticationProvider.AUTH0, "https://tenant.invalid/", " Case|ID "
    )
    context = AuthenticationContext(("api",), 200, 100, None)
    principal = ExternalPrincipal(identity, context)
    assert principal.identity.subject == " Case|ID "
    assert not hasattr(principal, "user_id")
    assert not hasattr(principal, "permissions")
    assert "Case" not in repr(principal)
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.subject = "changed"


@pytest.mark.parametrize(
    "subject", [None, "", "   ", 1], ids=["missing", "empty", "blank", "numeric"]
)
def test_external_subject_cannot_be_absent(subject):
    with pytest.raises(ValueError, match="^Invalid external subject.$"):
        ExternalIdentity(AuthenticationProvider.AUTH0, "https://tenant.invalid/", subject)


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "http://tenant.invalid/"},
        {"issuer": "https://tenant.invalid"},
        {"issuer": "https://tenant.invalid/path/"},
        {"issuer": "https://tenant.invalid/?q=1"},
        {"issuer": "https://tenant.invalid/#fragment"},
        {"issuer": "https://user@tenant.invalid/"},
        {"issuer": "https://127.0.0.1/"},
        {"issuer": "https://tenant.invalid:443/"},
        {"issuer": " https://tenant.invalid/"},
        {"issuer": "https://tenant%2einvalid/"},
        {"issuer": None},
        {"audience": ""},
        {"audience": "api\nvalue"},
        {"algorithms": ("HS256",)},
        {"algorithms": ("none",)},
        {"algorithms": ()},
        {"leeway_seconds": -1},
        {"leeway_seconds": 61},
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"jwks_ttl_seconds": 0},
        {"jwks_ttl_seconds": 3601},
        {"refresh_cooldown_seconds": 0},
        {"jwks_ttl_seconds": 30, "refresh_cooldown_seconds": 60},
    ],
    ids=[
        "http",
        "slash",
        "path",
        "query",
        "fragment",
        "userinfo",
        "ip",
        "port",
        "space",
        "encoded",
        "missing",
        "audience-empty",
        "audience-control",
        "symmetric",
        "unsigned",
        "no-algorithm",
        "negative-leeway",
        "excess-leeway",
        "timeout-zero",
        "timeout-bool",
        "ttl-zero",
        "ttl-excess",
        "cooldown-zero",
        "cooldown-exceeds-ttl",
    ],
)
def test_invalid_configuration_is_redacted(changes):
    options = {"issuer": "https://tenant.invalid/", "audience": "drip-api", **changes}
    with pytest.raises(ValueError) as failure:
        Auth0VerifierConfig(**options)
    assert str(failure.value) == "Invalid authentication verifier configuration."


def test_configuration_is_explicit_and_independent_of_environment(monkeypatch):
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH0_ISSUER", "untrusted")
    config = Auth0VerifierConfig("https://tenant.invalid/", "drip-api")
    assert config.jwks_url == "https://tenant.invalid/.well-known/jwks.json"
    assert config.algorithms == ("RS256",)
    assert config.leeway_seconds == 0
