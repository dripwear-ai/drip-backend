"""Explicit verifier configuration; no dotenv, global settings or network side effects."""

import re
from dataclasses import dataclass
from typing import Literal

_ISSUER = re.compile(r"https://(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}/")


@dataclass(frozen=True, slots=True, repr=False)
class Auth0VerifierConfig:
    issuer: str
    audience: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 0
    jwks_ttl_seconds: int = 300
    refresh_cooldown_seconds: int = 30
    timeout_seconds: int = 3
    token_profile: Literal["auth0", "rfc9068"] = "auth0"

    def __post_init__(self) -> None:
        valid = (
            isinstance(self.issuer, str)
            and len(self.issuer) <= 260
            and _ISSUER.fullmatch(self.issuer) is not None
            and isinstance(self.audience, str)
            and 0 < len(self.audience) <= 512
            and all(33 <= ord(char) <= 126 for char in self.audience)
            and self.algorithms == ("RS256",)
            and self.token_profile in ("auth0", "rfc9068")
        )
        bounds = (
            (self.leeway_seconds, 0, 60),
            (self.jwks_ttl_seconds, 30, 3600),
            (self.refresh_cooldown_seconds, 1, 60),
            (self.timeout_seconds, 1, 10),
        )
        if not valid or any(
            type(value) is not int or not low <= value <= high for value, low, high in bounds
        ):
            raise ValueError("Invalid authentication verifier configuration.")
        if self.refresh_cooldown_seconds > self.jwks_ttl_seconds:
            raise ValueError("Invalid authentication verifier configuration.")

    @property
    def jwks_url(self) -> str:
        return self.issuer + ".well-known/jwks.json"
