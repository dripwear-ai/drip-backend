# DRIP Batch 2B-2b — Owner Decisions and Implementation Gates

Date recorded: **2026-11-16** (Asia/Calcutta)
Companion: [database migration and security foundation specification](batch-2b-2b-database-security-spec.md)

This is a new status record. It preserves, and does not rewrite, the earlier [Batch 2B-2 owner-decision register](batch-2b-2-owner-decisions.md). The owner has since explicitly confirmed D01–D04 approved in the Batch 2B-2b authorization. The original file still labels them pending; this document supersedes those status labels for current planning. The approval date for the earlier decisions was not separately provided; 2026-11-16 is this record's date, not an asserted historical approval date.

## 1. Settled decisions — approved

| Decision | Current status | Approved direction and boundary |
| --- | --- | --- |
| **D01 — migration checkpoint** | **APPROVED** | Preserve 0001/0002; retain normal PostgreSQL 18 history; use an explicit, guarded PG17 fresh-database adoption to portable checkpoint T only after verified 0001 effects/provenance. T's approved literal revision ID is `0003_portable_identity_ckpt` (27 characters) in the preserved filename `0003_portable_identity_checkpoint.py`; keep Alembic's default `VARCHAR(32)` version column. Never stamp 0002 or `head` on PG17. Approval does not authorize bypassing verification. |
| **D02 — database authority/security** | **APPROVED** | Private `drip_identity` schema; forced RLS; separated database owner, non-login function executor, controlled migration and runtime roles; restricted runtime functions only; no direct client/platform API role access. Follow the reviewed design in the companion specification. Approval does not establish that Supabase can provision these roles or that they are configured. |
| **D03 — schema and mapping** | **APPROVED** | Exactly two foundation tables; exact `(issuer, subject)` identity key; one external identity per internal user; approved ASCII issuer and UTF-8 subject byte bounds; C collation; restrictive foreign key; immutable identity associations; reviewed timestamps and constraints. This explicitly corrects the stale pending label in the earlier owner-decision document for current planning. |
| **D04 — lifecycle** | **APPROVED** | New mapped users are disabled by default, using the approved `active`, `disabled`, `deletion_pending` vocabulary. Mapping alone grants no private access. No activation endpoint, admin grant, session, or account recovery is included. |

Auth0 remains external identity proof, DRIP UUIDv7 remains the internal identity, and email matching/linking remains prohibited. PostgreSQL is authoritative; Redis remains ephemeral. These are preserved, not reopened here.

## 2. Decisions and evidence still required

| ID / status | Exact owner/environment question | Recommendation / safe default | What remains blocked |
| --- | --- | --- | --- |
| **D05 — PENDING: Supabase target** | Which actual project, owner, region, PostgreSQL major version, encoding, block size, extensions and existing DRIP objects are in scope? Is the target empty of DRIP data/writers? | Do not assume a project exists or is fresh. Supply a sanitized inventory and server evidence; no credentials or full URLs in reports. UTF8 is a mandatory technical precondition for U, not a selectable alternative. | Managed migration/bootstrap and managed acceptance. Unknown objects/data stop all adoption; non-UTF8 stops U before object DDL. |
| **D06 — PENDING: connectivity and limits** | Which runtime/migration connection modes, pooler, verified TLS settings, certificate rotation, process-wide pool budget, connection/statement/lock/transaction deadlines are approved? | Direct verified TLS for persistent runtime if available; session pooling only if required and proven. Do not use shared transaction pooling without pinned SQLAlchemy/asyncpg tests. Choose finite measured limits. | Managed runtime integration, migration operation and exposed persistence. Current pool defaults are not approved production budgets. |
| **D07 — PENDING: operator and credentials** | Who are named migration/runtime credential custodians and operators? How are secrets stored, rotated, revoked and used for break-glass? Who provisions roles and audits access? | Separate least-privilege runtime and migration credentials in an approved secret manager; named individual operators; no credentials in source, `.env` reports, or shared accounts. | Role provisioning, managed bootstrap and deployment. No request for secrets is made here. |
| **D08 — PARTIALLY APPROVED: bounded 2B-2b disposable migration tests** | The owner approved a local PG17 harness and reuse of existing PG18.6 integration infrastructure for this exact migration slice. Wider role/RLS test targets and any managed disposable project remain undecided. | PG17 only: official `postgres:17.12-alpine3.24` pinned by manifest digest, unique Compose project, loopback-only port, tmpfs data, temporary credentials. PG18 only: existing guarded repository Compose target without edits. | **This bounded 2B-2b live-test target is authorized.** Broader role/security and managed tests remain blocked pending separately approved target, concurrency and cleanup details. No PG17 or PG18 execution is implied by this authorization. |
| **D09 — PENDING: identity exposure boundary** | Which verified Auth0 principal types/flows may reach storage mapping, and what C2/C3/C4 checks are required before any registration, activation, or private route? | Keep migration/storage capabilities unrouted; require verified `ExternalPrincipal`; never use client IDs/email; keep users disabled. | API registration/lookup exposure, activation, private-data authorization and admin use. Does not reopen the approved no-link policy. |
| **D10 / C7 — PENDING: backup and lifecycle operations** | What RPO/RTO, backup/PITR, retention, deletion retries, 30-day private-data deletion verification, restoration suppression and accountable recovery authority apply? | No real-user data until values and a disposable restore drill are approved. Recovery is forward-fix/reviewed restore, not populated downgrade. | Production identity records, purge, restore and deletion lifecycle operations. |

## 3. Implementation gates

### Gate 2B-2b: checkpoint and guarded bootstrap

Before implementation: D01 is approved; D08 must approve exact disposable target(s) before any service or database test. D05/D07 evidence is required if bootstrap targets a managed project; otherwise use only a separately approved local disposable target. No target may be inferred from the current Compose file, which is PG18-only.

Acceptance evidence: immutable 0001/0002 hashes; PG17 ordinary replay fails at the historical 0002 without false T/head; successful guarded PG17 route executes 0001, verifies exact effects/provenance, stamps only exact T and produces a matching manifest; PG18 normal replay executes 0001/0002/T; injected failures/interruption/unknown commit never report false success; repeated verified T is no-op; downgrade below T is rejected on PG17. Commands, exits, logs and target attestation are retained without secrets. Owner separately accepts this slice before proceeding.

### Gate 2B-2c: identity and database security migration

Before implementation: 2B-2b accepted; D02–D04 approved (recorded above); concrete role names/ownership/membership, function contracts and target privileges reviewed; D08 disposable role/RLS test infrastructure ready. D05/D06/D07 are required for managed tests or deployment; D09 remains required before API exposure.

Acceptance evidence: U creates exactly the two metadata-matching tables; triggers enforce immutable bindings/timestamps; forced RLS and role capabilities match the approved matrix; runtime has only exact function EXECUTE grants; built-in/public/inherited paths are denied; SECURITY DEFINER ownership/search path/replacement and temp-schema attacks pass; exact lookups and atomic disabled registration pass duplicate/concurrency/rollback/unknown-commit tests on PG17 and PG18; populated downgrade refuses; no email linking, activation, admin, or public API behavior is inferred. Owner separately accepts this slice.

### Managed acceptance / production gate

Requires actual project/version/encoding/region evidence, verified TLS and exact pool topology, named operators and rotated credentials, backup/restore and deletion controls, full disposable security evidence, auth/admin decision closure as applicable, and a separate explicit managed-test/deployment authorization. Approval of these documents is not deployment authorization.

## 4. Preserved history and status note

The earlier owner-decision document's D01–D04 “PENDING” rows and unchecked approval checklist reflect its then-current planning status. This new record updates the current status from the owner's explicit approval; it does not edit that historical document or assert that any migration, role, RLS policy, function, connection, bootstrap, or test has been implemented.

## 5. Approval checklist for future work

- [x] Owner approval recorded for D01–D04.
- [ ] Owner separately authorizes the bounded 2B-2b implementation slice.
- [x] Owner authorized exact local disposable targets and cleanup for bounded 2B-2b live migration tests; broader D08 security/managed infrastructure remains pending.
- [ ] D05/D07 sanitized project and operator evidence is approved before managed bootstrap.
- [ ] 2B-2b migration and recovery acceptance evidence is reviewed and accepted.
- [ ] Owner separately authorizes 2B-2c implementation.
- [ ] D06/D07/D09/D10 gates close before corresponding managed, private-API, or real-user operations.

No implementation, service operation, migration, or database connection occurred while preparing this status record.

## 6. Documentation correction checkpoint — 2026-11-16

This correction clarifies the already approved D02 implementation design; it does not change its approval or close any pending decision. The companion specification now requires executor schema `USAGE`, a transactional function creation/ownership-transfer procedure with temporary executor `CREATE` and temporary SET-only owner-to-executor membership revoked before commit, and runtime isolation from owner/executor membership. It also defines a migration-only, boolean-only emptiness helper compatible with FORCE RLS, separate Alembic/catalog-manifest verification, and UTF8 as a fail-closed U precondition with real PostgreSQL multibyte boundary tests. The actual managed role-administration capability remains unverified and is still within pending D05/D07 evidence.

D01–D04 remain **APPROVED**. D05–D07 and D09–D10 remain **PENDING**. D08 is approved only for the bounded local PG17/PG18 migration tests in the 2B-2b implementation authorization; broader role/security and managed targets remain pending. This correction does not approve a Supabase project, managed encoding result, role provisioning capability, or deployment.

## 7. Bounded 2B-2b implementation checkpoint — 2026-11-16

The owner selected Option 1 for Alembic's 32-character revision storage limit: keep the file `0003_portable_identity_checkpoint.py`, use only revision ID `0003_portable_identity_ckpt`, and do not widen the version column or introduce custom version-table behavior. The owner separately authorized the local PG17 and existing PG18.6 disposable execution described in the implementation instruction. This is a scoped D08 authorization for Batch 2B-2b only; it does not authorize managed targets, roles/RLS tests, or Batch 2B-2c. D05, D06, D07, D09 and D10 remain **PENDING**.
