import json
import socket
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from drip.core.errors import setup_error_handlers
from drip.identity.config import Auth0VerifierConfig
from drip.identity.dependencies import external_principal_dependency
from drip.identity.verifier import (
    MAX_JWKS_BYTES,
    Auth0TokenVerifier,
    AuthenticationFailed,
)
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

ISSUER = "https://tenant.invalid/"
AUDIENCE = "drip-test-api"
NOW = 1800000000


@pytest.fixture(autouse=True)
def offline_and_fixed_time(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected network attempt")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(NOW, UTC)

    monkeypatch.setattr(jwt.api_jwt, "datetime", FixedDatetime)


@pytest.fixture(scope="module")
def signing_keys():
    # Ephemeral test-only keys; never persisted or used by runtime application code.
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))


def jwks(key, kid="first", **changes):
    entry = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    entry.update({"kid": kid, "alg": "RS256", "use": "sig", **changes})
    return json.dumps({"keys": [entry]}).encode()


def token(key, *, changes=None, remove=(), headers=None):
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "auth0|Case-sensitive",
        "exp": NOW + 300,
        "iat": NOW - 1,
        "nbf": NOW - 1,
    }
    claims.update(changes or {})
    for name in remove:
        claims.pop(name, None)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "first", **(headers or {})})


def verifier(body, **kwargs):
    fetcher = Mock(return_value=body)
    instance = Auth0TokenVerifier(Auth0VerifierConfig(ISSUER, AUDIENCE), fetcher=fetcher, **kwargs)
    return instance, fetcher


def test_valid_access_token_returns_only_external_proof(signing_keys):
    instance, fetcher = verifier(jwks(signing_keys[0]))
    result = instance.verify(
        token(signing_keys[0], changes={"email": "not-an-identity-key", "roles": ["admin"]})
    )
    assert result.identity.subject == "auth0|Case-sensitive"
    assert result.identity.provider == "auth0"
    assert result.identity.issuer == ISSUER
    assert result.authentication.audiences == (AUDIENCE,)
    assert result.authentication.expires_at == NOW + 300
    assert not hasattr(result, "email")
    assert not hasattr(result, "permissions")
    fetcher.assert_called_once_with(ISSUER + ".well-known/jwks.json", 3)


@pytest.mark.parametrize(
    "changes,remove",
    [
        ({"iss": "https://other.invalid/"}, ()),
        ({"aud": "other-api"}, ()),
        ({"exp": NOW}, ()),
        ({"nbf": NOW + 1}, ()),
        ({"iat": NOW + 1}, ()),
        ({}, ("sub",)),
        ({"sub": ""}, ()),
        ({"sub": " "}, ()),
        ({"sub": 42}, ()),
        ({}, ("exp",)),
        ({}, ("aud",)),
        ({}, ("iss",)),
        ({"exp": str(NOW + 300)}, ()),
        ({"exp": NOW + 300.5}, ()),
        ({"nbf": False}, ()),
        ({"iat": True}, ()),
        ({"aud": [AUDIENCE, 1]}, ()),
    ],
    ids=[
        "issuer",
        "audience",
        "expired",
        "future-nbf",
        "future-iat",
        "missing-sub",
        "empty-sub",
        "blank-sub",
        "numeric-sub",
        "missing-exp",
        "missing-aud",
        "missing-iss",
        "string-exp",
        "float-exp",
        "boolean-nbf",
        "boolean-iat",
        "invalid-audience-list",
    ],
)
def test_invalid_claims_fail_closed(signing_keys, changes, remove):
    instance, _ = verifier(jwks(signing_keys[0]))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0], changes=changes, remove=remove))


def test_audience_list_and_optional_time_claims(signing_keys):
    instance, _ = verifier(jwks(signing_keys[0]))
    result = instance.verify(
        token(signing_keys[0], changes={"aud": [AUDIENCE, "userinfo"]}, remove=("nbf", "iat"))
    )
    assert result.authentication.audiences == (AUDIENCE, "userinfo")
    assert result.authentication.not_before is None


def test_invalid_signature_does_not_trigger_repeated_refresh(signing_keys):
    instance, fetcher = verifier(jwks(signing_keys[0]))
    for _ in range(3):
        with pytest.raises(AuthenticationFailed):
            instance.verify(token(signing_keys[1]))
    assert fetcher.call_count == 1


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"kid": None},
        {"kid": ""},
        {"kid": 1},
        {"kid": "x" * 129},
        {"jku": "https://untrusted.invalid/"},
        {"jwk": {}},
        {"x5u": "https://untrusted.invalid/"},
        {"crit": ["unsupported"]},
        {"typ": "other"},
    ],
    ids=[
        "missing-kid",
        "null-kid",
        "empty-kid",
        "numeric-kid",
        "long-kid",
        "jku",
        "jwk",
        "x5u",
        "crit",
        "type",
    ],
)
def test_invalid_header_does_not_fetch_keys(signing_keys, headers):
    # PyJWT refuses non-string kid while encoding; build an untrusted compact token ourselves.
    header = jwt.utils.base64url_encode(
        json.dumps({"alg": "RS256", "typ": "JWT", **headers}).encode()
    ).decode()
    instance, fetcher = verifier(jwks(signing_keys[0]))
    with pytest.raises(AuthenticationFailed):
        instance.verify(header + ".e30.eA")
    fetcher.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "malformed",
        "a.b.c",
        "a.b",
        "x" * 16385,
        "eyJhbGciOiJub25lIiwia2lkIjoiZmlyc3QifQ.e30.",
    ],
    ids=["missing", "empty", "malformed", "invalid-json", "segments", "oversized", "unsigned"],
)
def test_malformed_or_unsigned_tokens_never_fetch(raw):
    instance, fetcher = verifier(b"{}")
    with pytest.raises(AuthenticationFailed):
        instance.verify(raw)
    fetcher.assert_not_called()


def test_symmetric_algorithm_rejected_before_key_fetch():
    instance, fetcher = verifier(b"{}")
    raw = jwt.encode(
        {"sub": "test"},
        "test-only-key-with-sufficient-length",
        algorithm="HS256",
        headers={"kid": "first"},
    )
    with pytest.raises(AuthenticationFailed):
        instance.verify(raw)
    fetcher.assert_not_called()


@pytest.mark.parametrize("part", ["header", "payload"])
def test_duplicate_json_members_are_rejected_before_fetch(part):
    header = b'{"alg":"RS256","typ":"JWT","kid":"first"}'
    payload = b'{"sub":"one","sub":"two"}'
    if part == "header":
        header = b'{"alg":"RS256","alg":"HS256","typ":"JWT","kid":"first"}'
        payload = b"{}"
    raw = ".".join(jwt.utils.base64url_encode(v).decode() for v in (header, payload, b"signature"))
    instance, fetcher = verifier(b"{}")
    with pytest.raises(AuthenticationFailed):
        instance.verify(raw)
    fetcher.assert_not_called()


def test_unknown_kid_rotation_and_retired_key_removal(signing_keys):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])
    instance.verify(token(signing_keys[0]))
    fetcher.return_value = jwks(signing_keys[1], "second")
    second = token(signing_keys[1], headers={"kid": "second"})
    with pytest.raises(AuthenticationFailed):
        instance.verify(second)  # Refresh cooldown, not a fallback to an arbitrary key.
    clock[0] = 31
    assert instance.verify(second).identity.subject == "auth0|Case-sensitive"
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))
    assert fetcher.call_count == 2


def test_unknown_keys_are_rate_bounded(signing_keys):
    instance, fetcher = verifier(jwks(signing_keys[0]))
    for index in range(10):
        with pytest.raises(AuthenticationFailed):
            instance.verify(token(signing_keys[0], headers={"kid": f"unknown-{index}"}))
    assert fetcher.call_count == 1


def test_cache_expiry_refreshes_even_an_existing_key_id(signing_keys):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])
    assert fetcher.call_count == 0  # Construction does not perform I/O.
    instance.verify(token(signing_keys[0]))
    fetcher.return_value = jwks(signing_keys[1])
    clock[0] = 299
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[1]))
    assert fetcher.call_count == 1
    clock[0] = 300
    instance.verify(token(signing_keys[1]))
    assert fetcher.call_count == 2


def test_explicit_leeway_is_bounded_and_applied(signing_keys):
    instance = Auth0TokenVerifier(
        Auth0VerifierConfig(ISSUER, AUDIENCE, leeway_seconds=5),
        fetcher=Mock(return_value=jwks(signing_keys[0])),
    )
    instance.verify(token(signing_keys[0], changes={"exp": NOW - 4}))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0], changes={"exp": NOW - 5}))


def test_expired_cache_never_falls_back_after_jwks_failure(signing_keys, caplog):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])
    raw = token(signing_keys[0])
    instance.verify(raw)
    clock[0] = 301
    fetcher.side_effect = OSError("synthetic-private-provider-detail")
    with pytest.raises(AuthenticationFailed) as failure:
        instance.verify(raw)
    assert str(failure.value) == "Authentication could not be verified."
    formatted = "".join(traceback.format_exception(failure.value))
    assert "synthetic-private-provider-detail" not in formatted + caplog.text
    assert raw not in formatted + caplog.text
    with pytest.raises(AuthenticationFailed):
        instance.verify(raw)
    assert fetcher.call_count == 2


def test_cold_jwks_unavailable_fails_closed(signing_keys):
    instance, fetcher = verifier(b"{}")
    fetcher.side_effect = TimeoutError("untrusted detail")
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b"{}",
        b'{"keys":[]}',
        b'{"keys":{},"keys":[]}',
        b"x" * (MAX_JWKS_BYTES + 1),
        b'{"keys":[null]}',
    ],
    ids=["json", "array", "missing", "empty", "duplicate", "oversize", "entry"],
)
def test_invalid_jwks_fails_closed(signing_keys, body):
    instance, _ = verifier(body)
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


@pytest.mark.parametrize(
    "changes",
    [
        {"alg": "HS256"},
        {"use": "enc"},
        {"key_ops": ["sign"]},
        {"d": "not-public"},
        {"kty": "oct"},
        {"n": "invalid"},
    ],
    ids=["algorithm", "encryption", "sign-only", "private-material", "symmetric", "modulus"],
)
def test_inappropriate_jwks_key_rejected(signing_keys, changes):
    instance, _ = verifier(jwks(signing_keys[0], **changes))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


def test_duplicate_kid_rejected(signing_keys):
    data = json.loads(jwks(signing_keys[0]))
    data["keys"] *= 2
    instance, _ = verifier(json.dumps(data).encode())
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


def test_small_rsa_key_and_excess_key_count_are_rejected(signing_keys):
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    instance, _ = verifier(jwks(weak))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))
    data = json.loads(jwks(signing_keys[0]))
    data["keys"] *= 33
    instance, _ = verifier(json.dumps(data).encode())
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


def test_concurrent_verification_uses_single_cache_refresh(signing_keys):
    instance, fetcher = verifier(jwks(signing_keys[0]))
    raw = token(signing_keys[0])
    instance.verify(raw)  # Warm cache; concurrent cold callers now fail fast during refresh.
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(instance.verify, [raw] * 12))
    assert len(results) == 12
    assert fetcher.call_count == 1


def test_same_email_never_combines_external_principals(signing_keys):
    instance, _ = verifier(jwks(signing_keys[0]))
    first = instance.verify(
        token(signing_keys[0], changes={"sub": "provider|one", "email": "same"})
    )
    second = instance.verify(
        token(signing_keys[0], changes={"sub": "provider|two", "email": "same"})
    )
    assert first.identity != second.identity


@pytest.mark.parametrize(
    "headers",
    [
        [],
        [("authorization", "Basic value")],
        [("authorization", "Bearer")],
        [("authorization", "Bearer malformed")],
        [("authorization", "Bearer one"), ("authorization", "Bearer two")],
    ],
    ids=["guest", "wrong-scheme", "missing-token", "bad-token", "duplicate-headers"],
)
async def test_fastapi_dependency_rejects_unauthenticated_request(headers, caplog):
    instance, _ = verifier(b"{}")
    app = FastAPI()
    setup_error_handlers(app)
    dependency = external_principal_dependency(instance)
    proof_dependency = Depends(dependency)

    @app.get("/proof")
    def proof(principal=proof_dependency):
        pytest.fail("Unauthenticated request reached protected test handler")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/proof", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_FAILED"
    assert response.json()["details"] == []
    assert "malformed" not in response.text + caplog.text


async def test_fastapi_dependency_returns_verified_external_identity_only(signing_keys):
    instance, _ = verifier(jwks(signing_keys[0]))
    app = FastAPI()
    proof_dependency = Depends(external_principal_dependency(instance))

    @app.get("/proof")
    def proof(principal=proof_dependency):
        return {"provider": principal.identity.provider, "subject": principal.identity.subject}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/proof", headers={"Authorization": "Bearer " + token(signing_keys[0])}
        )
    assert response.json() == {"provider": "auth0", "subject": "auth0|Case-sensitive"}
    assert response.status_code == 200


def test_http_fetcher_is_bounded_and_disallows_redirects(monkeypatch):
    from drip.identity import jwks_transport as module

    response = Mock(status=200)
    response.headers = {}
    response.read.return_value = b'{"keys":[]}'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    builder = Mock(return_value=opener)
    monkeypatch.setattr(module, "build_opener", builder)
    assert module._read_jwks(ISSUER + ".well-known/jwks.json", 3) == b'{"keys":[]}'
    response.read.assert_called_once_with(MAX_JWKS_BYTES + 1)
    assert opener.open.call_args.kwargs == {"timeout": 3}
    assert opener.open.call_args.args[0].full_url == ISSUER + ".well-known/jwks.json"
    handlers = builder.call_args.args
    assert handlers[0].proxies == {}
    assert handlers[1]._context.check_hostname is True
    assert handlers[1]._context.verify_mode == module.ssl.CERT_REQUIRED
    assert isinstance(handlers[-1], module._NoRedirect)
    assert handlers[-1].redirect_request(None, None, 302, "", {}, "https://other.invalid/") is None
    response.read.return_value = b"x" * (MAX_JWKS_BYTES + 1)
    with pytest.raises(ValueError):
        module._read_jwks(ISSUER + ".well-known/jwks.json", 3)
    response.status = 503
    with pytest.raises(ValueError):
        module._read_jwks(ISSUER + ".well-known/jwks.json", 3)


def test_unknown_key_flood_preserves_fresh_keys_but_never_extends_expiry(signing_keys):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])
    known = token(signing_keys[0])
    instance.verify(known)
    fetcher.side_effect = TimeoutError("synthetic-private-detail")
    clock[0] = 31
    for index in range(100):
        with pytest.raises(AuthenticationFailed):
            instance.verify(token(signing_keys[0], headers={"kid": f"unknown-{index}"}))
    assert fetcher.call_count == 2
    instance.verify(known)
    clock[0] = 299
    instance.verify(known)
    clock[0] = 300
    with pytest.raises(AuthenticationFailed):
        instance.verify(known)
    assert fetcher.call_count == 3
    for instant in (301, 329):
        clock[0] = instant
        with pytest.raises(AuthenticationFailed):
            instance.verify(known)
    assert fetcher.call_count == 3
    clock[0] = 330
    with pytest.raises(AuthenticationFailed):
        instance.verify(known)
    assert fetcher.call_count == 4
    clock[0] = 360
    fetcher.side_effect = None
    instance.verify(known)
    assert fetcher.call_count == 5


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "fresh-snapshot"])
def test_inflight_unknown_key_flood_fails_fast_without_waiting(signing_keys, warm):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])
    known = token(signing_keys[0])
    if warm:
        instance.verify(known)
    clock[0] = 31
    entered, release = Event(), Event()

    def slow_fetch(*args):
        entered.set()
        assert release.wait(5)
        raise TimeoutError("synthetic-private-detail")

    fetcher.side_effect = slow_fetch
    unknown = token(signing_keys[0], headers={"kid": "unknown"})

    def rejected():
        with pytest.raises(AuthenticationFailed):
            instance.verify(unknown)

    with ThreadPoolExecutor(max_workers=8) as pool:
        first = pool.submit(rejected)
        try:
            assert entered.wait(5)
            futures = [pool.submit(rejected) for _ in range(40)]
            for future in futures:
                future.result(timeout=2)
            if warm:
                instance.verify(known)
            else:
                with pytest.raises(AuthenticationFailed):
                    instance.verify(known)
            assert fetcher.call_count == (2 if warm else 1)
        finally:
            release.set()
        first.result(timeout=2)
    clock[0] = 61
    fetcher.side_effect = None
    instance.verify(known)


def test_refresh_cooldown_starts_at_completion_and_slow_fetch_cannot_extend_ttl(signing_keys):
    clock = [0.0]
    instance, fetcher = verifier(jwks(signing_keys[0]), clock=lambda: clock[0])

    def delayed(*args):
        clock[0] = 301
        return jwks(signing_keys[0])

    fetcher.side_effect = delayed
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))
    clock[0] = 330
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))
    assert fetcher.call_count == 1
    clock[0] = 331
    fetcher.side_effect = None
    instance.verify(token(signing_keys[0]))


@pytest.mark.parametrize(
    "typ",
    [None, "at+jwt", "jwt", "ID", ""],
    ids=["missing", "other-profile", "case", "id", "empty"],
)
def test_auth0_profile_requires_exact_jwt_type_before_fetch(signing_keys, typ):
    instance, fetcher = verifier(jwks(signing_keys[0]))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0], headers={"typ": typ}))
    fetcher.assert_not_called()


def test_id_token_audience_is_not_the_api_audience(signing_keys):
    instance, _ = verifier(jwks(signing_keys[0]))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0], changes={"aud": "oauth-client-identifier"}))


@pytest.mark.parametrize(
    "missing",
    [None, "iat", "client_id", "jti"],
    ids=["valid", "missing-iat", "missing-client", "missing-jti"],
)
def test_rfc9068_profile_is_explicit_and_requires_profile_claims(signing_keys, missing):
    instance = Auth0TokenVerifier(
        Auth0VerifierConfig(ISSUER, AUDIENCE, token_profile="rfc9068"),
        fetcher=Mock(return_value=jwks(signing_keys[0])),
    )
    raw = token(
        signing_keys[0],
        changes={"client_id": "test-client", "jti": "test-id"},
        remove=() if missing is None else (missing,),
        headers={"typ": "at+jwt"},
    )
    if missing is None:
        assert instance.verify(raw).identity.subject == "auth0|Case-sensitive"
    else:
        with pytest.raises(AuthenticationFailed):
            instance.verify(raw)
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0]))


@pytest.mark.parametrize("name", ["azp", "client_id", "jti"])
@pytest.mark.parametrize("value", [None, 1, " "], ids=["null", "numeric", "blank"])
def test_present_profile_identifiers_must_be_nonempty_strings(signing_keys, name, value):
    instance, _ = verifier(jwks(signing_keys[0]))
    with pytest.raises(AuthenticationFailed):
        instance.verify(token(signing_keys[0], changes={name: value}))


@pytest.mark.parametrize(
    "value",
    [
        " Bearer a.b.c",
        "Bearer a.b.c ",
        "Bearer\ta.b.c",
        "Bearer a.b.c\r\n",
        "Bearer a.b.c, a.b.c",
        "Bearer " + "x" * 16400,
    ],
    ids=["leading-space", "trailing-space", "tab", "crlf", "combined", "oversize"],
)
def test_malformed_authorization_never_reaches_verifier(value):
    from starlette.requests import Request

    instance = Mock()
    dependency = external_principal_dependency(instance)
    request = Request({"type": "http", "headers": [(b"authorization", value.encode())]})
    with pytest.raises(AuthenticationFailed) as failure:
        dependency(request)
    instance.verify.assert_not_called()
    assert str(failure.value) == "Authentication could not be verified."


@pytest.mark.parametrize(
    "profile",
    [None, "JWT", "automatic", ""],
    ids=["null", "header-not-profile", "automatic", "empty"],
)
def test_invalid_profile_configuration_is_redacted(profile):
    with pytest.raises(ValueError, match="^Invalid authentication verifier configuration.$"):
        Auth0VerifierConfig(ISSUER, AUDIENCE, token_profile=profile)
