from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import provision_test_identity_roles as bootstrap

MIGRATOR_SECRET = "a" * 64
RUNTIME_SECRET = "b" * 64
PG17_URL = f"postgresql+asyncpg://drip_pg17_test:{MIGRATOR_SECRET}@127.0.0.1:55436/drip_pg17_target"
PG18_URL = "postgresql+asyncpg://drip_test:disposable_test_only@127.0.0.1:55435/drip_gate_b_test"


@pytest.mark.parametrize(
    ("url", "major"),
    [(PG17_URL, 17), (PG18_URL, 18)],
    ids=["documented-pg17-target", "documented-pg18-target"],
)
def test_accepts_only_the_documented_disposable_urls(url: str, major: int) -> None:
    parsed, actual_major = bootstrap.validate_target(url)

    assert actual_major == major
    assert parsed.host == "127.0.0.1"


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "not a url",
        PG17_URL.replace("postgresql+asyncpg", "postgresql"),
        PG17_URL.replace("127.0.0.1", "localhost"),
        PG17_URL.replace(":55436", ":55435"),
        PG17_URL.replace("drip_pg17_target", "postgres"),
        PG17_URL + "?ssl=false",
        PG17_URL + "#fragment",
        PG17_URL.replace("drip_pg17_test:", "drip_pg17_test@"),
        PG17_URL.replace("127.0.0.1", "127.0.0.1.evil"),
        PG18_URL.replace("drip_gate_b_test", "other_db"),
    ],
    ids=["missing", "empty", "malformed", "scheme", "host", "port", "database", "query", "fragment", "userinfo", "host-suffix", "pg18-database"],
)
def test_rejects_noncanonical_or_non_disposable_urls_before_engine_creation(url, monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Rejected target created an engine.")

    monkeypatch.setattr(bootstrap, "create_async_engine", forbidden)

    with pytest.raises(bootstrap.RoleBootstrapError) as error:
        # URL validation occurs before any engine creation.
        import asyncio

        asyncio.run(
            bootstrap.provision_test_roles(
                url,
                migrator_password=MIGRATOR_SECRET,
                runtime_password=RUNTIME_SECRET,
            )
        )

    assert str(error.value) == "Disposable role bootstrap target is invalid."
    assert MIGRATOR_SECRET not in str(error.value)
    assert "postgresql" not in str(error.value)


@pytest.mark.parametrize("password", [None, "", "short", "g" * 64, "a" * 64])
def test_rejects_invalid_or_reused_login_secrets(password) -> None:
    with pytest.raises(bootstrap.RoleBootstrapError):
        bootstrap._validate_login_secrets(password, password)


def test_validates_exact_role_attributes_and_refuses_privilege_drift() -> None:
    attributes = []
    for name, can_login in (
        ("drip_identity_owner", False),
        ("drip_identity_executor", False),
        ("drip_identity_migrator", True),
        ("drip_identity_runtime", True),
    ):
        attributes.append(
            {
                "rolname": name,
                "rolcanlogin": can_login,
                "rolsuper": False,
                "rolcreatedb": False,
                "rolcreaterole": False,
                "rolinherit": False,
                "rolreplication": False,
                "rolbypassrls": False,
            }
        )

    bootstrap._verify_role_attributes(attributes)
    attributes[-1]["rolbypassrls"] = True
    with pytest.raises(bootstrap.RoleBootstrapError, match="attributes are unexpected"):
        bootstrap._verify_role_attributes(attributes)


def test_validates_exact_membership_options_and_rejects_runtime_membership() -> None:
    memberships = [
        {
            "member": "drip_identity_migrator",
            "parent": "drip_identity_owner",
            "admin_option": False,
            "set_option": True,
            "inherit_option": False,
        },
        {
            "member": "drip_identity_migrator",
            "parent": "drip_identity_executor",
            "admin_option": True,
            "set_option": False,
            "inherit_option": False,
        },
    ]

    bootstrap._verify_memberships(memberships)
    memberships.append(
        {
            "member": "drip_identity_runtime",
            "parent": "drip_identity_executor",
            "admin_option": False,
            "set_option": True,
            "inherit_option": False,
        }
    )
    with pytest.raises(bootstrap.RoleBootstrapError, match="membership is unexpected"):
        bootstrap._verify_memberships(memberships)


def test_cli_requires_explicit_test_mode_before_database_access(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DRIP_TEST_ROLE_BOOTSTRAP", raising=False)

    monkeypatch.setattr(
        "sys.argv", ["provision_test_identity_roles.py", "--target", "pg18"]
    )
    assert bootstrap.main() == 2
    assert capsys.readouterr().err == "Disposable role bootstrap requires explicit test-mode authorization.\n"
