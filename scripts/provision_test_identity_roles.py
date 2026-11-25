"""Explicit, disposable-only bootstrap for the DRIP identity database roles.

This module provisions roles only. Alembic must be invoked separately using
``drip_identity_migrator`` after role provisioning has been verified.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

PG17_TEST = ("127.0.0.1", 55436, "drip_pg17_target", "drip_pg17_test", 17)
PG18_TEST = ("127.0.0.1", 55435, "drip_gate_b_test", "drip_test", 18)
_ROLE_LOCK_ID = 6_897_410_231_113_118
_LOGIN_SECRET = re.compile(r"[0-9a-f]{64}\Z")
_ROLE_NAMES = (
    "drip_identity_owner",
    "drip_identity_executor",
    "drip_identity_migrator",
    "drip_identity_runtime",
)


class RoleBootstrapError(ValueError):
    """Fixed, secret-safe rejection for a test role bootstrap."""


@dataclass(frozen=True)
class RoleBootstrapResult:
    state: str
    server_major: int
    database: str


def validate_target(raw_url: object) -> tuple[URL, int]:
    """Accept only the exact disposable PG17/PG18 endpoints used by the repo."""
    if not isinstance(raw_url, str) or "?" in raw_url or "#" in raw_url:
        raise RoleBootstrapError("Disposable role bootstrap target is invalid.")
    try:
        url = make_url(raw_url)
    except Exception:  # noqa: BLE001 - parser failures must become fixed redacted errors
        raise RoleBootstrapError("Disposable role bootstrap target is invalid.") from None
    for host, port, database, username, major in (PG17_TEST, PG18_TEST):
        if (
            url.drivername == "postgresql+asyncpg"
            and url.host == host
            and url.port == port
            and url.database == database
            and url.username == username
            and bool(url.password)
            and not url.query
            and url.render_as_string(hide_password=False) == raw_url
        ):
            return url, major
    raise RoleBootstrapError("Disposable role bootstrap target is invalid.")


def _validate_login_secrets(migrator_password: object, runtime_password: object) -> None:
    if not isinstance(migrator_password, str) or not _LOGIN_SECRET.fullmatch(migrator_password):
        raise RoleBootstrapError("Disposable role bootstrap credentials are invalid.")
    if not isinstance(runtime_password, str) or not _LOGIN_SECRET.fullmatch(runtime_password):
        raise RoleBootstrapError("Disposable role bootstrap credentials are invalid.")
    if migrator_password == runtime_password:
        raise RoleBootstrapError("Disposable role bootstrap credentials are invalid.")


async def provision_test_roles(
    raw_url: object,
    *,
    migrator_password: object,
    runtime_password: object,
) -> RoleBootstrapResult:
    """Provision all four roles atomically on an attested ephemeral test DB.

    The allowlist is checked before creating an engine. The designated Compose
    initialization role is used only for this role-only phase, never for DDL
    migrations. Existing complete role state is a verified no-op; partial or
    drifted state fails without attempting repair.
    """
    url, expected_major = validate_target(raw_url)
    _validate_login_secrets(migrator_password, runtime_password)
    try:
        engine = create_async_engine(url, poolclass=NullPool, echo=False)
    except Exception as exc:  # noqa: BLE001 - database/driver details may contain secrets
        raise RoleBootstrapError(
            f"Disposable role bootstrap failed safely ({type(exc).__name__})."
        ) from None
    try:
        async with engine.begin() as connection:
            attestation = (
                await connection.execute(
                    text(
                        """SELECT current_database() AS database_name,
                                  session_user AS session_role,
                                  current_user AS current_role,
                                  current_setting('server_version_num')::integer AS version_num,
                                  current_setting('server_encoding') AS encoding,
                                  r.rolsuper
                           FROM pg_catalog.pg_roles AS r
                           WHERE r.rolname = session_user"""
                    )
                )
            ).mappings().one_or_none()
            if (
                attestation is None
                or attestation["database_name"] != url.database
                or attestation["session_role"] != url.username
                or attestation["current_role"] != url.username
                or attestation["version_num"] // 10000 != expected_major
                or attestation["encoding"] != "UTF8"
                or not attestation["rolsuper"]
            ):
                raise RoleBootstrapError("Disposable role bootstrap target attestation failed.")

            await connection.execute(text("SELECT pg_catalog.pg_advisory_xact_lock(:key)"), {"key": _ROLE_LOCK_ID})
            existing = (
                await connection.execute(
                    text("SELECT rolname FROM pg_catalog.pg_roles WHERE rolname = ANY(:names)"),
                    {"names": list(_ROLE_NAMES)},
                )
            ).scalars().all()
            if not existing:
                await _create_roles(connection, migrator_password, runtime_password)
                await _grant_database_access(connection, url.database)
                state = "created"
            elif set(existing) == set(_ROLE_NAMES):
                state = "verified_noop"
            else:
                raise RoleBootstrapError("Disposable identity role state is partial or unexpected.")

            await _verify_roles(connection, url.database)
            return RoleBootstrapResult(state, expected_major, url.database)
    except RoleBootstrapError:
        raise
    except Exception as exc:  # noqa: BLE001 - database/driver details may contain secrets
        # Never expose SQL, bound values, URLs, or credentials from driver errors.
        raise RoleBootstrapError(
            f"Disposable role bootstrap failed safely ({type(exc).__name__})."
        ) from None
    finally:
        await engine.dispose()


async def _create_roles(connection, migrator_password: str, runtime_password: str) -> None:
    await connection.exec_driver_sql(
        "CREATE ROLE drip_identity_owner NOLOGIN NOSUPERUSER NOCREATEDB "
        "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
    )
    await connection.exec_driver_sql(
        "CREATE ROLE drip_identity_executor NOLOGIN NOSUPERUSER NOCREATEDB "
        "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
    )
    for role, password in (
        ("drip_identity_migrator", migrator_password),
        ("drip_identity_runtime", runtime_password),
    ):
        # Only fixed role identifiers and strictly validated lowercase hex
        # passwords are interpolated; no environment string is used as SQL.
        await connection.exec_driver_sql(
            f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            f"NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{password}'"
        )
    await connection.exec_driver_sql(
        "GRANT drip_identity_owner TO drip_identity_migrator "
        "WITH SET TRUE, INHERIT FALSE"
    )
    await connection.exec_driver_sql(
        "GRANT drip_identity_executor TO drip_identity_migrator "
        "WITH ADMIN TRUE, SET FALSE, INHERIT FALSE"
    )


async def _grant_database_access(connection, database: str) -> None:
    # Database names are restricted by validate_target to two fixed literals.
    await connection.exec_driver_sql(
        f'GRANT CONNECT, CREATE ON DATABASE "{database}" TO drip_identity_migrator'
    )
    await connection.exec_driver_sql(
        f'GRANT CONNECT ON DATABASE "{database}" TO drip_identity_runtime'
    )


async def authorize_test_migrator_checkpoint(
    raw_url: object,
) -> None:
    """Grant only the DML needed to advance the attested test Alembic table.

    This is a separate test-only preparation phase after reaching checkpoint T;
    it never runs Alembic and never grants runtime access to the version table.
    """
    url, expected_major = validate_target(raw_url)
    try:
        engine = create_async_engine(url, poolclass=NullPool, echo=False)
    except Exception as exc:  # noqa: BLE001 - database/driver details may contain secrets
        raise RoleBootstrapError(
            f"Disposable checkpoint grant failed safely ({type(exc).__name__})."
        ) from None
    try:
        async with engine.begin() as connection:
            info = (
                await connection.execute(
                    text(
                        """SELECT current_database(), session_user, current_user,
                                  current_setting('server_version_num')::integer,
                                  current_setting('server_encoding'), r.rolsuper
                           FROM pg_catalog.pg_roles AS r WHERE r.rolname=session_user"""
                    )
                )
            ).one_or_none()
            if (
                info is None
                or info[0] != url.database
                or info[1] != url.username
                or info[2] != url.username
                or info[3] // 10000 != expected_major
                or info[4] != "UTF8"
                or not info[5]
            ):
                raise RoleBootstrapError("Disposable checkpoint grant target attestation failed.")
            await _verify_checkpoint_table(connection, url.username)
            await connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.alembic_version "
                "TO drip_identity_migrator"
            )
            await _verify_checkpoint_grants(connection)
    except RoleBootstrapError:
        raise
    except Exception as exc:  # noqa: BLE001 - database/driver details may contain secrets
        raise RoleBootstrapError(
            f"Disposable checkpoint grant failed safely ({type(exc).__name__})."
        ) from None
    finally:
        await engine.dispose()


async def _verify_checkpoint_table(connection, expected_owner: str) -> None:
    relations = (
        await connection.execute(
            text(
                """SELECT n.nspname, c.relkind::text AS relkind, owner.rolname AS owner
                   FROM pg_catalog.pg_class AS c
                   JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                   JOIN pg_catalog.pg_roles AS owner ON owner.oid = c.relowner
                   WHERE c.relname = 'alembic_version' AND c.relkind IN ('r','p','v','m','f')
                   ORDER BY n.nspname"""
            )
        )
    ).mappings().all()
    relations = [dict(row) for row in relations]
    expected = (
        len(relations) == 1
        and str(relations[0]["nspname"]) == "public"
        and str(relations[0]["relkind"]) == "r"
        and str(relations[0]["owner"]) == expected_owner
    )
    if not expected:
        observed = ",".join(
            f"{row['nspname']}/{row['relkind']}/{row['owner']}" for row in relations
        ) or "none"
        raise RoleBootstrapError(
            f"Disposable Alembic checkpoint table state is unexpected ({observed})."
        )
    columns = (
        await connection.execute(
            text(
                """SELECT column_name, data_type, character_maximum_length, is_nullable
                   FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'alembic_version'
                   ORDER BY ordinal_position"""
            )
        )
    ).mappings().all()
    columns = [dict(row) for row in columns]
    if columns != [
        {
            "column_name": "version_num",
            "data_type": "character varying",
            "character_maximum_length": 32,
            "is_nullable": "NO",
        }
    ]:
        raise RoleBootstrapError("Disposable Alembic checkpoint table shape is unexpected.")
    primary_key = await connection.scalar(
        text(
            """SELECT count(*) = 1
               FROM pg_catalog.pg_index AS i
               JOIN pg_catalog.pg_class AS c ON c.oid = i.indrelid
               JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
               WHERE n.nspname='public' AND c.relname='alembic_version' AND i.indisprimary
                 AND i.indnatts=1"""
        )
    )
    revision = await connection.scalar(text("SELECT version_num FROM public.alembic_version"))
    if not primary_key or revision != "0003_portable_identity_ckpt":
        raise RoleBootstrapError("Disposable Alembic checkpoint revision is unexpected.")


async def _verify_checkpoint_grants(connection) -> None:
    revision_acl = (
        await connection.execute(
            text(
                """SELECT has_table_privilege('drip_identity_migrator', 'public.alembic_version', 'SELECT') AS migrator_select,
                          has_table_privilege('drip_identity_migrator', 'public.alembic_version', 'INSERT') AS migrator_insert,
                          has_table_privilege('drip_identity_migrator', 'public.alembic_version', 'UPDATE') AS migrator_update,
                          has_table_privilege('drip_identity_migrator', 'public.alembic_version', 'DELETE') AS migrator_delete,
                          has_table_privilege('drip_identity_runtime', 'public.alembic_version', 'SELECT') AS runtime_select,
                          has_table_privilege('drip_identity_runtime', 'public.alembic_version', 'INSERT') AS runtime_insert,
                          has_table_privilege('drip_identity_runtime', 'public.alembic_version', 'UPDATE') AS runtime_update,
                          has_table_privilege('drip_identity_runtime', 'public.alembic_version', 'DELETE') AS runtime_delete"""
            )
        )
    ).mappings().one()
    if any(not revision_acl[f"migrator_{privilege}"] for privilege in ("select", "insert", "update", "delete")) or any(
        revision_acl[f"runtime_{privilege}"]
        for privilege in ("select", "insert", "update", "delete")
    ):
        raise RoleBootstrapError("Disposable Alembic checkpoint grants are unexpected.")


async def _verify_roles(connection, database: str) -> None:
    role_rows = (
        await connection.execute(
            text(
                """SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                          rolinherit, rolreplication, rolbypassrls
                   FROM pg_catalog.pg_roles WHERE rolname = ANY(:names)"""
            ),
            {"names": list(_ROLE_NAMES)},
        )
    ).mappings().all()
    _verify_role_attributes(role_rows)

    memberships = (
        await connection.execute(
            text(
                """SELECT parent.rolname AS parent, member.rolname AS member,
                          m.admin_option, m.set_option, m.inherit_option
                   FROM pg_catalog.pg_auth_members AS m
                   JOIN pg_catalog.pg_roles AS parent ON parent.oid = m.roleid
                   JOIN pg_catalog.pg_roles AS member ON member.oid = m.member
                   WHERE parent.rolname = ANY(:names) OR member.rolname = ANY(:names)"""
            ),
            {"names": list(_ROLE_NAMES)},
        )
    ).mappings().all()
    _verify_memberships(memberships)

    db_acl = (
        await connection.execute(
            text(
                """SELECT has_database_privilege('drip_identity_migrator', :db, 'CONNECT') AS migrator_connect,
                          has_database_privilege('drip_identity_migrator', :db, 'CREATE') AS migrator_create,
                          has_database_privilege('drip_identity_runtime', :db, 'CONNECT') AS runtime_connect,
                          has_database_privilege('drip_identity_runtime', :db, 'CREATE') AS runtime_create"""
            ),
            {"db": database},
        )
    ).mappings().one()
    if not db_acl["migrator_connect"] or not db_acl["migrator_create"] or not db_acl["runtime_connect"] or db_acl["runtime_create"]:
        raise RoleBootstrapError("Disposable identity database grants are unexpected.")
    platform_memberships = (
        await connection.execute(
            text(
                """SELECT pg_catalog.pg_has_role(r.rolname, 'drip_identity_owner', 'MEMBER') AS owner_member,
                          pg_catalog.pg_has_role(r.rolname, 'drip_identity_executor', 'MEMBER') AS executor_member
                   FROM pg_catalog.pg_roles AS r
                   WHERE r.rolname IN ('anon', 'authenticated', 'service_role')"""
            )
        )
    ).all()
    if any(row[0] or row[1] for row in platform_memberships):
        raise RoleBootstrapError("Disposable platform-role membership boundary is unsafe.")

    identity_schema_exists = await connection.scalar(
        text("SELECT pg_catalog.to_regnamespace('drip_identity') IS NOT NULL")
    )
    if identity_schema_exists:
        protected = (
            await connection.execute(
                text(
                    """SELECT has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'SELECT')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'INSERT')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'UPDATE')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'DELETE')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'SELECT')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'INSERT')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'UPDATE')
                                  OR has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'DELETE')"""
                )
            )
        ).scalar_one()
        if protected:
            raise RoleBootstrapError("Disposable runtime identity-table privileges are unsafe.")


def _verify_role_attributes(role_rows) -> None:
    if len(role_rows) != 4:
        raise RoleBootstrapError("Disposable identity role attributes are incomplete.")
    by_name = {row["rolname"]: row for row in role_rows}
    for name in ("drip_identity_owner", "drip_identity_executor"):
        row = by_name[name]
        if any(row[key] for key in ("rolcanlogin", "rolsuper", "rolcreatedb", "rolcreaterole", "rolinherit", "rolreplication", "rolbypassrls")):
            raise RoleBootstrapError("Disposable identity role attributes are unexpected.")
    for name in ("drip_identity_migrator", "drip_identity_runtime"):
        row = by_name[name]
        if (
            not row["rolcanlogin"]
            or any(row[key] for key in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolinherit", "rolreplication", "rolbypassrls"))
        ):
            raise RoleBootstrapError("Disposable identity role attributes are unexpected.")

def _verify_memberships(memberships) -> None:
    actual = {
        (row["member"], row["parent"], row["admin_option"], row["set_option"], row["inherit_option"])
        for row in memberships
    }
    expected = {
        ("drip_identity_migrator", "drip_identity_owner", False, True, False),
        ("drip_identity_migrator", "drip_identity_executor", True, False, False),
    }
    if actual != expected:
        raise RoleBootstrapError("Disposable identity role membership is unexpected.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("pg17", "pg18"), required=True)
    args = parser.parse_args()
    if os.environ.get("ENVIRONMENT") != "test" or os.environ.get("DRIP_TEST_ROLE_BOOTSTRAP") != "1":
        print("Disposable role bootstrap requires explicit test-mode authorization.", file=sys.stderr)
        return 2
    if args.target == "pg17":
        admin_raw = os.environ.get("DRIP_PG17_TEST_ADMIN_URL")
        try:
            admin_url = make_url(admin_raw) if admin_raw else None
        except Exception:  # noqa: BLE001 - CLI must not echo malformed target data
            admin_url = None
        if (
            admin_url is None
            or admin_url.drivername != "postgresql+asyncpg"
            or admin_url.host != "127.0.0.1"
            or admin_url.port != 55436
            or admin_url.database != "drip_pg17_admin"
            or admin_url.username != "drip_pg17_test"
            or not admin_url.password
            or admin_url.query
            or admin_url.render_as_string(hide_password=False) != admin_raw
        ):
            print("Disposable role bootstrap target is invalid.", file=sys.stderr)
            return 1
        target_raw = admin_url.set(database=PG17_TEST[2]).render_as_string(hide_password=False)
    else:
        target_raw = os.environ.get("DRIP_TEST_DATABASE_URL")
    migrator_password = os.environ.get("DRIP_TEST_IDENTITY_MIGRATOR_PASSWORD")
    runtime_password = os.environ.get("DRIP_TEST_IDENTITY_RUNTIME_PASSWORD")
    try:
        result = asyncio.run(
            provision_test_roles(
                target_raw,
                migrator_password=migrator_password,
                runtime_password=runtime_password,
            )
        )
    except RoleBootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Disposable identity roles {result.state}; target PostgreSQL {result.server_major} attested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
