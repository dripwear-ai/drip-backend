"""Read-only preconditions and target attestation for migration checkpoint T."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import Connection, text

T_REVISION_ID = "0003_portable_identity_ckpt"
PARENT_REVISION_ID = "0002_require_pg18_uuidv7"
BASELINE_REVISION_ID = "0001_initial_baseline"
PG17_TEST_USER = "drip_pg17_test"
PG17_TEST_PORT = 55436
PG17_ADMIN_DATABASE = "drip_pg17_admin"
PG17_TARGET_DATABASE = "drip_pg17_target"
PG17_BOOTSTRAP_URL_PATTERN = (
    r"^postgresql\+asyncpg://drip_pg17_test:[0-9a-f]{64}"
    r"@127\.0\.0\.1:55436/drip_pg17_target$"
)


class CheckpointPreconditionError(RuntimeError):
    """Raised with fixed diagnostics when a database is unsafe for checkpointing."""


def _rows(connection: Connection, statement: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(statement), params).mappings()]


def _extension_manifest(connection: Connection) -> list[dict[str, Any]]:
    extensions = _rows(
        connection,
        """
        SELECT e.extname, e.extversion, n.nspname AS schema_name, r.rolname AS owner_name
        FROM pg_catalog.pg_extension AS e
        JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
        JOIN pg_catalog.pg_roles AS r ON r.oid = e.extowner
        WHERE e.extname = 'pgcrypto'
        """,
    )
    if len(extensions) > 1:
        raise CheckpointPreconditionError("Checkpoint preflight rejected extension state.")
    if extensions and extensions[0]["schema_name"] != "public":
        raise CheckpointPreconditionError("Checkpoint preflight rejected extension namespace.")

    if not extensions:
        return []

    extension_oid = _rows(
        connection,
        "SELECT oid FROM pg_catalog.pg_extension WHERE extname = 'pgcrypto'",
    )[0]["oid"]
    objects = _rows(
        connection,
        """
        SELECT pg_catalog.pg_describe_object(d.classid, d.objid, d.objsubid) AS object_name
        FROM pg_catalog.pg_depend AS d
        WHERE d.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
          AND d.refobjid = CAST(:extension_oid AS oid)
          AND d.deptype = 'e'
        ORDER BY object_name
        """,
        extension_oid=extension_oid,
    )
    return [{**extensions[0], "objects": [item["object_name"] for item in objects]}]


def _unaccounted_objects(connection: Connection) -> list[dict[str, Any]]:
    """Return user objects except the baseline revision table and pgcrypto members."""
    unsupported_schemas = _rows(
        connection,
        """
        SELECT nspname AS schema_name
        FROM pg_catalog.pg_namespace
        WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'public')
          AND nspname NOT LIKE 'pg_toast%'
          AND nspname NOT LIKE 'pg_temp_%'
        ORDER BY nspname
        """,
    )
    objects = _rows(
        connection,
        """
        SELECT n.nspname AS schema_name, c.relkind::text AS object_type,
               c.relname AS object_name
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
          AND c.relname <> 'alembic_version'
          AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_depend AS d
              WHERE d.classid = 'pg_catalog.pg_class'::pg_catalog.regclass
                AND d.objid = c.oid AND d.objsubid = 0
                AND d.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
                AND d.deptype = 'e'
          )
        UNION ALL
        SELECT n.nspname, 'function', p.proname
        FROM pg_catalog.pg_proc AS p
        JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_depend AS d
              WHERE d.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
                AND d.objid = p.oid AND d.objsubid = 0
                AND d.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
                AND d.deptype = 'e'
          )
        UNION ALL
        SELECT n.nspname, 'type', t.typname
        FROM pg_catalog.pg_type AS t
        JOIN pg_catalog.pg_namespace AS n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' AND t.typtype IN ('d', 'e', 'r')
          AND NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_depend AS d
              WHERE d.classid = 'pg_catalog.pg_type'::pg_catalog.regclass
                AND d.objid = t.oid AND d.objsubid = 0
                AND d.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
                AND d.deptype = 'e'
          )
        ORDER BY 1, 2, 3
        """,
    )
    return [
        *({"schema_name": row["schema_name"], "object_type": "schema"} for row in unsupported_schemas),
        *objects,
    ]


def database_attestation(
    connection: Connection, *, include_system_identifier: bool = False
) -> dict[str, Any]:
    system_identifier = (
        ", (SELECT system_identifier::text FROM pg_catalog.pg_control_system()) "
        "AS system_identifier"
        if include_system_identifier
        else ""
    )
    rows = _rows(
        connection,
        f"""
        SELECT current_database() AS database_name, current_user AS role_name,
               current_setting('server_version_num')::integer AS server_version_num,
               current_setting('server_encoding') AS server_encoding,
               current_setting('block_size')::integer AS block_size,
               inet_server_addr()::text AS server_address
               {system_identifier}
        """,
    )
    if len(rows) != 1:
        raise CheckpointPreconditionError("Checkpoint target attestation failed.")
    attestation = rows[0]
    if attestation["server_version_num"] // 10000 < 17:
        raise CheckpointPreconditionError("Checkpoint target PostgreSQL version is unsupported.")
    if attestation["server_encoding"] != "UTF8":
        raise CheckpointPreconditionError("Checkpoint target encoding is unsupported.")
    return attestation


def revision_tables(connection: Connection) -> list[dict[str, Any]]:
    return _rows(
        connection,
        """
        SELECT n.nspname AS schema_name, c.relkind::text AS relation_kind
        FROM pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        WHERE c.relname = 'alembic_version'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
        ORDER BY n.nspname
        """,
    )


def checkpoint_manifest(connection: Connection, expected_revision: str) -> dict[str, Any]:
    revision_relations = revision_tables(connection)
    if revision_relations != [{"schema_name": "public", "relation_kind": "r"}]:
        raise CheckpointPreconditionError("Checkpoint revision-table location is unexpected.")
    revisions = _rows(
        connection,
        "SELECT version_num FROM public.alembic_version ORDER BY version_num",
    )
    if revisions != [{"version_num": expected_revision}]:
        raise CheckpointPreconditionError("Checkpoint revision state is unexpected.")

    extensions = _extension_manifest(connection)
    if len(extensions) != 1:
        raise CheckpointPreconditionError("Checkpoint preflight rejected extension state.")
    if _rows(
        connection,
        "SELECT 1 AS present FROM pg_catalog.pg_namespace WHERE nspname = 'drip_identity'",
    ):
        raise CheckpointPreconditionError("Checkpoint preflight found identity objects.")
    objects = _unaccounted_objects(connection)
    if objects:
        raise CheckpointPreconditionError("Checkpoint preflight found unaccounted application objects.")

    attestation = database_attestation(connection)
    return {
        "database_name": attestation["database_name"],
        "server_major": attestation["server_version_num"] // 10000,
        "server_encoding": attestation["server_encoding"],
        "block_size": attestation["block_size"],
        "revision_table": "public.alembic_version",
        "revision": expected_revision,
        "pgcrypto": extensions,
        "drip_identity_schema_present": False,
        "unaccounted_application_objects": objects,
    }


def manifest_sha256(manifest: dict[str, Any]) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_checkpoint(connection: Connection, expected_revision: str) -> dict[str, Any]:
    """Verify the historical parent and portable state before T is recorded."""
    database_attestation(connection)
    return checkpoint_manifest(connection, expected_revision)


def assert_pg17_bootstrap_baseline(connection: Connection) -> dict[str, Any]:
    """Require a fresh, allowlisted PG17 database before any bootstrap writes."""
    attestation = database_attestation(connection, include_system_identifier=True)
    if attestation["server_version_num"] // 10000 != 17:
        raise CheckpointPreconditionError("PG17 bootstrap requires PostgreSQL 17.x.")
    if attestation["database_name"] != PG17_TARGET_DATABASE:
        raise CheckpointPreconditionError("PG17 bootstrap database identity is unexpected.")
    if attestation["role_name"] != PG17_TEST_USER:
        raise CheckpointPreconditionError("PG17 bootstrap role identity is unexpected.")

    if revision_tables(connection):
        raise CheckpointPreconditionError("PG17 bootstrap found an existing revision table.")
    if _rows(
        connection,
        "SELECT 1 AS present FROM pg_catalog.pg_namespace WHERE nspname = 'drip_identity'",
    ):
        raise CheckpointPreconditionError("PG17 bootstrap found identity objects.")
    objects = _unaccounted_objects(connection)
    if objects:
        raise CheckpointPreconditionError("PG17 bootstrap found unaccounted application objects.")

    extensions = _extension_manifest(connection)
    return {
        "database_name": attestation["database_name"],
        "role_name": attestation["role_name"],
        "server_major": 17,
        "server_version_num": attestation["server_version_num"],
        "server_encoding": attestation["server_encoding"],
        "block_size": attestation["block_size"],
        "system_identifier": attestation["system_identifier"],
        "extensions_before": extensions,
        "unaccounted_application_objects": objects,
        "alembic_revision_tables": [],
    }


def verify_0001_effects(
    connection: Connection,
    before_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Verify revision 0001 and distinguish a newly created extension from a retained one."""
    after = verify_checkpoint(connection, "0001_initial_baseline")
    before_extensions = before_manifest["extensions_before"]
    after_extensions = after["pgcrypto"]
    if len(after_extensions) != 1:
        raise CheckpointPreconditionError("PG17 bootstrap could not verify pgcrypto state.")
    if before_extensions and before_extensions != after_extensions:
        raise CheckpointPreconditionError("PG17 bootstrap detected a changed extension state.")
    if not before_extensions and not after_extensions[0]["objects"]:
        raise CheckpointPreconditionError("PG17 bootstrap could not verify extension objects.")
    provenance = "retained_existing" if before_extensions else "created_by_0001"
    return {"manifest": after, "extension_provenance": provenance}
