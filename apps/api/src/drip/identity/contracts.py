"""Internal contracts, not client-supplied credentials or public API DTOs."""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class AuthenticationProvider(StrEnum):
    AUTH0 = "auth0"


@dataclass(frozen=True, slots=True)
class InternalUserId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("Internal user ID requires a UUID.")


@dataclass(frozen=True, slots=True, repr=False)
class ExternalIdentity:
    provider: AuthenticationProvider
    issuer: str
    subject: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider, AuthenticationProvider):
            raise TypeError("Invalid authentication provider.")
        if not isinstance(self.issuer, str) or not self.issuer:
            raise ValueError("Invalid external issuer.")
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("Invalid external subject.")


@dataclass(frozen=True, slots=True, repr=False)
class AuthenticationContext:
    """Verified token facts only; not MFA, a DRIP session, or grant evidence."""

    audiences: tuple[str, ...]
    expires_at: int
    issued_at: int | None
    not_before: int | None


@dataclass(frozen=True, slots=True, repr=False)
class ExternalPrincipal:
    """Trusted verifier output. Python constructors are not a security sandbox."""

    identity: ExternalIdentity
    authentication: AuthenticationContext

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ExternalIdentity) or not isinstance(
            self.authentication, AuthenticationContext
        ):
            raise TypeError("An external principal requires verified identity context.")


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Future authoritative service output; never derived from token roles/email."""

    user_id: InternalUserId
    permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, InternalUserId):
            raise TypeError("Authorization requires an internal user ID.")
        if not isinstance(self.permissions, frozenset) or any(
            not isinstance(item, str) or not item for item in self.permissions
        ):
            raise TypeError("Invalid authorization context.")
