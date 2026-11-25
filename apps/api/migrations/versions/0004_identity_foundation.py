"""Create the private, disabled-first DRIP identity capability boundary.

Revision ID: 0004_identity_foundation
Revises: 0003_portable_identity_ckpt
"""

from collections.abc import Sequence

from alembic import context, op
from sqlalchemy import text

revision: str = "0004_identity_foundation"
down_revision: str | None = "0003_portable_identity_ckpt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MIGRATION_LOCK_ID = 6_897_410_231_113_117

_PREFLIGHT = r"""
DO $$
DECLARE
    role_name text;
BEGIN
    IF current_setting('server_encoding') <> 'UTF8' THEN
        RAISE EXCEPTION 'DRIP identity foundation requires UTF8';
    END IF;
    IF current_setting('server_version_num')::integer < 170000 THEN
        RAISE EXCEPTION 'DRIP identity foundation requires PostgreSQL 17 or later';
    END IF;
    IF current_user <> 'drip_identity_migrator' THEN
        RAISE EXCEPTION 'DRIP identity migration role is not active';
    END IF;
    IF to_regnamespace('drip_identity') IS NOT NULL THEN
        RAISE EXCEPTION 'DRIP identity schema already exists; manual inventory is required';
    END IF;
    IF to_regclass('public.alembic_version') IS NULL OR
       (SELECT array_agg(version_num ORDER BY version_num)
          FROM public.alembic_version) IS DISTINCT FROM ARRAY['0003_portable_identity_ckpt']::varchar[] THEN
        RAISE EXCEPTION 'DRIP identity migration parent revision is not exact';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_owner'
                   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) OR
       NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_executor'
                   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) OR
       NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_migrator'
                   AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) OR
       NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_runtime'
                   AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls) THEN
        RAISE EXCEPTION 'DRIP identity role attributes do not match the approved boundary';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_default_acl
        WHERE defaclrole IN (
            'drip_identity_owner'::pg_catalog.regrole,
            'drip_identity_executor'::pg_catalog.regrole
        ) AND defaclnamespace = 0
    ) THEN
        RAISE EXCEPTION 'DRIP identity role has unreviewed global default privileges';
    END IF;
    IF NOT has_database_privilege(current_user, current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'DRIP identity migrator lacks required schema creation capability';
    END IF;
    IF NOT has_database_privilege('drip_identity_runtime', current_database(), 'CONNECT') THEN
        RAISE EXCEPTION 'DRIP identity runtime lacks approved database connectivity';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS m
        WHERE m.member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user)
          AND m.roleid = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_owner')
          AND m.set_option AND NOT m.inherit_option
    ) THEN
        RAISE EXCEPTION 'DRIP identity migrator lacks its audited owner SET membership';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS m
        WHERE m.member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user)
          AND m.roleid = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_executor')
          AND m.admin_option AND NOT m.set_option AND NOT m.inherit_option
    ) THEN
        RAISE EXCEPTION 'DRIP identity migrator lacks its restricted executor grant authority';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members AS m
        WHERE m.member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_owner')
          AND m.roleid = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = 'drip_identity_executor')
    ) OR pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_owner', 'MEMBER')
      OR pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_executor', 'MEMBER') THEN
        RAISE EXCEPTION 'DRIP identity owner/executor membership boundary is unsafe';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) AND
           (pg_catalog.pg_has_role(role_name::name, 'drip_identity_owner', 'MEMBER') OR
            pg_catalog.pg_has_role(role_name::name, 'drip_identity_executor', 'MEMBER')) THEN
            RAISE EXCEPTION 'DRIP identity platform-role membership boundary is unsafe';
        END IF;
    END LOOP;
END
$$;
"""

_UPGRADE_DDL = (
    "CREATE SCHEMA drip_identity AUTHORIZATION drip_identity_owner",
    "SET LOCAL ROLE drip_identity_owner",
    r"""CREATE TABLE drip_identity.users (
    id uuid NOT NULL,
    status text DEFAULT 'disabled' NOT NULL,
    created_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT ck_identity_users_status
        CHECK (status IN ('active', 'disabled', 'deletion_pending')),
    CONSTRAINT ck_identity_users_uuid_v7
        CHECK ((pg_catalog.get_byte(pg_catalog.uuid_send(id), 6) >> 4) = 7),
    CONSTRAINT ck_identity_users_uuid_rfc_variant
        CHECK ((pg_catalog.get_byte(pg_catalog.uuid_send(id), 8) & 192) = 128),
    CONSTRAINT ck_identity_users_updated_at_order CHECK (updated_at >= created_at)
);""",
    r"""CREATE TABLE drip_identity.external_identities (
    issuer text COLLATE "C" NOT NULL,
    subject text COLLATE "C" NOT NULL,
    user_id uuid NOT NULL,
    provider text NOT NULL,
    created_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_identity_external_identity PRIMARY KEY (issuer, subject),
    CONSTRAINT uq_identity_external_identity_user_id UNIQUE (user_id),
    CONSTRAINT fk_identity_external_identity_user_id
        FOREIGN KEY (user_id) REFERENCES drip_identity.users(id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ck_identity_external_issuer_format
        CHECK (pg_catalog.octet_length(issuer) BETWEEN 1 AND 260 AND
               issuer ~ '^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}/$'),
    CONSTRAINT ck_identity_external_subject_bytes
        CHECK (pg_catalog.octet_length(subject) BETWEEN 1 AND 1024 AND
               subject ~ '[^[:space:]]'),
    CONSTRAINT ck_identity_external_provider CHECK (provider = 'auth0'),
    CONSTRAINT ck_identity_external_timestamps_equal CHECK (updated_at = created_at)
);""",
    r"""CREATE FUNCTION drip_identity.enforce_user_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'DRIP identity user immutable fields cannot be changed';
    END IF;
    NEW.updated_at := GREATEST(OLD.updated_at, pg_catalog.statement_timestamp());
    RETURN NEW;
END
$$""",
    r"""CREATE FUNCTION drip_identity.reject_external_identity_update()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    RAISE EXCEPTION 'DRIP external identity associations are immutable';
END
$$""",
    "REVOKE ALL ON FUNCTION drip_identity.enforce_user_update() FROM PUBLIC",
    "REVOKE ALL ON FUNCTION drip_identity.reject_external_identity_update() FROM PUBLIC",
    """CREATE TRIGGER trg_identity_users_immutable_timestamps
BEFORE UPDATE ON drip_identity.users
FOR EACH ROW EXECUTE FUNCTION drip_identity.enforce_user_update()""",
    """CREATE TRIGGER trg_identity_external_identity_immutable
BEFORE UPDATE ON drip_identity.external_identities
FOR EACH ROW EXECUTE FUNCTION drip_identity.reject_external_identity_update()""",
    "ALTER TABLE drip_identity.users ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE drip_identity.users FORCE ROW LEVEL SECURITY",
    "ALTER TABLE drip_identity.external_identities ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE drip_identity.external_identities FORCE ROW LEVEL SECURITY",
    """CREATE POLICY identity_executor_users_select ON drip_identity.users
    FOR SELECT TO drip_identity_executor USING (true)""",
    """CREATE POLICY identity_executor_users_insert ON drip_identity.users
    FOR INSERT TO drip_identity_executor WITH CHECK (true)""",
    """CREATE POLICY identity_executor_external_select ON drip_identity.external_identities
    FOR SELECT TO drip_identity_executor USING (true)""",
    """CREATE POLICY identity_executor_external_insert ON drip_identity.external_identities
    FOR INSERT TO drip_identity_executor WITH CHECK (true)""",
    "REVOKE ALL ON TABLE drip_identity.users, drip_identity.external_identities FROM PUBLIC",
    "REVOKE ALL ON TABLE drip_identity.users, drip_identity.external_identities FROM drip_identity_runtime",
    r"""DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON TABLE drip_identity.users, drip_identity.external_identities FROM %I',
                role_name
            );
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION drip_identity.enforce_user_update() FROM %I', role_name
            );
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION drip_identity.reject_external_identity_update() FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$""",
    "GRANT USAGE ON SCHEMA drip_identity TO drip_identity_executor",
    """GRANT SELECT, INSERT ON drip_identity.users, drip_identity.external_identities
    TO drip_identity_executor""",
    "GRANT CREATE ON SCHEMA drip_identity TO drip_identity_executor",
    r"""CREATE FUNCTION drip_identity.lookup_identity(
    p_provider text, p_issuer text, p_subject text
)
RETURNS TABLE (id uuid, status text, created_at timestamptz, updated_at timestamptz)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF p_provider IS DISTINCT FROM 'auth0' OR p_issuer IS NULL OR
       pg_catalog.octet_length(p_issuer) NOT BETWEEN 1 AND 260 OR
       p_issuer !~ '^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}/$' OR
       p_subject IS NULL OR pg_catalog.octet_length(p_subject) NOT BETWEEN 1 AND 1024 OR
       p_subject !~ '[^[:space:]]' THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Invalid identity lookup input';
    END IF;
    RETURN QUERY
        SELECT u.id, u.status, u.created_at, u.updated_at
        FROM drip_identity.external_identities AS e
        JOIN drip_identity.users AS u ON u.id = e.user_id
        WHERE e.provider = p_provider AND e.issuer = p_issuer AND e.subject = p_subject;
END
$$""",
    r"""CREATE FUNCTION drip_identity.register_identity(
    p_candidate_user_id uuid, p_provider text, p_issuer text, p_subject text
)
RETURNS TABLE (id uuid, status text, created_at timestamptz, updated_at timestamptz)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF p_candidate_user_id IS NULL OR p_provider IS DISTINCT FROM 'auth0' OR
       p_issuer IS NULL OR pg_catalog.octet_length(p_issuer) NOT BETWEEN 1 AND 260 OR
       p_issuer !~ '^https://([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}/$' OR
       p_subject IS NULL OR pg_catalog.octet_length(p_subject) NOT BETWEEN 1 AND 1024 OR
       p_subject !~ '[^[:space:]]' THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Invalid identity registration input';
    END IF;
    INSERT INTO drip_identity.users AS u (id, status)
        VALUES (p_candidate_user_id, 'disabled')
        RETURNING u.id, u.status, u.created_at, u.updated_at
        INTO id, status, created_at, updated_at;
    BEGIN
        INSERT INTO drip_identity.external_identities
            (issuer, subject, user_id, provider, created_at, updated_at)
        VALUES
            (p_issuer, p_subject, p_candidate_user_id, p_provider,
             pg_catalog.transaction_timestamp(), pg_catalog.transaction_timestamp());
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION USING ERRCODE = '23505', MESSAGE = 'Identity mapping conflict';
    END;
    RETURN NEXT;
END
$$""",
    r"""CREATE FUNCTION drip_identity.identity_tables_empty_for_migration()
RETURNS TABLE (users_empty boolean, external_identities_empty boolean)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT NOT EXISTS (SELECT 1 FROM drip_identity.users),
           NOT EXISTS (SELECT 1 FROM drip_identity.external_identities)
$$""",
    "RESET ROLE",
    "GRANT drip_identity_executor TO drip_identity_owner WITH SET TRUE, INHERIT FALSE",
    "SET LOCAL ROLE drip_identity_owner",
    "ALTER FUNCTION drip_identity.lookup_identity(text, text, text) OWNER TO drip_identity_executor",
    "ALTER FUNCTION drip_identity.register_identity(uuid, text, text, text) OWNER TO drip_identity_executor",
    "ALTER FUNCTION drip_identity.identity_tables_empty_for_migration() OWNER TO drip_identity_executor",
    "SET LOCAL ROLE drip_identity_executor",
    "REVOKE ALL ON FUNCTION drip_identity.lookup_identity(text, text, text) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION drip_identity.register_identity(uuid, text, text, text) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION drip_identity.identity_tables_empty_for_migration() FROM PUBLIC",
    "REVOKE ALL ON FUNCTION drip_identity.lookup_identity(text, text, text) FROM drip_identity_runtime, drip_identity_migrator",
    "REVOKE ALL ON FUNCTION drip_identity.register_identity(uuid, text, text, text) FROM drip_identity_runtime, drip_identity_migrator",
    "REVOKE ALL ON FUNCTION drip_identity.identity_tables_empty_for_migration() FROM drip_identity_runtime, drip_identity_migrator",
    r"""DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION drip_identity.lookup_identity(text, text, text) FROM %I',
                role_name
            );
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION drip_identity.register_identity(uuid, text, text, text) FROM %I',
                role_name
            );
            EXECUTE pg_catalog.format(
                'REVOKE ALL ON FUNCTION drip_identity.identity_tables_empty_for_migration() FROM %I',
                role_name
            );
        END IF;
    END LOOP;
END
$$""",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA drip_identity REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION drip_identity.lookup_identity(text, text, text) TO drip_identity_runtime",
    "GRANT EXECUTE ON FUNCTION drip_identity.register_identity(uuid, text, text, text) TO drip_identity_runtime",
    "GRANT EXECUTE ON FUNCTION drip_identity.identity_tables_empty_for_migration() TO drip_identity_migrator",
    "RESET ROLE",
    "REVOKE drip_identity_executor FROM drip_identity_owner",
    "SET LOCAL ROLE drip_identity_owner",
    "REVOKE CREATE ON SCHEMA drip_identity FROM drip_identity_executor",
    "GRANT USAGE ON SCHEMA drip_identity TO drip_identity_runtime, drip_identity_migrator",
    "RESET ROLE",
    r"""DO $$
BEGIN
    IF pg_catalog.has_schema_privilege('drip_identity_executor', 'drip_identity', 'CREATE') OR
       NOT pg_catalog.has_schema_privilege('drip_identity_executor', 'drip_identity', 'USAGE') OR
       pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_owner', 'MEMBER') OR
       pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_executor', 'MEMBER') OR
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
           WHERE roleid = 'drip_identity_executor'::pg_catalog.regrole
             AND member = 'drip_identity_owner'::pg_catalog.regrole
       ) THEN
        RAISE EXCEPTION 'DRIP identity role cleanup verification failed';
    END IF;
END
$$""",
)

_POSTFLIGHT = r"""
DO $$
DECLARE
    schema_oid oid;
BEGIN
    SELECT oid INTO schema_oid FROM pg_catalog.pg_namespace
    WHERE nspname = 'drip_identity'
      AND nspowner = 'drip_identity_owner'::pg_catalog.regrole;
    IF schema_oid IS NULL OR
       (SELECT array_agg(c.relname ORDER BY c.relname)
        FROM pg_catalog.pg_class AS c
        WHERE c.relnamespace = schema_oid AND c.relkind = 'r') IS DISTINCT FROM
       ARRAY['external_identities', 'users']::name[] OR
       (SELECT count(*) FROM pg_catalog.pg_class AS c
        WHERE c.relnamespace = schema_oid AND c.relkind = 'r') <> 2 OR
       (SELECT count(*) FROM pg_catalog.pg_proc AS p
        WHERE p.pronamespace = schema_oid) <> 5 OR
       (SELECT count(*) FROM pg_catalog.pg_policies AS p
        WHERE p.schemaname = 'drip_identity') <> 4 THEN
        RAISE EXCEPTION 'DRIP identity object manifest verification failed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class AS c
        WHERE c.relnamespace = schema_oid AND c.relkind = 'r'
          AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'DRIP identity forced RLS verification failed';
    END IF;
    IF NOT pg_catalog.has_schema_privilege('drip_identity_executor', 'drip_identity', 'USAGE') OR
       pg_catalog.has_schema_privilege('drip_identity_executor', 'drip_identity', 'CREATE') OR
       NOT pg_catalog.has_schema_privilege('drip_identity_runtime', 'drip_identity', 'USAGE') OR
       NOT pg_catalog.has_schema_privilege('drip_identity_migrator', 'drip_identity', 'USAGE') OR
       pg_catalog.has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'SELECT') OR
       pg_catalog.has_table_privilege('drip_identity_runtime', 'drip_identity.users', 'INSERT') OR
       pg_catalog.has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'SELECT') OR
       pg_catalog.has_table_privilege('drip_identity_runtime', 'drip_identity.external_identities', 'INSERT') OR
       pg_catalog.has_table_privilege('drip_identity_migrator', 'drip_identity.users', 'SELECT') OR
       pg_catalog.has_table_privilege('drip_identity_migrator', 'drip_identity.external_identities', 'SELECT') THEN
        RAISE EXCEPTION 'DRIP identity schema/table privilege verification failed';
    END IF;
    IF NOT pg_catalog.has_function_privilege(
           'drip_identity_runtime',
           'drip_identity.lookup_identity(text,text,text)', 'EXECUTE'
       ) OR
       NOT pg_catalog.has_function_privilege(
           'drip_identity_runtime',
           'drip_identity.register_identity(uuid,text,text,text)', 'EXECUTE'
       ) OR
       pg_catalog.has_function_privilege(
           'drip_identity_runtime',
           'drip_identity.identity_tables_empty_for_migration()', 'EXECUTE'
       ) OR
       NOT pg_catalog.has_function_privilege(
           'drip_identity_migrator',
           'drip_identity.identity_tables_empty_for_migration()', 'EXECUTE'
       ) OR
       pg_catalog.has_function_privilege(
           'drip_identity_migrator',
           'drip_identity.lookup_identity(text,text,text)', 'EXECUTE'
       ) OR
       pg_catalog.has_function_privilege(
           'drip_identity_migrator',
           'drip_identity.register_identity(uuid,text,text,text)', 'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'DRIP identity function grant verification failed';
    END IF;
    IF pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_owner', 'MEMBER') OR
       pg_catalog.pg_has_role('drip_identity_runtime', 'drip_identity_executor', 'MEMBER') OR
       EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
           WHERE roleid = 'drip_identity_executor'::pg_catalog.regrole
             AND member = 'drip_identity_owner'::pg_catalog.regrole
       ) THEN
        RAISE EXCEPTION 'DRIP identity role membership verification failed';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS p
        WHERE p.pronamespace = schema_oid
          AND p.prosecdef IS DISTINCT FROM
              (p.proname IN ('lookup_identity', 'register_identity', 'identity_tables_empty_for_migration'))
    ) OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS p
        WHERE p.pronamespace = schema_oid
          AND p.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog, pg_temp']::text[]
    ) THEN
        RAISE EXCEPTION 'DRIP identity function security attributes verification failed';
    END IF;
END
$$;
"""


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("DRIP identity foundation requires an online role and encoding preflight.")
    connection = op.get_bind()
    if connection.scalar(text("SELECT current_setting('server_encoding')")) != "UTF8":
        raise RuntimeError("DRIP identity foundation requires UTF8.")
    acquired = connection.scalar(
        text("SELECT pg_catalog.pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": _MIGRATION_LOCK_ID},
    )
    if acquired is not True:
        raise RuntimeError("Another DRIP migration operation is active.")
    op.execute(_PREFLIGHT)
    for statement in _UPGRADE_DDL:
        op.execute(statement)
    op.execute(_POSTFLIGHT)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("DRIP identity downgrade requires online emptiness and role checks.")
    connection = op.get_bind()
    if connection.scalar(text("SELECT current_user")) != "drip_identity_migrator":
        raise RuntimeError("DRIP identity downgrade role precondition failed.")
    acquired = connection.scalar(
        text("SELECT pg_catalog.pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": _MIGRATION_LOCK_ID},
    )
    if acquired is not True:
        raise RuntimeError("Another DRIP migration operation is active.")
    connection.exec_driver_sql("SET LOCAL ROLE drip_identity_owner")
    connection.exec_driver_sql(
        "LOCK TABLE drip_identity.users, drip_identity.external_identities IN ACCESS EXCLUSIVE MODE"
    )
    connection.exec_driver_sql("RESET ROLE")
    empty = connection.execute(
        text(
            "SELECT users_empty, external_identities_empty "
            "FROM drip_identity.identity_tables_empty_for_migration()"
        )
    ).mappings().one()
    if not empty["users_empty"] or not empty["external_identities_empty"]:
        raise RuntimeError("DRIP identity downgrade refuses populated identity tables.")
    for statement in (
        r"""DO $$
BEGIN
    IF current_user <> 'drip_identity_migrator' OR
       NOT EXISTS (
           SELECT 1 FROM pg_catalog.pg_auth_members
           WHERE member = 'drip_identity_migrator'::pg_catalog.regrole
             AND roleid = 'drip_identity_executor'::pg_catalog.regrole
             AND admin_option AND NOT set_option AND NOT inherit_option
       ) THEN
        RAISE EXCEPTION 'DRIP identity downgrade role precondition failed';
    END IF;
END
$$""",
        "GRANT drip_identity_executor TO drip_identity_owner WITH SET TRUE, INHERIT FALSE",
        "SET LOCAL ROLE drip_identity_owner",
        "GRANT CREATE ON SCHEMA drip_identity TO drip_identity_executor",
        "SET LOCAL ROLE drip_identity_executor",
        "DROP FUNCTION drip_identity.lookup_identity(text, text, text)",
        "DROP FUNCTION drip_identity.register_identity(uuid, text, text, text)",
        "DROP FUNCTION drip_identity.identity_tables_empty_for_migration()",
        "RESET ROLE",
        "SET LOCAL ROLE drip_identity_owner",
        "DROP TABLE drip_identity.external_identities",
        "DROP TABLE drip_identity.users",
        "DROP FUNCTION drip_identity.enforce_user_update()",
        "DROP FUNCTION drip_identity.reject_external_identity_update()",
        "DROP SCHEMA drip_identity",
        "RESET ROLE",
        "REVOKE drip_identity_executor FROM drip_identity_owner",
    ):
        op.execute(statement)
