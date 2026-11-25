"""Auth0 access-token proof only. No user lookup, linking, sessions or grants."""

import json
import re
import time
from collections.abc import Callable
from threading import Lock
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from drip.core.errors import DripException
from drip.identity.config import Auth0VerifierConfig
from drip.identity.contracts import (
    AuthenticationContext,
    AuthenticationProvider,
    ExternalIdentity,
    ExternalPrincipal,
)
from drip.identity.jwks_transport import MAX_JWKS_BYTES, fetch_jwks

MAX_TOKEN_BYTES = 16384
_KID = re.compile(r"[\x21-\x7e]{1,128}")


class AuthenticationFailed(DripException):
    def __init__(self) -> None:
        super().__init__(
            "Authentication could not be verified.", code="AUTHENTICATION_FAILED", status_code=401
        )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Ambiguous JSON object.")
        result[key] = value
    return result


def _json_object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("Invalid JSON object.")
    return value


class Auth0TokenVerifier:
    def __init__(
        self,
        config: Auth0VerifierConfig,
        *,
        fetcher: Callable[[str, int], bytes] = fetch_jwks,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._fetcher = fetcher
        self._clock = clock
        self._keys: dict[str, RSAPublicKey] = {}
        self._expires = 0.0
        self._last_attempt = float("-inf")
        self._lock = Lock()
        self._refreshing = False

    @property
    def config(self) -> Auth0VerifierConfig:
        return self._config

    def _load_keys(self) -> dict[str, RSAPublicKey]:
        raw = self._fetcher(self.config.jwks_url, self.config.timeout_seconds)
        if not isinstance(raw, bytes) or len(raw) > MAX_JWKS_BYTES:
            raise ValueError("Invalid signing key response.")
        entries = _json_object(raw).get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
            raise ValueError("Invalid signing key response.")
        keys: dict[str, RSAPublicKey] = {}
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid signing key response.")
            kid = entry.get("kid")
            if not isinstance(kid, str) or not _KID.fullmatch(kid) or kid in seen:
                raise ValueError("Invalid signing key response.")
            seen.add(kid)
            if entry.get("kty") != "RSA" or entry.get("alg", "RS256") != "RS256":
                continue
            if entry.get("use", "sig") != "sig" or entry.get("key_ops", ["verify"]) != ["verify"]:
                continue
            if any(field in entry for field in ("d", "p", "q", "dp", "dq", "qi")):
                raise ValueError("Invalid signing key response.")
            key = jwt.PyJWK.from_dict(entry, algorithm="RS256").key
            if not isinstance(key, RSAPublicKey) or not 2048 <= key.key_size <= 8192:
                raise ValueError("Invalid signing key response.")
            keys[kid] = key
        if not keys:
            raise ValueError("Invalid signing key response.")
        return keys

    def _key(self, kid: str) -> RSAPublicKey:
        with self._lock:
            now = self._clock()
            if now < self._expires and kid in self._keys:
                return self._keys[kid]
            if self._refreshing or now - self._last_attempt < self.config.refresh_cooldown_seconds:
                raise AuthenticationFailed()
            self._refreshing = True
        # No lock or waiter queue across I/O. Fresh known keys remain usable.
        try:
            keys = self._load_keys()
            with self._lock:
                self._keys = keys
                self._expires = now + self.config.jwks_ttl_seconds
                if self._clock() >= self._expires or kid not in keys:
                    raise AuthenticationFailed()
                return keys[kid]
        finally:
            with self._lock:
                # Failure never extends the old snapshot's original expiry.
                self._last_attempt = self._clock()
                self._refreshing = False

    def verify(self, token: str | None) -> ExternalPrincipal:
        """Return external proof, never a DRIP user or application authorization."""
        try:
            if not isinstance(token, str) or not 0 < len(token) <= MAX_TOKEN_BYTES:
                raise AuthenticationFailed()
            if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
                raise AuthenticationFailed()
            header_part, claims_part, _ = token.split(".")
            header = _json_object(jwt.utils.base64url_decode(header_part))
            # Only use unverified fields for rejection/key selection, never for identity.
            _json_object(jwt.utils.base64url_decode(claims_part))
            kid = header.get("kid")
            if (
                header.get("alg") not in self.config.algorithms
                or not isinstance(kid, str)
                or not _KID.fullmatch(kid)
                or any(name in header for name in ("jku", "jwk", "x5u", "crit", "b64"))
                or header.get("typ")
                != ("JWT" if self.config.token_profile == "auth0" else "at+jwt")
            ):
                raise AuthenticationFailed()
            claims = jwt.decode(
                token,
                self._key(kid),
                algorithms=list(self.config.algorithms),
                issuer=self.config.issuer,
                audience=self.config.audience,
                leeway=self.config.leeway_seconds,
                options={
                    "require": ["exp", "iss", "aud", "sub"]
                    + (
                        ["iat", "client_id", "jti"]
                        if self.config.token_profile == "rfc9068"
                        else []
                    )
                },
            )
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject.strip() or len(subject) > 1024:
                raise AuthenticationFailed()
            if claims["iss"] != self.config.issuer:
                raise AuthenticationFailed()
            for name in ("exp", "iat", "nbf"):
                if name in claims and (type(claims[name]) is not int or claims[name] < 0):
                    raise AuthenticationFailed()
            for name in ("azp", "client_id", "jti"):
                if name in claims and (
                    not isinstance(claims[name], str) or not claims[name].strip()
                ):
                    raise AuthenticationFailed()
            audiences = claims["aud"]
            if isinstance(audiences, str):
                audiences = [audiences]
            if not isinstance(audiences, list) or any(
                not isinstance(value, str) or not value for value in audiences
            ):
                raise AuthenticationFailed()
            return ExternalPrincipal(
                identity=ExternalIdentity(
                    AuthenticationProvider.AUTH0, self.config.issuer, subject
                ),
                authentication=AuthenticationContext(
                    tuple(audiences), claims["exp"], claims.get("iat"), claims.get("nbf")
                ),
            )
        except Exception:
            # Never propagate provider/crypto/network exceptions, inputs or URL values.
            raise AuthenticationFailed() from None
