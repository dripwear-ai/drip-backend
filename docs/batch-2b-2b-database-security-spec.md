# DRIP Batch 2B-2b — Database Migration and Security Foundation Specification

Date: **2026-11-16** (Asia/Calcutta)
Status: **Specification baseline; the bounded Batch 2B-2b implementation slice is separately owner-authorized. Batch 2B-2c is not authorized.**
Companion: [owner decisions and prerequisites](batch-2b-2b-owner-decisions.md)

## 1. Purpose, authority and scope

This specification turns the approved Batch 2B-2 decisions into a reviewable plan for portable migration history, a guarded PostgreSQL 17 bootstrap, and the database security foundation for the two identity tables. It does not create executable SQL, migrations, roles, policies, functions, or runtime behavior.

Approved architectural constraints are PostgreSQL/Supabase PostgreSQL as the source of truth; FastAPI as the only business-logic and authorization layer; Auth0 as external identity proof; stable application-generated DRIP UUIDv7 identifiers; exact `(issuer, subject)` identity mapping; disabled-first user records; no email-based linking; Redis only for ephemeral infrastructure; no direct LLM database access; and immutable historical migrations.

D01–D04 are owner-approved as recorded in the companion decision document. Actual Supabase project configuration, PostgreSQL version, managed role capabilities, connection mode, operators, and disposable test infrastructure remain unverified. These approvals do not authorize implementation or production use.

### In scope for the future implementation proposal

- Immutable historical revisions `0001_initial_baseline` and `0002_require_pg18_uuidv7`.
- Portable checkpoint **T**, revision ID `0003_portable_identity_ckpt` in file `0003_portable_identity_checkpoint.py`.
- Identity/security revision **U**, proposed revision `0004_identity_foundation`.
- A separately guarded, explicit fresh PostgreSQL 17 bootstrap that verifies revision 0001 effects before stamping exactly T.
- The private schema, two-table DDL matching Batch 2B-2a metadata, RLS, roles, fixed database capabilities, and acceptance tests on disposable PostgreSQL 17 and 18.

### Out of scope

Authentication endpoints, account activation, session persistence/revocation, admin grants, customer profiles, catalogue/wishlist tables, external identity linking, cloud provisioning, managed production migrations, and application repository/service behavior. No database connection or destructive operation is authorized by this planning task.

## 2. Repository facts and migration history

The current history contains exactly two revisions. `0001_initial_baseline` creates the `pgcrypto` extension if absent; its downgrade is a no-op. It creates no application schema or table. Whether the extension was newly created or already installed, and its owner/schema/version and objects, must be inventoried on a real target before adoption.

`0002_require_pg18_uuidv7`, directly after 0001, checks server version `>= 180000` and verifies `pg_catalog.uuid_extract_version(pg_catalog.uuidv7()) = 7`. It performs no table/default alteration and its downgrade is a no-op. It must remain byte-identical and must not be bypassed by changing its assertion or fabricating server capability.

`apps/api/migrations/env.py` imports `Base.metadata`, supports injected connections, and accepts an optional `version_table_schema`; absent that option, Alembic uses its default schema/search-path behavior. It doubles percent signs in the URL before configuring Alembic. For all future production/bootstrap calls, explicitly pin the established Alembic version table to `public.alembic_version` (or stop if an approved existing deployment establishes a different location); never let a changed `search_path` silently create a second version table. The current tests can set a temporary version-table schema for isolated rollback tests.

The migration environment imports `drip.models.base.Base`; the existing model package import registers the Batch 2B-2a identity tables. Registration is not evidence that those objects exist in any database. Migration U must create objects from reviewed migration definitions, not run application `metadata.create_all()` or autogenerate across Supabase/platform schemas.

The current application engine is created at import from settings, with `pool_pre_ping`, a bounded-by-settings pool in normal environments, and `NullPool` in test mode. `get_db_session` does not commit implicitly. Migration runs use a separate controlled process/credential and `NullPool`; API replicas must not run migrations at startup. Current pool defaults and absent explicit verified TLS setup are not approved Supabase production settings.

The lock resolves SQLAlchemy **2.1.4** and asyncpg **0.32.0**. This proves package selection only. Supabase direct, session-pooler, and transaction-pooler compatibility has not been verified for an actual project. The asyncpg dialect uses prepared statements; disabling its cache alone does not establish transaction-pooler compatibility.

## 3. Revision graph and checkpoint semantics

Freeze these IDs/names before coding; they are proposed names and are not present revisions today:

| Symbol | Proposed revision | Parent | Purpose |
| --- | --- | --- | --- |
| Historical 0001 | `0001_initial_baseline` | base | Existing pgcrypto operation only; immutable. |
| Historical 0002 | `0002_require_pg18_uuidv7` | 0001 | Existing PostgreSQL 18 capability assertion only; immutable. |
| **T** | `0003_portable_identity_ckpt` (`0003_portable_identity_checkpoint.py`) | 0002 | Portable lineage checkpoint. No identity tables or UUID server default. Normal upgrade verifies the supported baseline; PG17 adoption is handled only by the explicit bootstrap. The 27-character ID fits Alembic's default `VARCHAR(32)`; do not widen the version column. |
| **U** | `0004_identity_foundation` | T | Creates the two identity tables and the reviewed integrity/security objects using pre-provisioned role identities. |

### PostgreSQL 18 normal path

1. Attest a target explicitly approved for the operation; inspect current revision, version, existing application objects, extension state, and migration lock state.
2. Under a single migration runner and bounded migration lock, perform ordinary Alembic upgrade in order: 0001 → 0002 → T → U.
3. 0002 must actually execute and pass. T verifies its portable checkpoint preconditions. U creates only the reviewed `drip_identity` objects/security surface.
4. Verify the final revision and owned-object/security manifest. An unknown or populated pre-existing `drip_identity` namespace, unexpected revision, or conflicting writers stops the run for inventory; it is not reconciled automatically.

An existing PostgreSQL 18 database at 0001 advances normally through 0002, T, and U. One at 0002 advances through T and U. A database with an unknown revision, an unexplained `alembic_version` location, or unexpected identity objects must stop before any DDL. No downgrade or revision stamp is used to skip 0002 on PostgreSQL 18.

### Guarded fresh PostgreSQL 17 bootstrap

Ordinary `upgrade head` on a fresh PostgreSQL 17 server must continue to fail at 0002. A normal successor cannot repair an earlier failing revision. The only proposed alternative is the D01-approved, separately guarded bootstrap; it is not a generic `stamp` command and is not permission to stamp 0002 or `head`.

The bootstrap accepts only a specifically allowlisted, explicitly disposable or otherwise separately authorized fresh DRIP target, attests PostgreSQL **major version 17**, and refuses a shared/production/unknown target. It must fail closed on target ambiguity, unsupported major version, insufficient privileges, concurrent migration, unknown application objects, prior data/writers, incompatible extension state, or an existing conflicting Alembic version table.

“Fresh” means no existing DRIP installation or user data; it does not mean an empty Supabase database. Existing managed platform schemas/objects are retained and excluded from DRIP ownership. The bootstrap must not use blanket database emptiness checks that misclassify platform resources, nor broad autogeneration/drop behavior.

#### Exact preconditions and evidence before stamping T

Before opening a write transaction, record a secret-free target attestation and read-only baseline manifest:

- Target is the configured approved disposable/authorized PostgreSQL 17 database; database identity is verified without printing a URL or credential.
- Server version is 17.x; encoding, block size, privileges, and required extension namespace are recorded. Actual managed values are not assumed.
- No `drip_identity` schema, identity tables, DRIP-owned identity functions/triggers/policies, or unaccounted DRIP application objects/data exist.
- No conflicting `alembic_version` table/revision exists at the documented `public` location or any schema made visible by `search_path`; if found, stop. Existing PG17 databases are not silently adopted as fresh.
- `pgcrypto` state is snapshotted: extension catalog identity, version, namespace, owner, and extension-owned object manifest. Any namespace must be in an explicitly reviewed allowlist. The operation must not relocate, upgrade, or remove it.
- The migration operator can run 0001 and use Alembic stamping through the supported injected connection path. Platform role/extension limitations are checked before writing.
- A single migration runner holds the approved migration/advisory lock, with finite lock, statement, and connection deadlines approved under D06.

Then, on one injected connection and one explicit transaction:

1. Apply only the exact immutable 0001 revision. Do not execute 0002, forge version/function results, create domain objects manually, or stamp first.
2. Verify 0001's actual effect. The expected effect is the historical `pgcrypto` extension operation and its extension-owned objects, plus Alembic's version row at exactly 0001 in `public`. Compare before/after extension state and object inventory to distinguish “created by this operation” from “already installed and retained.” Any unexpected object, extension move/change, or missing capability fails verification.
3. Apply the same reviewed T precondition verifier used by the normal PG18 T path: supported minimum baseline, pgcrypto present in allowed unchanged state, no conflicting DRIP domain objects, and exact version-table location/state.
4. Only after all checks succeed, use Alembic's supported `stamp` API for the **literal T revision ID**. Never pass `head`, 0002, or a computed “latest” target. The receipt must explicitly say that 0001 executed and 0002's PG18-only assertion was intentionally not run on PG17.
5. Commit the transaction once. Verify after commit that the public Alembic revision is exactly T and the post-state manifest matches the expected T manifest. Only then report bootstrap success.

Alembic stamping is an explicit baseline-adoption mechanism; it records lineage and does not mean every ancestor migration body ran. The secret-free external deployment receipt must make this PG17 exception auditable: target identifier, PostgreSQL major/encoding/block size, route, pre/post manifests and hashes, extension provenance, exact revision, operator identity, timestamp, tool/build version, and outcome. Never store credentials, URLs, tokens, or identity subjects in the receipt.

### T manifest and convergence

At T, freeze an exact manifest for Alembic revision-table placement/value, the `pgcrypto` extension state and owned objects, and absence of DRIP identity objects. Do not require Supabase's unrelated system schemas to match between clusters. At U, compare only explicitly DRIP-owned schema/security objects: object names/types, columns/types/nullability/defaults/checks, collations, keys/indexes, functions/bodies/security attributes/owners/search paths, triggers, RLS flags/policies, grants/role membership relevant to this schema, extension references, and Alembic revision.

Fresh PostgreSQL 18 replay (0001→0002→T), existing PostgreSQL 18 upgrade from 0002, and guarded PostgreSQL 17 adoption must converge to the same approved DRIP-owned U manifest. Differences outside that ownership boundary are neither normalized nor deleted.

## 4. Failure, interruption, retry and recovery

All bootstrap state changes—including 0001's extension action, Alembic version-table updates, verification-dependent stamping, and T revision—must share one database transaction. PostgreSQL transactional DDL is relied on only after it is proven with disposable tests for the exact extension and platform versions. No external receipt is written as “success” before commit and post-commit verification.

| Observed condition | Required behavior |
| --- | --- |
| Preflight failure | No DDL or stamp; return a fixed safe diagnostic and retain a secret-free failure receipt. |
| Verification failure after 0001 | Abort/rollback the transaction; no T success record. Reinspect catalog state read-only before any retry. |
| Process interruption before commit | Reconnect read-only. Expect either the pre-bootstrap state or a committed complete state; do not infer from process exit alone. |
| Commit result unknown | Do not retry writes immediately. Attest target, inspect exact revision and manifest from a new connection. Exact T plus matching receipt/manifest is confirmed success; pristine pre-state is retryable after full preflight; any intermediate, conflicting, or unexplained state is a stop-and-review condition. |
| Exact verified T on retry | Return idempotent “already adopted” only if the recorded target identity and manifest match; perform no second `stamp` or extension operation. |
| Revision 0001 without T, partial extension state, wrong version-table schema, or stale/missing receipt | Stop for manual, owner-authorized inventory. Do not automatically complete stamping. |
| U migration failure | Roll back its transactional DDL and retain T. On uncertain commit, inspect U revision and owned-object manifest before retry. Never mark U complete from object presence alone. |
| Duplicate/concurrent bootstrap attempt | One runner proceeds under the migration lock. The other fails fast or waits only within the approved timeout, then rereads revision and manifest. |

Retry is a new operation after read-only attestation, never blind replay. Operator diagnostics must redact connection strings, credentials, SQL parameters, issuer/subject values and tokens. Logs record target identifier, revision, operation category and sanitized error class only.

## 5. U migration: reconcile SQLAlchemy metadata and database enforcement

U must create exactly two tables in private schema `drip_identity`, using the current models as the contract source and explicit migration definitions (not runtime `create_all`). It must not create catalogue, profile, session, admin-grant, wishlist, or other tables.

### `drip_identity.users`

- `id`: PostgreSQL UUID primary key; SQLAlchemy callable default is application `new_uuid7`; no server UUID default. U adds checks on binary UUID version nibble 7 and RFC variant bits using PostgreSQL UUID send bytes. No call to native `uuidv7()` or PostgreSQL 18-only extraction functions.
- `status`: non-null text; closed vocabulary `active`, `disabled`, `deletion_pending`; server default `disabled`.
- `created_at`, `updated_at`: non-null `timestamptz`, initialized from PostgreSQL transaction time; check `updated_at >= created_at`.
- A reviewed trigger rejects changes to `id` and `created_at`; on an allowed row update it sets `updated_at` to at least the greater of the old value and statement timestamp. This is database enforcement absent from SQLAlchemy `Column.info` metadata.

### `drip_identity.external_identities`

- `issuer`, `subject`: non-null `text COLLATE "C"`; composite primary key `(issuer, subject)`, no normalization, trimming, case folding, or email key.
- `issuer`: exact verifier-compatible canonical ASCII HTTPS DNS issuer, 1–260 bytes.
- `subject`: opaque, nonblank UTF-8 string, 1–1024 UTF-8 bytes, no NUL (PostgreSQL text itself cannot store NUL); do not trim, case-fold or Unicode-normalize.
- `user_id`: non-null UUID FK to `drip_identity.users.id`, `ON UPDATE RESTRICT`, `ON DELETE RESTRICT`, with UNIQUE constraint so a user has at most one external identity.
- `provider`: non-null text, check exactly `auth0`, no default.
- `created_at`, `updated_at`: non-null `timestamptz`, same transaction timestamp, check equality. A trigger rejects UPDATE of every mapping field; equality/default metadata alone is not an immutability mechanism.

### Mandatory database encoding precondition

Before U performs **any identity-object DDL**, its preflight must read the server's `server_encoding` and require the exact value `UTF8`. A different or unavailable encoding fails closed before U creates the schema, tables, functions, triggers, policies, or grants. Do not transcode or weaken the byte constraints to accommodate a different encoding. Record the verified value in the U manifest. This is a fixed technical acceptance condition, not a new owner option; the actual target value remains unverified under D05.

The approved limits remain issuer 1–260 ASCII bytes and subject 1–1024 UTF-8 bytes. Since PostgreSQL `octet_length` measures bytes in the database encoding, the UTF8 precondition is necessary for the subject limit to mean the approved UTF-8 bound. Real PostgreSQL 17 and 18 tests must use UTF8 databases and exercise accepted boundary values and over-limit multibyte subjects (including 256 four-byte code points at 1024 bytes and a rejected 257-code-point value), plus valid canonical issuer values at and beyond the approved byte bound. A metadata/string assertion is not a substitute for these server tests.

All defaults, named checks, collations, keys, nullability and FK behavior must match `apps/api/src/drip/models/identity.py`. SQLAlchemy `Column.info` annotations are documentation to metadata consumers, not PostgreSQL enforcement. In particular, the existing status default does not prevent a privileged insert from explicitly supplying `active`; the only registration capability must insert a new row with `disabled` and no activation/update capability is granted here.

The migration may use only pre-provisioned reviewed roles. It must not create cluster roles opportunistically or use a superuser fallback. It fails before domain DDL if required roles, ownership relationships, schema exposure policy, or privilege preconditions do not match.

## 6. Role architecture and privilege boundary

Proposed role names below are implementation labels; any final rename is a documented mapping, not a change to privilege semantics.

| Role | Login / ownership | Minimum capability | Must not have |
| --- | --- | --- | --- |
| `drip_identity_owner` | NOLOGIN; owns only the private schema/tables/policies/triggers and reviewed grants | DDL ownership in `drip_identity` | Runtime login, application use, superuser, `BYPASSRLS`, or membership granted to runtime. |
| `drip_identity_executor` | NOLOGIN; owns only the fixed SECURITY DEFINER functions; distinct from table owner | Permanent schema `USAGE`; exact SELECT/INSERT grants on the two tables, subject to table-specific RLS policies | Table ownership, login, `BYPASSRLS`, UPDATE/DELETE/TRUNCATE, permanent schema `CREATE`, or membership granted to runtime. |
| `drip_identity_migrator` | Controlled LOGIN for migration job; may assume the owner role only through audited operator provisioning | Apply reviewed Alembic revisions, call the migration-only emptiness helper, and verify ownership/manifests | Credential in the API process, public/client use, direct table access, BYPASSRLS, executor membership, default shared founder credential. Do not assume managed platform grants superuser/CREATEROLE. |
| `drip_identity_runtime` | LOGIN for FastAPI only | CONNECT, schema `USAGE`, and EXECUTE on the exact approved lookup/registration signatures | Direct table privileges, function ownership, owner/executor membership or inheritance/SET ROLE path, DDL, role administration, arbitrary SQL definer capability, or ability to activate a user. |
| `PUBLIC`, Supabase `anon`, `authenticated`, `service_role` | Existing platform identities, not DRIP identity runtimes | None on `drip_identity` tables/functions | Schema/table access, execute on private functions, ownership, or inherited path to runtime/executor/owner. Do not alter unrelated platform grants. |

The schema owner retains `USAGE` and `CREATE` as owner. `drip_identity_executor` receives permanent `USAGE` on `drip_identity` because its owned functions must resolve the schema-qualified tables; it receives no permanent schema `CREATE`. The runtime gets `USAGE` only to call its exact granted functions, and never receives table SELECT/INSERT/UPDATE/DELETE/TRUNCATE or schema CREATE. The migration role accesses the private schema through its controlled owner-role assumption and a separately granted migration-only helper signature; it receives no direct identity-table grants.

Function creation and ownership transfer are one controlled, auditable migration procedure inside U's transaction: (1) the migration job assumes `drip_identity_owner`; (2) owner creates each fixed function with its reviewed SECURITY DEFINER attributes; (3) the controlled role administrator temporarily grants the owner role SET-only membership in the non-login executor and grants executor schema `CREATE` only as required for ownership transfer; (4) owner transfers each exact function signature to `drip_identity_executor`; (5) the role administrator revokes the temporary SET membership and owner immediately revokes executor schema `CREATE`, verifies executor retains `USAGE` but lacks `CREATE`, revokes default/PUBLIC execution, then grants only the reviewed exact signatures to their designated roles; and (6) the migration records the ACL/owner manifest before commit. Temporary membership/grants must be transactionally reversible and removed before commit; the bootstrap must verify their absence. The role administrator authority required to perform this narrowly scoped operation is an environmental prerequisite under D07. If the managed provider cannot perform and verify this procedure without a superuser/BYPASSRLS fallback or persistent executor membership, stop before U DDL. Never grant executor membership to runtime. The migration helper is executable by the controlled migrator role only; lookup/registration are executable by runtime only.

Runtime role membership must be empty with respect to both owner and executor, including transitive memberships and any `SET ROLE` path. Verify membership direction, `INHERIT` and `SET` options, and default privileges from catalogs. Runtime must not be able to inherit/assume either role now or through a future default grant. Migration login may assume owner only through its separately provisioned, audited operator path; it must not assume executor.

Role creation/membership is a separately attested operator prerequisite. Role names must not collide with existing roles. Migration must inspect direct and transitive memberships, `INHERIT`/`SET` capability, `BYPASSRLS`, object ownership, default privileges, and PUBLIC grants. Abort if the managed platform cannot establish the approved separation. Never “fix” a privilege failure by granting a built-in service role broad access.

No reporting role is created. Least-privilege role provisioning and secrets remain separate from the FastAPI runtime. Runtime SQL credentials must not be a Supabase service-role key. Credentials are delivered by an approved secret manager, rotated/restarted under the future D07 procedure, and never committed or logged.

## 7. Forced RLS and SECURITY DEFINER contract

Enable both `ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` on both tables. Default is deny. Policies are scoped only to the non-login `drip_identity_executor` and only to the required SELECT/INSERT operations. The executor's table capability is intentionally broad within these two private tables, so safety depends on (a) it having no login and no runtime membership, (b) runtime having only exact function EXECUTE grants, (c) fixed reviewed function bodies, and (d) negative privilege tests. No `USING (true)` policy is granted to runtime or client-facing roles. Explicitly exclude `drip_identity` from Supabase Data API/GraphQL/Realtime exposure (or disable unused API surfaces) and verify actual project configuration; SQL grants and RLS are not a substitute for schema exposure review.

### Migration-only emptiness and state verification under FORCE RLS

The migration/table owner is also subject to policies under `FORCE ROW LEVEL SECURITY`; it must not attempt direct row reads or be granted `BYPASSRLS` to inspect emptiness. U therefore installs one narrow internal helper, `identity_tables_empty_for_migration()`, owned by `drip_identity_executor`. It has no parameters, uses the fixed safe search path and schema-qualified relations, performs only existence checks, and returns only two booleans (`users_empty`, `external_identities_empty`). It returns no count, identifier, issuer, subject, or row data and has no mutation side effects. The executor's existing SELECT policy/grant allows its SECURITY DEFINER body to perform the checks while FORCE RLS remains enabled.

Grant the helper's exact signature to `drip_identity_migrator` only; do not grant it to runtime, PUBLIC, `anon`, `authenticated`, or `service_role`. The migrator has schema USAGE needed to invoke the helper but no direct table privilege and no executor membership. Calls are made only by the controlled migration/downgrade job and are recorded in the secret-free deployment audit receipt with actor, target, revision, action, boolean outcome, timestamp and result—never identity values. A true result is a prerequisite to removing U-owned tables during downgrade; if either flag is false, downgrade refuses before destructive DDL.

Alembic revision state is verified separately through the fixed `public.alembic_version` table by the controlled migration job; the helper does not read or modify migration state. Owned-object definitions, role memberships, ACLs, RLS flags/policies and function attributes are verified from read-only catalog metadata available to the migration operator. If the provider withholds enough catalog visibility to verify the required manifest, stop; do not substitute superuser, `BYPASSRLS`, or broader runtime grants. An uncertain migration commit is reconciled by revision plus object manifest; helper output alone never establishes migration success.

The only planned application capabilities are the fixed exact lookup and atomic registration contracts from the approved foundation spec. The separate migration-only emptiness helper below is not an application/API capability:

- Lookup accepts provider, issuer, subject; performs exact pair matching; returns zero or one internal record (`id`, `status`, `created_at`, `updated_at`) to the trusted backend. It exposes no list/search, email lookup, arbitrary user-ID selection, or provider identifiers in public DTOs.
- Registration accepts only the application-generated candidate UUID and the verified provider/issuer/subject passed by the trusted FastAPI layer. It inserts one new disabled user and one binding in a single transaction. It cannot attach to an existing internal user, reassign a mapping, activate a user, update/delete data, or accept an email argument. Pair collision rolls back the candidate user; lookup of the winner is a separate fresh transaction. Unexpected database errors fail closed.

Functions are owned by `drip_identity_executor`, not the table owner or a BYPASSRLS role. Each is explicitly `SECURITY DEFINER` only where required, uses fixed `search_path = pg_catalog, pg_temp`, schema-qualifies every application object and sensitive built-in, uses bound values, and contains no dynamic SQL, caller-selected identifiers, arbitrary search or generic mutation. Do not trust client-set GUCs or `auth.uid()` as an internal DRIP ID. FastAPI derives arguments from a verified Auth0 `ExternalPrincipal`; database functions do not validate JWTs or grant authorization.

In the same reviewed migration transaction, revoke default `PUBLIC` execute and all unintended inherited/existing grants, then grant only the exact function signatures to `drip_identity_runtime`. No execution privilege is granted to `PUBLIC`, Supabase client API roles, or service-role. Runtime cannot set role to executor/owner. Fully qualified object references and a safe fixed path prevent caller-controlled schema shadowing; tests must probe temporary-object and function-replacement attacks.

`FORCE ROW LEVEL SECURITY` subjects table owners to policies but does not constrain superusers or `BYPASSRLS` roles. Those remain privileged operational boundaries, not a guarantee against database-owner compromise. The RLS design also cannot protect against compromised FastAPI code/credential invoking the approved exact-pair capability for another pair. These limitations must remain explicit in security reviews.

## 8. Async SQLAlchemy, asyncpg, pooler and TLS requirements

- Keep FastAPI's SQLAlchemy asyncio layer and pinned asyncpg unless evidence and separate approval authorize a dependency change.
- Managed target chooses the connection topology under D06. Prefer direct persistent TLS connectivity for the API when supported; use a session pooler only for a demonstrated network constraint. Use direct/session semantics for migration jobs as supported. Do not select shared transaction pooling by assumption.
- Test the exact pinned SQLAlchemy 2.1.4 + asyncpg 0.32.0 + Supabase connection mode, transaction semantics, prepared statements, concurrent sessions, cancellation, timeouts and RLS context. SQLAlchemy's asyncpg dialect calls `prepare()`; disabling the prepared statement cache alone does not remove this behavior.
- Require certificate-chain and hostname verification for managed connections. Test invalid CA, hostname mismatch, expiry/rotation, refused endpoint and timeout. Encryption-only SSL settings are insufficient. Do not print connection strings or secrets in test output.
- Set finite connection, pool-acquisition, statement, lock and transaction deadlines. Exact numerical budgets and process-wide pool sizing require D06 measurement/approval; current development defaults are not production approval. Account for API replicas, background workers, migrations and Supabase plan limits together.
- Migration/bootstrap runs as a controlled, serialized job, not each web replica. Keep URL percent-encoding handling and secret redaction. Migration credentials and runtime credentials are separate.
- `DATABASE_URL` and current environment-loading convention remain the interface unless a separately approved configuration change is made. This specification does not add or populate any environment variable.

No actual Supabase project, region, PostgreSQL version, pooler, TLS certificate, role grant, or database encoding has been verified. D05–D07 remain prerequisites for managed acceptance and deployment. UTF8 is mandatory before U; a non-UTF8 target is rejected rather than treated as an unresolved preference.

## 9. Test strategy and disposable targets

All executable tests are future work. The current local integration Compose file provides only PostgreSQL 18.6 and Redis on the documented Gate B test ports with tmpfs storage; it is not a PostgreSQL 17 or role-security test target. Existing integration tests use an outer transaction and a temporary schema on one connection; that cannot isolate independently committed concurrent sessions, global role creation or bootstrap revision state.

Create a new separately guarded database-test harness, outside the inherited PG18 integration `conftest` target or behind an equally strict target selection. B2-D08 must approve exact images/versions, endpoints, disposable database/project, credentials delivery, cleanup ownership, concurrency isolation, and target verification before any PG17/security service is created or contacted. Never point tests at Supabase, a shared dev DB, or another user's data. Do not repoint or weaken the existing guard. Use only test-generated synthetic identities and close every connection before task-scoped cleanup.

### Required layers

| Layer / evidence | Required checks |
| --- | --- |
| Offline/unit | Migration graph exactly 0001→0002→T→U; immutable hashes for 0001/0002; bootstrap allowlist parser; no credential/URL output; metadata-to-U manifest parity. No import-time engine connection. |
| Disposable PG17 migration | Ordinary historical `upgrade head` fails at 0002 with no T/head false stamp; guarded fresh route runs 0001, verifies its effect/provenance, stamps exact T, then upgrades U; rejects unsupported version/ambiguous target/unknown objects. |
| Disposable PG18 migration | Ordinary upgrade executes 0001 and 0002 genuinely, then T/U; native assertion remains meaningful; existing at-0002 upgrade reaches U. Historical file hashes unchanged. |
| Bootstrap failure/recovery | Injected failure before/after extension verification, before stamp, after stamp but before commit, transaction interruption, and unknown commit outcome; assert either pristine state or exact committed T, never a partial-success classification. Exact T retry is idempotent. |
| Schema parity | Against UTF8 PG17 and UTF8 PG18, verify encoding preflight rejects non-UTF8 before U DDL; exact columns, nullability, defaults, status/provider/byte/UUID checks, `C` collation, PK/unique/FK, trigger behavior, timestamp semantics and no database UUIDv7 default. Test issuer byte boundaries and subject values at 1024 and above 1024 UTF-8 bytes using multibyte code points. |
| Security/roles | Real role catalogs and `SET ROLE`/inherited privilege behavior; direct table SELECT/INSERT/UPDATE/DELETE/TRUNCATE denied to runtime, PUBLIC and API roles; only exact functions executable; no runtime membership/owner/BYPASSRLS; executor has schema USAGE but loses temporary CREATE; transfer and ACL procedure is auditable; FORCE RLS and intended executor policies; migration helper returns only empty flags to migrator and no data; temp/search-path spoof, GUC spoof, function replacement and malformed parameter tests. |
| Function atomicity/concurrency | At least 20 independent sessions for same pair; one committed user/mapping and same resolved ID; winner rollback; pair collision rolls back candidate; unexpected error/cancellation leaves no orphan; no email merge, second binding or reassignment. Test commit-unknown recovery and bounded retry after D06 deadlines are settled. |
| Managed acceptance | Only a dedicated approved expendable Supabase project after D05–D08 close: version, encoding, schema exposure, roles, TLS rejection, direct/pool mode, privileges and cleanup. No production/shared project. Separate review/authorization required. |

Existing scripts are `pnpm test`, `pnpm lint:api`, `pnpm type-check:api`, and `pnpm test:integration`; `pnpm test:integration` presently targets only the guarded PG18/Redis stack and does not prove this strategy. Future new harness commands are proposals, not existing scripts. No test, migration, SQL operation, bootstrap, or external-service command was run while writing this specification; only documentation structure/link/whitespace checks were run.

## 10. Rollback and recovery policy

- Preserve 0001 and 0002 byte-for-byte. Never rewrite/downgrade history to make PG17 replay succeed.
- PG17's minimum supported Alembic floor is T. A guarded migration entry point rejects any downgrade below T on PG17. Raw Alembic access is a privileged escape; minimize and audit it. Do not claim the guard protects a database owner who edits the revision table directly.
- U downgrade may remove only reviewed U-owned routines, triggers/policies/grants, and tables when both identity tables are empty and object ownership/manifests match. It must refuse if either table has rows. Do not use broad `CASCADE`; never drop platform schemas, `pgcrypto`, unrelated roles, schemas or objects.
- Do not automatically drop cluster roles or revoke operator access during downgrade. Role provisioning/cleanup is an explicit separate operator activity after inventory.
- On populated data, rollback means a forward-compatible correction or separately approved backup/restore—not `downgrade base`, ID regeneration, deleting identity mappings, or restoring account access implicitly.
- For PG18, the existing legacy round-trip may be tested only on an isolated disposable database. It does not justify populated production downgrade. For PG17, do not claim the native-default legacy test or run down past T.
- Backups, RPO/RTO, PITR, retention, 30-day private-data deletion, restored-account suppression and restore authority remain C7/D10 gates before real-user records.

## 11. Implementation sequence and exact acceptance gates

This plan follows the approved predecessor sequence and does not collapse 2B-2b portability into 2B-2c identity persistence/security merely because this document specifies both.

### 2B-2b — portable checkpoint and guarded test harness

Likely future files: `apps/api/migrations/versions/0003_portable_identity_checkpoint.py`, `scripts/bootstrap_identity_database.py`, narrowly scoped migration/bootstrap tests, and a separate guarded `apps/api/database_tests/` plus test-target configuration. `0001` and `0002` are not edited. Do not modify test Compose targets until D08 explicitly approves them.

Accept only when: exact target allowlist and preflight; PG17 ordinary replay rejection; guarded PG17 fresh adoption at T only after 0001 verification; PG18 historical replay to T; interruption/unknown-commit cases have no false stamp; identical T manifests; rollback-floor enforcement; immutable history hashes; exact commands/exits; no service target ambiguity.

### 2B-2c — U identity/security migration

Prerequisites: accepted 2B-2b; D02 role architecture; pre-provisioned role authority and target capability evidence; exact metadata parity; disposable PG17 and PG18 harness; approved function contracts and operational timeouts. Likely future files: `apps/api/migrations/versions/0004_identity_foundation.py`, role/bootstrap procedure, `apps/api/database_tests/` security cases, and later persistence modules only under their own authorization.

Accept only when: exactly two identity tables; UTF8 preflight passes and non-UTF8 fails before U DDL; metadata/DDL parity; actual PostgreSQL multibyte byte-boundary tests pass; triggers enforce the specified immutability/timestamps; role separation and no inherited/public/client grants; executor has USAGE and no persistent CREATE; temporary CREATE is revoked and verified after function ownership transfer; RLS/FORCE and exact definer functions pass negative tests; runtime has only exact function EXECUTE grants; migration emptiness helper reveals only booleans to the controlled migrator; atomic registration and lookup pass concurrency/rollback tests on both versions; downgrade refuses populated data; every test has actual evidence and target attestation.

No implementation is authorized by this document. Owner review and a separately scoped implementation authorization are required for each slice. 2B-2d managed acceptance and Batch 2B-3 remain separate gates.

## 12. Risks and open limits

1. **False checkpoint or wrong target (critical):** mitigated only by target attestation, exact 0001 provenance, single transaction, exact T stamp and post-commit manifest; any ambiguity stops.
2. **Supabase role/extension limitations (critical):** vendor branding does not prove superuser/CREATEROLE, schema ownership, extension namespace, or role membership capability. Verify before DDL.
3. **Definer capability compromise (critical):** function defects or leaked runtime credential can query/map arbitrary exact pairs. Keep functions tiny, role isolated, parameters bound, input verified in FastAPI, audit calls without identity values, negative-test privileges.
4. **Metadata/DDL drift (high):** `Column.info` is not enforcement; tests compare full schema manifests and behavior on real PostgreSQL versions.
5. **Pooler/TLS mismatch (high):** no managed endpoint or exact topology is selected; do not expose runtime persistence until D06 and S01 pass.
6. **Non-atomic role changes (high):** role provisioning may be outside migration transaction; perform as controlled prerequisite, verify membership/ownership, and do not drop roles on rollback.
7. **Unknown existing state/data (critical):** repository does not prove actual databases are empty. Inventory first; never stamp, migrate, clean, or drop unknown state.

This is a design specification, not evidence of PostgreSQL 17/18 execution, managed Supabase support, security enforcement, or migration acceptance.

### Implementation amendment — 2026-11-16

The owner selected the shorter exact T revision ID `0003_portable_identity_ckpt` while preserving the migration filename `0003_portable_identity_checkpoint.py`. It is 27 characters and fits Alembic's default `public.alembic_version.version_num VARCHAR(32)`; no widening or custom version-table implementation is permitted. The owner separately authorized this bounded local PG17 bootstrap/testing slice and reuse of the existing guarded PG18.6 integration target. The PG17 harness is pinned to the official `postgres:17.12-alpine3.24` multi-platform manifest digest `sha256:34261f594522cf41dfcb76aefd42b9d201098b0e6b23c9c68733f169e4218b6f`, uses a unique Compose project and tmpfs only, and has no authority to contact a managed or external database. This scoped authorization does not close D05–D07, D09, or D10, does not authorize U/2B-2c, and is not evidence that either PostgreSQL target has been started or tested.
