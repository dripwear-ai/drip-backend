# Batch 2B-2 — Database foundation implementation specification

Date: **2026-11-09**, Asia/Calcutta. **PLANNING ONLY — implementation not authorized.** Batch 2B-1R is owner-approved and closed by the current instruction. Its recorded verification remains historical; no software or database tests were rerun for this specification.

## 1. Scope, authority and entry gate

The owner has approved Auth0 authentication, Supabase PostgreSQL as the intended authoritative database, FastAPI business logic/authorization, permanent internal application-generated UUIDv7 IDs, and exact external mapping by `(issuer, subject)`. Email cannot establish identity or merge accounts. Redis remains ephemeral; LLMs have no direct database access. Money stays integer minor units or exact Decimal; neither proposed table contains money.

Everything labelled **proposed** below needs review with [the owner decision register](batch-2b-2-owner-decisions.md). Provider choice and application UUIDv7 ownership are settled and are not reopened. Historical Cognito/Supabase Auth and native-generation proposals are not current authority. This document does not release unresolved identity/session/admin gates.

Proposed implementation scope: two private tables, constraints/indexes, migration/bootstrap tooling, restricted database capabilities, an unrouted Python repository/service boundary and offline/disposable acceptance tests. No HTTP endpoint, login integration, account linking, profile, wishlist, cart, investment, transaction, session, grant, audit-event, notification or catalogue table. No admin lifecycle UI, provider setup, public Data API exposure or deployment. Lifecycle columns express denial state; they do not implement sessions, deletion workflows or founder privileges.

**Entry:** approve B2-D01–D04 in the decision register, authorize an exact implementation slice, and approve its disposable infrastructure before any live tests. Additional operational gates apply before managed or real-user use. No actual project, role, founder identity, credential or connection string is specified here.

## 2. Repository baseline and evidence reviewed

Repository `C:\Users\batla\Desktop\Drip`; branch `main`; HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`. Initial inventory: **37 modified tracked files, 139 untracked individual files, zero staged**. Both requested report paths were absent. All **192 Git-visible regular files** were SHA-256 hashed, including existing root Android/Gradle/IDE work. Ignored files, secrets and generated output are not included in that inventory. No applicable `AGENTS.md` or separately named constitution was found by the repository instruction filename search; ADRs, existing engineering rules and the current owner instructions apply.

| Inspected source | Current finding and consequence |
| --- | --- |
| [ADR 0001](adr/0001-modular-monolith-foundation.md), [ADR 0002](adr/0002-cognito-authentication-decision.md) and later decision amendments; relevant identity/privacy/approval sections of [Phase 2](phase-2-specification-and-plan.md), [P2-0](p2-0-contracts-and-acceptance.md), [readiness audit](p2-a-readiness-audit.md) | Preserve modular boundaries, exact money, separate founders, no linking and approval gates. Some old provider/readiness wording predates implemented primitives. No historical document is rewritten here. |
| [Infrastructure realignment](infrastructure-architecture-realignment.md), [Batch 2A](batch-2a-infrastructure-compatibility-report.md), [Batch 2A.1 §§7–8](batch-2a1-authentication-architecture-resolution.md) | The proposed portable-checkpoint bootstrap is already discussed. Their Auth0/application UUID choices have since been approved; checkpoint mechanics and managed target remain undecided. |
| [Batch 2B-1](batch-2b-1-identity-foundation.md), [Batch 2B-1R including review correction](batch-2b-1r-identity-hardening.md) | Historical final correction evidence: six files compiled, 157 focused tests and 405 backend tests passed, five live tests deselected; lint/Mypy passed. This is not evidence of identity persistence or Supabase access. |
| [Identity contracts](../apps/api/src/drip/identity/contracts.py), [configuration](../apps/api/src/drip/identity/config.py), [verifier](../apps/api/src/drip/identity/verifier.py), [dependency](../apps/api/src/drip/identity/dependencies.py) | External proof is distinct from `InternalUserId` and `AuthorizationContext`. Verifier preserves opaque subject, limits it to 1024 characters and issuer to a canonical HTTPS DNS origin up to 260 characters. It does not map users, prove human status or grant application permissions. |
| [UUID utility](../apps/api/src/drip/core/identifiers.py), [identity tests](../apps/api/tests/test_identity_foundation.py) | `new_uuid7()` calls native Python `uuid.uuid7()`. Runtime pin is 3.14.7, project requires `>=3.14,<3.15`. Utility exists but is not connected to current ORM defaults. |
| [Model base](../apps/api/src/drip/models/base.py) (UUID mixin line 42), [model package](../apps/api/src/drip/models/__init__.py) | Only base/mixins; no persistent domain model. `UUIDPrimaryKeyMixin.id` has database `uuidv7()` default and no Python default. Timestamp mixin has Python and server insert defaults, Python-only `onupdate`; raw SQL updates do not automatically update timestamps. |
| [0001](../apps/api/migrations/versions/0001_initial_baseline.py) (upgrade line 20), [0002](../apps/api/migrations/versions/0002_require_pg18_uuidv7.py) (upgrade line 13), [migration environment](../apps/api/migrations/env.py) (URL line 17), migration template and Alembic configuration | Only two revisions. 0001 installs `pgcrypto` if absent; 0002 asserts PG18/native v7; neither creates application tables. Both downgrades are no-ops. Environment escapes URL percent signs, uses `NullPool`, supports an injected connection and `version_table_schema`; it imports only `Base`, so future models must be explicitly registered for metadata/autogeneration. |
| [Database module](../apps/api/src/drip/core/database.py), [settings](../apps/api/src/drip/core/config.py), [setup](setup.md), API README | Async SQLAlchemy/asyncpg engine, pre-ping, local/test pool conventions; session dependency rolls back exceptions but does not commit success. Root dotenv/process loading, production credential/debug rejection and redaction exist. No reviewed managed TLS/role configuration exists. README still says Gate B pending; that stale sentence is superseded by owner acceptance, not fixed in this two-file task. |
| [Migration tests](../apps/api/tests/test_migrations.py), [five live tests](../apps/api/tests/test_live_infrastructure.py), [startup fixtures](../apps/api/tests/conftest.py), [target guard](../apps/api/tests/disposable_targets.py), [test Compose](../infra/compose.test.yml) | Current tests explicitly require server-generated v7 and a head equal to 0002. Live round trip uses a random schema, injected connection and outer rollback. PostgreSQL test service is 18.6; exact guarded loopback endpoints cannot be repointed at Supabase or PG17 silently. |
| [Live execution record](docker-live-integration-readiness-verification.md), [guard record](disposable-target-guard-verification.md), [Gate B record](gate-b-verification.md) | Prior five-test execution passed in the disposable PG18/Redis stack. Those results do not test role isolation, concurrent identity creation or managed Supabase. |
| API manifest/lock, root scripts, [shared exports](../packages/shared-types/src/index.ts), [router](../apps/api/src/drip/api/router.py) | Lock resolves SQLAlchemy 2.1.4, Alembic 1.20.0, asyncpg 0.32.0. Health routes only; no identity API/schema. Shared `MoneyINR` is string-valued paise; no new public identity DTO is needed in this database batch. |

This is source inspection, not a remote data inventory: absence of models in the repository does not establish that every existing database is empty. Unknown deployed tables, revisions, writers or defaults require a stop and separate inventory approval.

## 3. PostgreSQL compatibility and immutable history

### 3.1 What requires PostgreSQL 18 today

`0002_require_pg18_uuidv7` follows 0001. It rejects `server_version_num < 180000` and verifies `pg_catalog.uuid_extract_version(pg_catalog.uuidv7()) = 7`. It contains **no table/default alteration**. The reason was the Gate B native-generation contract: the shared ORM mixin supplies `server_default=uuidv7()` and the live test proves direct SQL and ORM inserts use it. `pgcrypto` is historical; it is not required for PG18's native v7 function.

The standalone Python generator already works independently of a database. PostgreSQL's UUID storage accepts externally generated UUIDs, while upstream PostgreSQL 18 supplies native v7 generation [E1–E3]. New user tables can therefore use application v7 values on PostgreSQL 17 without a native generator. Their ORM/Python default, if used, must be the callable `new_uuid7`, evaluated per insert; raw SQL must supply an ID and must fail when omitted. Existing mixin/default/test behavior does not change merely because the helper exists.

### 3.2 Behavior matrix

| Target/path | Current actual behavior inferred from source | Proposed compatible behavior; not tested here |
| --- | --- | --- |
| Fresh PostgreSQL 17, ordinary `upgrade head` | Stops at 0002. 0001 extension creation/version changes participate in Alembic's transaction when run together; do not assume a failed invocation leaves a partial stamp. Inspect actual state before retry. | Still reject ordinary historical replay. Use only approved verified bootstrap to portable checkpoint T, then subsequent migrations. |
| Fresh PostgreSQL 18, ordinary upgrade | 0001 extension operation; 0002 capability check succeeds only if required functions/privileges exist. No user tables result today. | Historical replay to T then shared new foundation revision U. |
| Existing PG18 at 0001 | Executes capability assertion at 0002. | Continue normally to T/U after inventory. |
| Existing PG18 at 0002 | Current head, no further work today. | Normal forward T/U; preserve existing data and revision history. |
| Existing database with unknown tables/revisions/defaults | Repository cannot establish compatibility. | Stop. No blanket default removal, table recreation, rekeying or stamping. Design data-specific changes separately. |
| Managed Supabase project | Version, existence, privileges, extension placement and connection mode unverified. | Confirm actual project before deployment; provider name does not establish PG18 capability. |

Official Supabase upgrade documentation reviewed on 2026-11-09 describes PostgreSQL 17; it does not establish a selected DRIP PG18 project. A text search found no PG18 offering in that guide. This is **insufficient evidence of availability**, not proof that Supabase universally cannot offer PG18. Actual project/server evidence remains pending. [E4]

### 3.3 Strategy evaluation

| Strategy | Advantage | Disadvantage/risk | Disposition |
| --- | --- | --- | --- |
| Require a confirmed Supabase PG18 target and replay all history | Simplest single replay path; preserves current five-test contract. | Ties fresh deployment to a managed capability not demonstrated; new IDs still must be application generated per owner direction. | Valid fallback if explicitly selected and verified; do not assume availability. |
| Immutable legacy chain plus fixed portable checkpoint and guarded fresh bootstrap | Supports PG17 UUID storage; one common future lineage, existing PG18 normal upgrade; follows Batch 2A.1 proposal. | Baseline adoption needs strict equivalence, provenance, rollback floor and interrupted-bootstrap tests. It intentionally does not execute the old capability assertion on PG17. | **Recommended, pending B2-D01.** |
| Separate permanent Alembic base/lineage | Can give PG17 a clean native replay path. | Two histories and adoption/merge/upgrade complexity for a two-table foundation. | Defer unless guarded checkpoint adoption is rejected. |
| Rewrite 0002, stamp it silently, fake server version/function, or add a successor that pretends to rescue earlier failure | None acceptable. | Conceals history or fails before successor; undermines test evidence. | Rejected. |

### 3.4 Exact proposed convergence sequence

T and U are **design labels**, not commands ready to run. Proposed filenames are `0003_portable_identity_checkpoint.py` and `0004_identity_foundation.py`; freeze IDs at implementation review. **Implementation status note (2026-11-16):** the owner approved T's literal revision ID `0003_portable_identity_ckpt` for the preserved filename `0003_portable_identity_checkpoint.py`. U remains unauthorized and has no implementation revision ID.

1. Freeze SHA-256 of both historical files. In a later explicitly authorized target, inventory exact current revision, database version, DRIP-owned objects/defaults, pgcrypto presence/namespace and writer paths. Managed `auth`, `storage`, extensions and unrelated objects are not DRIP-owned. An unknown or populated application schema is never a fresh-bootstrap target.
2. Introduce T as a successor of 0002, marking the **existing empty domain schema plus pgcrypto capability**, with a minimum supported version of 17 for future portability. T need not alter any default: no persistent application table was created by this history. Its explicit compatibility/provenance purpose is not a claim that a no-op revision fixes historical replay. If inventory finds real native-default columns, stop and separately design their writer-first forward transition; do not fold unknown tables into T.
3. Existing/fresh PG18 targets run ordinary 0001 → 0002 → T. Freeze the exact expected owned-object/extension/revision-state manifest at T. Preserve the existing public/default Alembic version-table location explicitly; do not accidentally select a second table via search_path. T contains no identity tables yet.
4. Fresh PG17 only: a reviewed bootstrap command must require an explicitly allowed disposable/deployment target, an empty DRIP namespace, no conflicting Alembic version table, version 17, expected managed schema allowlist and sufficient privilege. Managed platform objects may already exist; “fresh” means no DRIP installation, not an empty Supabase database.
5. Within one injected-connection transaction, run Alembic to the **exact immutable 0001 revision**, which is valid on PG17 and supplies the historical extension operation. Verify the durable effects at T, including pgcrypto availability (retain an existing managed extension namespace; never relocate/drop it), against the frozen T manifest and T's version precondition. T has no new domain DDL to reproduce. Only then use Alembic's supported stamp API to record the **exact T revision**, never 0002 or moving `head`. This keeps schema work Alembic-controlled instead of creating tables/extensions with an unrelated `create_all` script. Record that 0001 ran, T was adopted and 0002's historical capability test was intentionally not executed. Preserve a secret-free external deployment receipt with target identity, route, manifest/hash, operator, time and resulting revision; no speculative audit table.
6. Failed verification must roll back without a success stamp. A rerun at verified T reports already adopted; mismatched T, ambiguous outcome or residual conflicting objects stops for inspection. Do not stamp first and validate later. Baseline mechanisms are supported by Alembic [E5]; safety of this DRIP procedure still needs disposable proof.
7. All three routes (fresh PG18 replay, existing PG18 upgrade, fresh PG17 adoption) execute **the same U migration** for the two tables, constraints, functions/triggers, RLS and grants. Role identities must be provisioned through the separately approved operator procedure before U; no credentials inside migrations. Schema equivalence includes indexes, collations, defaults, function bodies/security attributes, triggers, grants, policies, owners and version state, not merely SQLAlchemy tables.
8. New entities use explicit application UUIDv7 and no database UUID default. Recommend an identity-specific column/mixin while retaining the old server-default mixin solely for historical Gate B coverage; do not use it in new models. A later separately reviewed cleanup may rename it. New runtime must contain no dependency on native UUIDv7 for identity creation.

The immutable chain can therefore remain available while supporting an approved PG17 target **only with this explicit alternate initialization path**. A regular successor cannot erase an earlier assertion for a clean replay. No existing database engine is downgraded; moving PG18 data to PG17 would be a separate restore/migration project.

## 4. Proposed schema and lifecycle

Proposed private schema: `drip_identity`, excluded from Data API/GraphQL/Realtime exposure. Proposed table names: `users`, `external_identities`. Names/role design are reviewable B2-D02/D03 decisions, not existing resources. SQL below is described as constraints, not supplied as executable migration code.

### 4.1 `drip_identity.users`

| Column | Type / nullability | Default / constraint | Index, ownership and security |
| --- | --- | --- | --- |
| `id` | PostgreSQL UUID; NOT NULL | Primary key; generated by backend `new_uuid7()` before insert, **no server default**. Proposed check of version nibble 7 and RFC variant bits using portable UUID binary bytes, not PG18 extraction functions. | PK B-tree. Permanent DRIP-owned ID; never accepted from client registration input. UUID reveals approximate generation time and is not a secret or authorization proof. |
| `status` | `text`; NOT NULL | Proposed closed check: `active`, `disabled`, `deletion_pending`; database default **`disabled`**. Initial foundation registration also creates disabled records. | No status index until an approved bulk lifecycle query needs it. Database authoritative; no token role/status overrides it. No activation function/endpoint in this batch. |
| `created_at` | `timestamptz`; NOT NULL | Server transaction timestamp; immutable after creation. | No standalone index required for exact-ID lookup. Service does not supply caller time. |
| `updated_at` | `timestamptz`; NOT NULL | Same insert timestamp. Proposed BEFORE UPDATE trigger sets it to the greater of old value and statement timestamp; check `updated_at >= created_at`. | No standalone index. Trigger also rejects changes to ID/created_at. Does not imply an approved lifecycle-update API. |

Initial disabled status is a **fail-closed proposal**, not a new approved product rule: mapping creation alone must not activate private operations before enrollment/session policy is approved. Owner may choose explicit eligible activation later under B2-D04; do not silently change the default to active. Future active means “not account-disabled,” not session/MFA/grant proof. Disabled and deletion-pending mappings remain reserved and return denial; login cannot create a replacement account to bypass the state. Restoration, deletion request, purge and their state transitions remain separate C4/C7 work.

Timestamp authority is intentionally specified for new tables rather than inheriting the current mixed Python/server behavior unnoticed. Use PostgreSQL microsecond timestamptz values and UTC session/display convention. Exact public timestamp string normalization and catalogue freshness are untouched. Lifecycle update triggers are schema integrity, not an implemented account-management workflow. [B2-D03/D04; E6]

### 4.2 `drip_identity.external_identities`

| Column | Type / nullability | Default / constraint | Index, ownership and security |
| --- | --- | --- | --- |
| `issuer` | `text COLLATE "C"`; NOT NULL | No default. Exact configured verified issuer; proposed ASCII, 1–260 byte bound and canonical format matching verifier. Never lowercase/trim/strip trailing slash on write. | First part of composite primary key `(issuer, subject)`, which provides the required unique constraint. No redundant unique index. Private provider identifier. |
| `subject` | `text COLLATE "C"`; NOT NULL | No default. Exact opaque nonblank subject; proposed 1–1024 **UTF-8 byte** bound, no NUL; never trim, case-fold or Unicode-normalize. | Second part of primary key. Case/trailing-space-distinct valid values stay distinct. No email lookup/index. |
| `user_id` | PostgreSQL UUID; NOT NULL | FK to `users.id`, ON UPDATE RESTRICT, ON DELETE RESTRICT. Proposed UNIQUE for initially one identity per internal user. | Unique B-tree also serves FK/reverse lookup. Cannot update/reassign the binding. |
| `provider` | `text`; NOT NULL | No default; check `provider = 'auth0'` initially. Future providers require a reviewed migration. Provider is not an extra discriminator that could weaken unique issuer/subject. | No provider-only index. Server-selected; never inferred from an email/domain or editable client flag. |
| `created_at` | `timestamptz`; NOT NULL | Server transaction timestamp, immutable. | No standalone index; private association metadata. |
| `updated_at` | `timestamptz`; NOT NULL | Same server timestamp; check equality with created_at; immutable. | Retained to respect the base engineering rule that entities carry creation/update timestamps. No claim that immutable identity records are periodically updated. |

All external-identity columns are immutable. A rejecting UPDATE trigger plus absent runtime UPDATE privilege protects the boundary; table owners remain privileged and must be operationally controlled. No cascade deletes. A separately approved purge must explicitly remove the binding and user in one authorized transaction after retention/recreation policy is settled; no deletion capability is granted now. “Never update a mapping” is not permission for indefinite personal-data retention.

**Cardinality proposal:** one committed user has exactly one binding through the only authorized creation capability; the UNIQUE FK prevents a second binding. The FK/unique constraints alone do not prevent a privileged operator creating an orphan parent—atomic creation and no direct runtime writes enforce that side. Future explicit linking/provider migration would require a reviewed change to cardinality plus ownership proofs; neither same-email matching nor token refresh changes a binding. Stable internal IDs survive that future procedure.

**Index-size finding:** the verifier's existing 1024-character bound permits multi-byte subjects too wide for a composite B-tree entry. PostgreSQL character limits are not byte limits; B-tree entries have page-size limits [E7/E8]. Proposed bounded text/check constraints avoid silent varchar casts/truncation and keep the pair comfortably below an 8 KiB page's index-entry limit. Confirm block size and worst-case insert in both database versions. This tightens persistence acceptance relative to the verifier; **B2-D03 approval is required**. Reject an overlong identity with a fixed safe error before writes; do not truncate or replace uniqueness with a hash-only approximation. If full 1024-character Unicode support is required, redesign/test exact uniqueness before implementation.

### 4.3 UUID enforcement and legacy data

For new users, check v7/version and RFC variant in both application and database: inspect byte 6 high nibble and byte 8 high bits of the UUID binary representation. Unit/integration tests must prove the expression on PG17 and PG18; no unavailable native function. PK enforces uniqueness, not generator quality. Generate at call time, never at import. Raw SQL without ID fails; explicit UUIDv4 fails for new users. External subject is opaque and may legitimately contain a provider UUIDv4 string.

Do not rewrite historical IDs/FKs, including legacy UUIDv4 if external inventory reveals it. Such existing tables require a separate compatibility/migration decision; the new-table constraint is not automatically applied to unknown legacy rows. UUID order is not a global commit order. No new UUID dependency or TypeScript generator is needed; future wire IDs remain strings, with no public DTO introduced here.

## 5. Transaction and isolation contract

Future Python modules consume only a trusted `ExternalPrincipal` from the approved verifier/composition boundary, not a request-supplied user ID, issuer or email. Real route integration remains gated on allowed customer flows, realm/API profile and C4. These functions establish storage identity, never return an `AuthorizationContext` or infer admin grants.

Proposed database capabilities in a private, unexposed schema: exact lookup and atomic registration. These are database functions, **not API routes**. Proposed signatures are `lookup_identity(provider, issuer, subject)` and `register_identity(candidate_user_id, provider, issuer, subject)`; provider/issuer/subject parameters are text, candidate ID is UUID. Null/invalid input fails with fixed errors. Lookup returns zero or one internal record (`id`, `status`, `created_at`, `updated_at`); registration returns the same shape for the inserted pair, subject to the caller's later commit. The latter receives the application-generated candidate UUID and exact verified issuer/subject/provider; it never accepts an existing account ID to attach an identity. FastAPI owns eligibility and orchestration; database functions enforce narrow storage invariants. These names and signatures are proposals under B2-D02, not installed routines or public contracts.

1. Perform exact-pair lookup. Return zero or one internal record with status/timestamps to trusted backend only. A conflicting provider for the same pair is an integrity error, not a second account. Do not return provider identifiers through a new public response.
2. On first registration, generate candidate UUIDv7 in Python; enter one explicit SQLAlchemy transaction. Atomic registration inserts a **new** disabled user and its identity. It must fail on an existing candidate PK; it cannot reuse that user. Both inserts share the transaction; no commit between them and no user-only success.
3. On unique pair conflict, roll back the whole failed attempt (including its new user), then exact-lookup the winner in a fresh READ COMMITTED transaction. PostgreSQL uniqueness, not a Redis lock or pre-check, decides ownership. No `ON CONFLICT DO UPDATE user_id` and no catch-all integrity-error-as-success.
4. Bound collision/serialization retries to a proposed three attempts. Catch named expected constraints/SQLSTATE internally, recheck current account status after resolution and return a sanitized retryable failure on exhaustion. Unexpected FK/check/privilege errors fail closed. Logs must omit SQL parameters, issuer/subject, tokens and credentials.
5. Return a confirmed new mapping only after commit. If commit outcome is unknown, do not claim creation succeeded or failed definitively; a later exact-pair lookup/retry reconciles using the unique key. Do not create an unrelated “replacement” internal ID on uncertain outcome. The current `get_db_session` does not commit implicitly; implementation must own transaction completion.

| Case | Required result |
| --- | --- |
| First eligible storage registration | One user plus one immutable binding, committed together; initially disabled under proposed B2-D04 policy. |
| Sequential duplicate or many concurrent identical pairs | All successful resolutions return the same internal ID and current status; exactly one user/binding remains after losers roll back. |
| Same subject, different issuer; same issuer, different subject | Distinct pairs/users; never normalize or associate them. |
| Same email in two provider identities | No email field/argument participates; distinct subjects remain distinct accounts. |
| Existing disabled/deletion-pending mapping | Resolve for internal denial; never create/re-enable a user. Unknown status also denies. |
| Failure after first insert, FK failure, cancellation before commit | No committed orphan user or binding; transaction rolls back. |
| Candidate UUID already belongs to another user | PK conflict, never bind to that user; regenerate only for a genuine new registration attempt. |
| Attempt to reassign, change subject/issuer/provider, or attach a second identity | Reject; absent capability, immutable trigger and constraints. |
| Caller supplies another internal ID / counterfeit principal | No public parameter accepts it; service entry trusts only internal verifier output. Python dataclasses are not an in-process security sandbox. |

Each request/task has its own AsyncSession; no cross-task session sharing. Database statement/lock timeouts and transaction budget are required before exposed use (B2-D06). A database record's status can change after lookup; later private operations must recheck authoritative state inside their own transaction under an approved concurrency/session policy. This batch does not promise immediate revocation from a one-time mapping lookup.

## 6. PostgreSQL roles, RLS and trust boundary

**Recommended design, pending B2-D02:** FastAPI is the only application data access path. No direct browser/mobile SQL or Supabase business-table API. Auth0 tokens are not Supabase database logins, and `auth.uid()` must not be assumed to contain a DRIP internal UUID. No client-set user ID or session variable establishes authorization.

| Proposed role/capability | Allowed | Explicitly denied / review requirement |
| --- | --- | --- |
| Non-login object owner | Own private schema/tables, constraints and RLS definitions. | No runtime login; no grant to client/runtime to assume it. Owner can alter security and remains trusted operationally. |
| Controlled migration login | Time-bounded ability to assume owner and execute reviewed Alembic/bootstrap changes. | Separate secret from runtime; never in application process; audit operator and revision. No claim managed PostgreSQL supplies unrestricted superuser. |
| Non-login identity function executor | SELECT/INSERT only on these two tables, plus fixed functions it owns. RLS policies allow the needed rows/insert operations for this internal executor. | No UPDATE/DELETE/TRUNCATE, schema creation, broad catalog access, BYPASSRLS, login or runtime role membership. Its cross-row lookup authority exists only behind reviewed exact-pair functions. |
| Runtime login | CONNECT, required schema USAGE and EXECUTE on only exact lookup/atomic registration signatures. | No table DML/SELECT, owner/executor membership, DDL, role creation, default PUBLIC function execution or raw user search. Cannot grant privileges or activate accounts. |
| Browser, mobile, Supabase `anon`/`authenticated`/service API roles | None on this schema/functions. | No grants, exposure, publication or Realtime subscription. A service-role key is not the application's SQL credential and must not be used as a bypass. |
| Reporting | None initially. | Add only justified redacted views and a separately approved least-privilege role later. |

Enable **RLS and FORCE RLS on both tables**; default deny for roles without an applicable policy. Policies for the internal non-login executor are deliberately table-scoped SELECT/INSERT capabilities; they are not unrestricted runtime policies. Security-definer functions must have fixed `search_path = pg_catalog, pg_temp`, fully qualified application objects and built-in calls, bound parameters, no dynamic SQL, no arbitrary table/column/user selectors, exact issuer/subject matching, and no grant/elevation methods. No untrusted schema may shadow referenced objects. Create/revoke PUBLIC EXECUTE/grant exact signatures atomically. Function owner must not also be table owner or BYPASSRLS. Test inherited privileges and PUBLIC defaults, not only explicit grants. [E9/E10]

The runtime cannot read arbitrary rows by setting a GUC because it has no direct table privileges and functions do not consume client user-context settings. Backend derives the function arguments from verified proof. The database does **not independently validate Auth0 JWTs**; a compromised runtime credential/code could invoke an allowed lookup with another pair. RLS/definer functions do not solve compromise of that trusted boundary. Protect credentials, use network restrictions/rotation, audit capability use without sensitive input and validate callers before exposure. Do not claim “RLS proves JWT ownership.”

Alternative for review: direct ORM table access with transaction-local verified context and row policies. It is simpler for CRUD, but context injection and pre-mapping registration require careful design; a runtime role able to set arbitrary identity context is trusted and cannot be protected from itself by that context. A broad BYPASSRLS runtime or `USING(true)` policy for the application is rejected. The capability design is recommended because this batch needs only two operations; permission/definer tests are mandatory overhead, not optional hardening.

Supabase exposed schemas and grants must be inspected in later disposable managed acceptance. Prefer disabled Data API when unused; at minimum exclude `drip_identity` and revoke all relevant API grants. Owner/superuser/BYPASSRLS privileges can defeat row policies; FORCE alone is not protection against all administrative credentials. [E9–E11]

## 7. Managed readiness, connection and configuration specification

- Project existence/reference, region, environment separation, actual PostgreSQL version/block size, extensions and role-provisioning capabilities are **UNVERIFIED**. Obtain sanitized evidence under B2-D05; never request passwords in chat. India-first does not establish a residency guarantee.
- Recommend persistent FastAPI with a bounded SQLAlchemy pool over direct TLS; session pooler is a candidate when IPv4/network constraints require it. Use direct connectivity for migrations/bootstrap/backup tools where supported. Set connection budget across all processes, preserving headroom for migrations/operations. Existing 10 + 20 per-process defaults are not an approved Supabase budget. [E12]
- Do not adopt shared transaction pooling by only disabling a cache. SQLAlchemy's asyncpg dialect calls `prepare()`; a zero prepared-statement cache does not eliminate that use. Shared pooler transaction-mode compatibility therefore needs explicit driver/platform evidence. Dedicated pooler support is distinct. No dependency switch is inferred. [E6/E12/E13]
- Require TLS with certificate-chain and hostname verification for managed runtime/migration connections. Driver-equivalent verified SSL context must be tested with asyncpg/SQLAlchemy; do not copy an unsupported libpq URL option blindly. Encryption-only `require` is not full server verification. Certificate source/rotation and egress allowlists need approval. [E14]
- Preserve existing `DATABASE_URL`, `DRIP_ENV_FILE`, `ENVIRONMENT`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT` conventions. Proposed migration invocation uses a separate protected process credential supplied through the existing URL setting; no new configuration variable is invented here. Preserve percent-encoding regression and redaction. Deployment secret manager, named operators and rotation/restart procedure remain pending; no `.env` change.
- Alembic runs as a controlled job, once per target with an approved migration lock and bounded lock/statement timeouts, not automatically from every API replica. Keep injected test-connection behavior and percent escaping. Explicitly scope metadata/autogenerate to owned objects; never generate drops for Supabase system/unknown tables. New models must be registered before metadata comparison.
- Backup/PITR plan, RPO/RTO, retention, deletion suppression and restored-account denial need owner values and a restore drill on a disposable target. Do not assume free-tier backups or an indefinite soft-delete satisfies the 30-day private-data deletion target. C7 governs identity/backup retention; no catalogue retention policy is reused. [E15]

## 8. Test and acceptance matrix — future work, not executed

| ID / layer | Required evidence |
| --- | --- |
| U01 unit | Native v7 object, version/variant bits, 2,048 unique samples, JSON round-trip; no UUIDv4 fallback. Existing generator tests retained; add per-insert/default tests. Sample uniqueness is not a mathematical proof. |
| U02 unit/metadata | Only two proposed tables; exact columns, PK/FK/unique/check constraints, no server UUID default; immutable/provider bounds; no email field or email argument. No import-time connection. |
| U03 unit/service | Verified principal required; exact pair, no normalization, fixed/redacted errors, inactive denial, bounded retries, rollback/cancellation and commit-unknown behavior. No permissions inferred. |
| I01 disposable PG17 and PG18 | Real UUID v7/variant checks; missing ID, v4, nulls, invalid status/provider/bounds rejected; max-byte and multi-byte cases; FK failures and immutable-update denial. ORM mappings and capability writes agree. |
| I02 disposable concurrency | Barrier-start at least 20 independent sessions for same pair: one committed user/binding, same resolved ID; repeat with winner rollback and lock timeout. Different pairs with same email-like test metadata remain isolated. No Redis dependency. |
| I03 disposable atomicity | Failure after user insert, invalid binding, unexpected integrity error, cancelled transaction: zero orphan commits. Duplicate candidate belonging to another user cannot attach identity. Unknown commit reconciles by pair. |
| I04 disposable isolation | Pair A cannot request B's ID through exposed function shape; no list/search function; exact match and minimal result. Subject case/Unicode/trailing-space distinctions; issuer distinctions; second binding/reassignment denied. |
| I05 disposable roles/RLS | Actual runtime role cannot SELECT/INSERT/UPDATE/DELETE/TRUNCATE tables or assume executor/owner; only two exact function signatures executable. PUBLIC/API roles denied, RLS/FORCE enabled. Search_path/temp spoof, malformed input, inherited grants, function replacement, GUC spoof and revoked EXECUTE fail closed. Owner/privileged bypass limitations explicitly evidenced. |
| M01 disposable PG18 legacy | Historical file hashes unchanged; replay 0001/0002 still verifies native v7. Existing baseline/native-default tests remain meaningful. Update head expectations explicitly when U exists; do not pretend head remains 0002. |
| M02 disposable PG17 portability | Ordinary historical replay fails at 0002; authorized T adoption succeeds only on allowed empty DRIP target. Negative unknown revision/nonempty schema/extension mismatch/insufficient role/interruption tests leave no false stamp. Repeat verified T is safe; no moving-head stamp. |
| M03 disposable convergence | Fresh PG18 replay, existing PG18-at-0002 upgrade and fresh PG17 bootstrap produce equal owned schema/security manifests at T and U; all IDs/FKs in relevant test data preserved. Unknown legacy tables stop rather than get altered. |
| M04 disposable downgrade/recovery | U rollback only under approved empty-foundation policy; populated tables refuse destructive downgrade. PG17 floor T enforced before any downgrade below it. PG18 historical round trip remains separately testable. Failed migration rolls back with correct revision; restore/reapply and secret-free provenance verified. |
| S01 disposable managed Supabase only | Confirm actual version, schema exposure, roles, TLS invalid-cert/host rejection, direct/pool connectivity, pool budget, function privileges and migration operator constraints. No managed production/personal/shared database test execution. |
| S02 disposable managed restore | Authorized backup/restore drill with synthetic test-only records; RPO/RTO measured, inactive/deletion restrictions not silently restored to active. C7 decisions must precede real-user deployment. |

Current runners exist: `pnpm test`, `pnpm lint:api`, `pnpm type-check:api`, and `pnpm test:integration` (exact guarded PG18/Redis stack only). Future focused command can use existing `uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml ...`; proposed test paths must exist before claiming it was run. No new test runner/package is needed for unit tests.

The current `conftest.py` fixes **both** disposable endpoints before imports: PostgreSQL `127.0.0.1:55435/drip_gate_b_test`, Redis `127.0.0.1:56381/0`. Do not weaken its URL/case guard, replace its image with PG17 secretly, or point these commands at Supabase. Propose a separate explicitly guarded `apps/api/database_tests/` suite and separately reviewed disposable target configuration for PG17/security-role/concurrent-commit testing (outside the inherited existing tests conftest). B2-D08 must fix exact project/images/ports/credentials/cleanup and verification procedure before code or service execution. No new command/configuration is represented as available today.

Outer-transaction rollback works for existing single-connection Gate B tests. It cannot contain independently committed concurrent sessions, bootstrap version state or cluster-scoped role creation. The new harness needs an explicitly owned disposable database/stack, recorded object ownership, all connections closed and task-scoped cleanup in finally blocks. Never drop roles, schemas, volumes or databases by loose name prefix on a shared system. Managed tests require a dedicated expendable project, separate authorization and strict target attestation; do not relax the local guard to accommodate them.

## 9. Implementation sequence after approval

| Slice | Prerequisites / likely files (proposed, not created) | Acceptance and stop gate |
| --- | --- | --- |
| 2B-2a: contract/metadata and pure tests | B2-D03/D04; `models/identity.py`, model registration, `identity/repository.py` protocol and focused `tests/test_identity_persistence_contract.py`. Reuse UUID utility; no public route. | Exact schema/default/bounds/denial contract and offline tests; no dependency change. Standalone authorization can bound this slice before cloud decisions. |
| 2B-2b: portability and guarded test harness | B2-D01/D08; proposed T revision, `scripts/bootstrap_identity_database.py`, `apps/api/database_tests/`, reviewed disposable config, migration/env scoping where necessary. | PG17 rejection + adoption, PG18 normal replay, T equivalence, failure atomicity and historical hashes. Stop if unknown state or target. |
| 2B-2c: persistence/role boundary | B2-D02/D03/D04 and 2b; proposed U revision, reviewed role provisioning procedure, narrow SQL functions/policies, `identity/repository.py`, `identity/service.py` and unit/integration tests. | Two-table atomic registration/lookup, concurrency, no reassignment/linking, real-role negative tests on both versions. Unrouted and inactive by default. |
| 2B-2d: managed acceptance and release decision | B2-D05–D10 as applicable, separately authorized expendable project; deployment documentation and test evidence. | TLS/roles/version/bootstrap/restore evidence; exact commands/exits and unresolved limits recorded. No real-user activation or 2B-3 without separate approval. |

Do not create domain models before the corresponding contract approval. Later implementation documentation may correct stale README/ADR current-status descriptions, with historical decisions preserved; this planning task edits neither. Scope/timing must account for stored-function review and dual-version integration tests rather than treating two tables as just two ORM classes.

## 10. Security, rollback and recovery

Primary risks: false baseline stamps; a managed version presumed from vendor branding; metadata autogeneration touching platform tables; privilege escalation through PUBLIC/definer ownership; SQL/exception logs exposing subjects; same-email or normalization collision; an overlarge unique key; orphan users from race recovery; session-context leakage through pooling; persisted disabled accounts accidentally activated; and restoring erased/revoked identities from backup.

Mitigations are explicit bootstrap preconditions/manifests, exact-match bounded data, atomic writes and unique constraints, private capabilities, least-privilege roles, verified TLS, reviewed operator authority and negative tests. These do not eliminate compromise of the migration owner or runtime verification boundary. No arbitrary custom UUID function, new auth provider, Redis identity cache authority or secret-bearing diagnostic is introduced.

Rollback policy proposal: before real data, U's downgrade may remove only its reviewed empty owned objects, refusing if either identity table contains rows; never drop pgcrypto, platform schemas or cluster roles automatically. Production recovery is forward-fix or reviewed restore, not `downgrade base`. T is the minimum portable checkpoint on PG17: the guarded migration entry point must reject downgrade below T; any T downgrade guard must reject pre-18 execution. Raw Alembic access by owner is a privileged operational escape, not a policy enforcement guarantee. PG18 full empty disposable round-trip can still exercise legacy revisions. Never restore an unsupported native default on PG17. Previous binaries/default-writing code are not compatible rollback targets there.

Only compatible application rollback may occur while retaining U and denial state. Populated data requires backup, rehearsed restore and explicit incident authorization. Do not regenerate IDs, silently delete mappings or automatically restore privileges. Private deletion target within 30 days and C7 backup/suppression obligations remain approved but unimplemented.

## 11. Exact acceptance gates

- [ ] Owner approves the selected bootstrap, schema, disabled-first lifecycle and capability/RLS proposals; explicitly authorizes a bounded implementation slice.
- [ ] Historical migrations remain byte-identical; fresh PG17/PG18 and existing PG18 routes produce the reviewed manifest and accurate revision provenance.
- [ ] Only two tables and necessary integrity/security objects exist; application v7 IDs, exact unique mapping, FK/immutability, timestamps and limits pass real PostgreSQL tests.
- [ ] Duplicate/concurrent/rollback/unknown-commit and cross-user tests pass with real independent sessions and runtime privileges; no email merge or direct client account binding.
- [ ] Role/RLS/definer negative tests pass, no service-role/owner credential used in runtime, no client/Data API access and no secret-bearing errors.
- [ ] All relevant backend tests, Ruff and Mypy pass with actual exits; local and managed checks are labelled separately; blocked/unrun tests remain visible.
- [ ] No destructive populated downgrade, unsupported PG17 historical replay, unapproved bootstrap or unsafe target cleanup is possible through the approved operational path.
- [ ] Before managed/real-user use, project/version/TLS/pool/credentials/operator/backup/retention decisions and applicable authentication gates have evidence-backed closure. No JWT-to-account activation route is inferred from schema acceptance.
- [ ] Final diff preserves unrelated work; owner separately accepts 2B-2. Batch 2B-3 does not start automatically.

## 12. Official evidence ledger and limits

Checked **2026-11-09** through public documentation, not cloud-account access. VERIFIED means documentation/source evidence; proposed DRIP behavior and managed project operation remain untested. Documentation may be newer than the pinned packages; no upgrade was made.

| Ref | Exact source and relevant section | Proves / does not prove |
| --- | --- | --- |
| E1 | [PostgreSQL 18 UUID functions](https://www.postgresql.org/docs/18/functions-uuid.html), generation/extraction | Native v7 exists upstream; not Supabase availability. |
| E2 | [PostgreSQL 17 UUID type](https://www.postgresql.org/docs/17/datatype-uuid.html), storage | Standard UUID storage independent of generating source; not a native v7 function. |
| E3 | [Python 3.14 uuid](https://docs.python.org/3.14/library/uuid.html), uuid7 | Native application generator; not database writer coverage or global ordering. |
| E4 | [Supabase upgrading](https://supabase.com/docs/guides/platform/upgrading), Upgrading to Postgres 17 | Managed version/upgrade considerations; no verified selected project or PG18 offer. |
| E5 | [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html), Building an Up to Date Database from Scratch | Explicit creation plus stamping is supported; not permission to skip checks or a tested DRIP bootstrap. |
| E6 | [SQLAlchemy 2.1 defaults](https://docs.sqlalchemy.org/en/21/core/defaults.html), Python/server/onupdate defaults | Distinguishes Python writes from database defaults; does not make raw SQL execute Python. |
| E7 | [PostgreSQL character types](https://www.postgresql.org/docs/17/datatype-character.html), length/casts | Character versus byte limits and truncation risk; motivates bounded text without normalization. |
| E8 | [PostgreSQL B-tree](https://www.postgresql.org/docs/17/btree.html), Introduction; [unique indexes](https://www.postgresql.org/docs/17/indexes-unique.html) | Page-size constraint and composite uniqueness; actual max-value inserts still require tests. |
| E9 | [PostgreSQL row security](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), default denial/owner/bypass/FORCE | Role semantics; not automatic proof of application identity. |
| E10 | [PostgreSQL CREATE FUNCTION](https://www.postgresql.org/docs/17/sql-createfunction.html), Writing SECURITY DEFINER Functions Safely | Ownership, safe search_path and PUBLIC EXECUTE concerns; not a reviewed DRIP function implementation. |
| E11 | [Supabase securing your API](https://supabase.com/docs/guides/api/securing-your-api), grants/schema exposure | API access must be deliberately restricted; no actual project configuration inspected. |
| E12 | [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres), direct/session/transaction modes | Connection choices and differing pooler capabilities; no selected topology or capacity measurement. |
| E13 | [SQLAlchemy 2.1 asyncpg](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#asyncpg), Prepared Statement Cache | Dialect prepares statements; cache disabling alone is not eliminating prepare calls. Compatibility must be tested with pinned 2.1.4. |
| E14 | [Supabase SSL enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement), SSL modes | Encryption versus certificate/hostname validation; no TLS configuration changed. |
| E15 | [Supabase database backups](https://supabase.com/docs/guides/platform/backups), backups/PITR/restoration | Platform backup mechanisms; no approved DRIP plan, RPO/RTO or completed restore drill. |

## 13. Planning verification

Only this specification and the linked owner-decision document may be created. Inspection consisted of read-only Git/file/hash commands and public official documentation review. No application tests, compilation, Docker queries, migration commands, DB connections or provider operations were run. Document structure/local links, whitespace, index and final hash/status comparison are checked at closeout; results are recorded in the owner-decision document. No implementation is authorized by the presence of these files.
