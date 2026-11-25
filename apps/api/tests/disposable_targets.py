"""Test-only preflight. Import no application settings, clients or drivers here."""

from collections.abc import Mapping, MutableMapping

# Exact canonical URLs from infra/compose.test.yml and docs/setup.md. These are
# disposable test credentials, never deployment credentials. Do not normalize:
# URL parsers can strip controls or interpret encoded/query/authority overrides.
POSTGRES_URL = (
    "postgresql+asyncpg://drip_test:disposable_test_only@127.0.0.1:55435/drip_gate_b_test"
)
REDIS_URL = "redis://127.0.0.1:56381/0"


class UnsafeTestTarget(ValueError):
    """A fixed, credential-free configuration error."""


def validate_disposable_targets(environment: Mapping[str, str]) -> tuple[str, str]:
    """Require both exact targets, including the documented authority components."""
    if environment.get("DRIP_TEST_DATABASE_URL") != POSTGRES_URL:
        raise UnsafeTestTarget(
            "DRIP_TEST_DATABASE_URL must be the documented disposable PostgreSQL URL."
        )
    if environment.get("DRIP_TEST_REDIS_URL") != REDIS_URL:
        raise UnsafeTestTarget(
            "DRIP_TEST_REDIS_URL must be the documented disposable Redis URL."
        )
    return POSTGRES_URL, REDIS_URL


def prepare_test_environment(environment: MutableMapping[str, str], markexpr: str) -> None:
    """Run before collection imports can construct application infrastructure.

    Only the repository's explicit non-live marker exclusion may omit both URLs.
    Any other selection (including no exclusion) requires explicit live targets.
    Supplied empty/partial/invalid test variables are never silently ignored.
    """
    for name in environment:
        if name.upper() in {"DRIP_TEST_DATABASE_URL", "DRIP_TEST_REDIS_URL"} and name != name.upper():
            raise UnsafeTestTarget(
                "Test-target variables must use only the documented uppercase names."
            )
    supplied = any(
        name in environment for name in ("DRIP_TEST_DATABASE_URL", "DRIP_TEST_REDIS_URL")
    )
    if markexpr != "not integration" or supplied:
        database_url, redis_url = validate_disposable_targets(environment)
    else:
        # Non-live collection still imports the app. Never inherit a user DB URL
        # or root dotenv, and do not manufacture explicit live-test authorization.
        database_url, redis_url = POSTGRES_URL, REDIS_URL
    # Settings is case-insensitive, including on case-sensitive operating systems.
    # Remove duplicate spellings so inherited aliases cannot win during parsing.
    controlled = {"ENVIRONMENT", "DRIP_ENV_FILE", "DATABASE_URL", "REDIS_URL"}
    for name in list(environment):
        if name.upper() in controlled:
            del environment[name]
    # Commit environment changes only after BOTH targets have passed validation.
    environment.update(
        ENVIRONMENT="test",
        DRIP_ENV_FILE="",
        DATABASE_URL=database_url,
        REDIS_URL=redis_url,
    )
