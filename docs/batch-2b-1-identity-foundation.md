# Batch 2B-1 — Backend identity foundation

Date: 2026-11-01. Scope: owner-authorized identity primitives only. Implementation completed for review; acceptance and Batch 2B-2 remain separate owner gates.

## Architecture and precedence

The owner approved Auth0 for authentication, Supabase PostgreSQL for application data, FastAPI for business logic/authorization, Cloudflare for infrastructure/media, Firebase for mobile support and Redis for ephemeral use only. This supersedes the provider-selection proposal in [Batch 2A.1](batch-2a1-authentication-architecture-resolution.md), not its unresolved deployment/security details. Earlier Supabase Auth/Cognito statements in historical records were not rewritten.

Reviewed the infrastructure realignment, Batch 2A compatibility report, Batch 2A.1 resolution, P2-A readiness audit, P2-0 contracts, backend configuration/errors/logging/tests, Python/TypeScript configuration and UUID migrations. No applicable AGENTS.md or separately named constitution was found by the scoped instruction search; existing ADR/engineering constraints apply. The latest authorization permits these offline primitives without choosing founder identities, sessions, admin assurance, cloud projects or database bootstrap.

Initial Git state: `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`; **37 modified tracked, 127 untracked individual files, zero staged**. The eight implementation/test paths and this report were absent before creation. A SHA-256 baseline covers 155 existing Git-visible regular files, excluding `.gradle/` and `.idea/` caches. Existing generated/ignored artifacts are not included in that checksum claim.

Existing unused `JWT_ALGORITHM=HS256` and lifetime settings are not reused or changed. Existing database `uuidv7()` defaults and migration 0002's PostgreSQL 18 assertion remain unchanged. A native Python UUID generator does not resolve that migration gate.

## Implemented files

All nine files are new; no existing user file was edited.

| File | Responsibility |
| --- | --- |
| [identity/__init__.py](../apps/api/src/drip/identity/__init__.py) | Module boundary; no startup configuration or connections. |
| [identity/config.py](../apps/api/src/drip/identity/config.py) | Explicit immutable Auth0 verifier configuration with fixed, redacted validation failures. |
| [identity/contracts.py](../apps/api/src/drip/identity/contracts.py) | Distinct internal ID, external identity, authentication context, principal and future authorization-context types. |
| [identity/verifier.py](../apps/api/src/drip/identity/verifier.py) | Signed access-JWT verification, bounded JWKS transport/cache and sanitized failure. |
| [identity/dependencies.py](../apps/api/src/drip/identity/dependencies.py) | Opt-in synchronous FastAPI dependency factory; no route added or mounted. |
| [core/identifiers.py](../apps/api/src/drip/core/identifiers.py) | Native Python `uuid.uuid7()` wrapper returning a UUID object. |
| [test_identity_foundation.py](../apps/api/tests/test_identity_foundation.py) | 33 configuration, contract and UUID regression cases. |
| [test_auth0_verifier.py](../apps/api/tests/test_auth0_verifier.py) | 70 token, JWKS/cache/transport, redaction and isolated FastAPI dependency cases. |
| This report | Implemented boundary, settings, actual verification and deferred work. |

## Token verification flow and security boundary

1. A future explicitly wired caller constructs `Auth0VerifierConfig` and a reusable `Auth0TokenVerifier`. Neither construction nor import fetches keys. Configuration is not implicitly read from global settings, environment or dotenv.
2. The optional dependency accepts exactly one Authorization header with a Bearer credential. Missing, duplicate, malformed or other schemes fail. The synchronous dependency runs in FastAPI's threadpool when used through dependency injection. An async caller invoking `verify()` directly must offload its blocking transport itself.
3. Before key lookup, enforce a 16,384-character ASCII compact-JWT limit, three nonempty base64url segments, unambiguous JSON, explicit RS256 algorithm, and bounded nonempty `kid`. Reject remote/injected key headers (`jku`, `jwk`, `x5u`), unsupported critical/b64 extensions and unexpected `typ`. Unverified claims are parsed only to reject malformed/duplicate JSON, never to establish identity or select a network destination.
4. Derive the JWKS endpoint exclusively from trusted issuer configuration. TLS certificate/hostname validation remains enabled. Redirects and environment-proxy discovery are disabled. Limit response to 65,536 bytes and 32 keys; reject duplicate key IDs, malformed sets, private RSA material and RSA keys outside 2048–8192 bits. Only RSA signing/verification keys compatible with RS256 are eligible; unsupported encryption/algorithm keys cannot authorize a token.
5. Verify the signature with the selected trusted public key using installed PyJWT/cryptography. Require `iss`, `aud`, `sub`, `exp`; validate exact issuer, intended audience membership, expiration, and `nbf`/`iat` when present. This foundation accepts nonnegative integer NumericDate values only, not booleans, strings or fractional values. Audiences may be a string or a list of strings. Subject must be a nonblank string of at most 1024 characters; preserve its exact value without trimming/case-folding.
6. Return an `ExternalPrincipal` containing provider, issuer, exact subject and verified audience/time context. Ignore email, provider roles and arbitrary claims. No internal user ID, permission, session, grant, MFA or recovery approval is inferred.
7. Rejections raise the fixed `AuthenticationFailed` domain exception: status 401, code `AUTHENTICATION_FAILED`, message `Authentication could not be verified.` The existing DRIP error handler produces its standard envelope and empty details. Provider/network/crypto exception messages and chained traces are suppressed. The verifier emits no logs and retains no bearer-token cache. Callers must not log inputs or captured locals.

The configured audience must be the **DRIP API identifier**, not an OAuth client ID or a third-party API. Issuer/audience selection remains operationally unconfigured. No local implementation can prove a tenant's token profile or distinguish an intentionally misconfigured audience by looking at an otherwise valid signature. ID tokens/Google API tokens are not approved DRIP API credentials. Their wrong issuer/audience must fail under the correctly configured verifier; real tenant acceptance remains deferred.

## JWKS cache and configuration contract

| Field / limit | Implemented behavior |
| --- | --- |
| `issuer` | Required canonical lowercase HTTPS DNS origin ending in `/`; no path, port, user-info, query, fragment, whitespace, encoded host or IP literal. No issuer normalization. Custom Auth0 DNS domains are possible after owner configuration review. |
| `audience` | Required nonempty printable ASCII API identifier, maximum 512 characters; no whitespace/control characters. |
| `algorithms` | Explicit allowlist `("RS256",)` only in this batch. HS256, unsigned, empty or broader lists fail configuration validation. Other algorithms require a separately reviewed extension, not automatic header negotiation. |
| `jwks_url` | Read-only derived value: issuer plus `.well-known/jwks.json`. No independent endpoint override or token-controlled URL. |
| `leeway_seconds` | Default 0, accepted integer range 0–60. This is JWT clock tolerance, not a decision on idle/session lifetime. |
| `jwks_ttl_seconds` | Default 300, accepted range 30–3600; per-verifier monotonic-clock cache. No indefinite per-key cache. |
| `refresh_cooldown_seconds` | Default 30, range 1–60 and not greater than TTL; limits refresh attempts including unknown-kid and failed-fetch requests. |
| `timeout_seconds` | Default 3, integer range 1–10; urllib socket/connect/read timeout. It is **not** a guaranteed total request/DNS deadline. Deployment-level deadlines/concurrency/egress controls remain a later integration responsibility. |

Documentation-only placeholder: `Auth0VerifierConfig(issuer="https://configured-tenant.invalid/", audience="DRIP_API_IDENTIFIER")`. `.invalid` is not a configured tenant and must not be used for deployment. No Auth0 environment variable reader, tenant secret, client secret or `.env` entry is introduced. A later composition layer must supply owner-approved values and instantiate one verifier per trusted issuer/audience configuration; do not mutate an existing verifier's configuration or share its cache across realms.

A lock serializes cache refresh. A fresh known key can verify without network access. An unknown key may refresh once the cooldown permits; during cooldown it fails closed. A successful refresh replaces the snapshot, removing retired keys. Failed refresh clears keys rather than serving stale results. On TTL expiry even a known `kid` must refresh; this handles key material changes under a reused ID at the TTL boundary. Signature failures alone do not force refresh, avoiding an unbounded invalid-signature request loop.

Limits: cached keys may remain usable until TTL expires; this is **not immediate provider key revocation or DRIP session revocation**. A newly rotated key may be denied for the cooldown window. Unknown-key abuse can cause bounded fetch attempts and temporary denial on a failed refresh; endpoint rate limits are still needed before deployment. The cooldown/lock is per process, not a distributed limiter. No Redis state was added. The default transport is wired but tested with doubles, not a real tenant/TLS server.

## Identity abstraction and UUIDv7

`InternalUserId` wraps a Python UUID and rejects provider-subject strings. `ExternalIdentity` is a separate immutable provider/issuer/subject value without an email field. `AuthenticationContext` contains token facts only. `ExternalPrincipal` requires external identity/context, not an optional anonymous value. The HTTP dependency rejects guests rather than manufacturing a principal. These are trusted Python internal contracts, not a sandbox against arbitrary in-process code and not models accepting client JSON.

`AuthorizationContext` holds an internal user ID and an immutable permission set, empty by default. No service constructs it from JWT claims or enforces it yet. Future mapping must use a unique `(issuer, subject)` binding to a stable DRIP UUID; application foreign keys use the internal ID. Email never chooses that binding. Provider migration/recovery must prove identity ownership and preserve the internal ID under a separately approved procedure. No identity record, automatic association or linking operation exists in this batch.

`new_uuid7()` calls the Python 3.14 standard library and returns a standard UUID. There is no UUIDv4 fallback and no new UUID package. Tests inspect version and RFC variant bits, generate 2,048 unique values and round-trip through JSON strings. This sample is a regression check, not a mathematical uniqueness proof or global transaction-order guarantee. The utility is intentionally not connected to current ORM defaults or migrations.

No TypeScript identity wire contract is added because no identity endpoint/response is approved here. Existing shared consumers/exports remain unchanged; the existing TypeScript exact-money compile-time regression was run to check preservation.

## Verification evidence

Existing environment: Python **3.14.7**, PyJWT **2.15.1**, cryptography **50.0.2**, FastAPI **0.143.0**, pytest **9.1.1**, Ruff **0.17.0**, Mypy **2.4.0**. No dependency or lockfile change was required. Node's current runtime-cache path reported 24.22.1 during inspection; the already installed `codex-primary-runtime.previous-a436b125-7c66-4b09-97dd-2f8da95a73da/dependencies/node/bin` was then selected, confirming **Node 24.19.0** and **pnpm 9.15.9**. No runtime was installed/upgraded.

Working directory for commands below: repository root. Package-script checks used the pinned Node path, existing roaming pnpm and process-only `UV_OFFLINE=1`; `uv run --locked --extra dev` used the existing environment. Tests used pytest's existing exact `not integration` selection and target guard. Synthetic keys are generated only in tests and never persisted. JWKS responses/clock are mocked; new verifier tests prohibit DNS/socket connection attempts. Asyncio's own Windows socket pair is local test-runner machinery, not database/provider access.

| Command / attempt | Actual exit and outcome |
| --- | --- |
| `apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml apps/api/tests/test_identity_foundation.py apps/api/tests/test_auth0_verifier.py` — first sandbox attempt | Interrupted, exit 1; 98 collected, no completed result. Stalled during asyncio fixture setup. Not a passing test run. |
| `apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml apps/api/tests/test_identity_foundation.py -x -vv -o faulthandler_timeout=20` — diagnostic | Interrupted, exit 1; traceback showed Windows `_fallback_socketpair` waiting in `accept` during event-loop initialization, before the first test. |
| `apps/api/.venv/Scripts/python.exe -c "import time, uuid; start=time.monotonic(); values=[uuid.uuid7() for _ in range(2048)]; print(len(values),time.monotonic()-start,flush=True)"` | Exit 0; 2,048 generated in approximately 0.005 seconds; diagnostic only. |
| Initial direct Ruff/Mypy inspection of the new source/tests | Ruff reported two test-style findings (import order and Depends default), subsequently fixed; individual Ruff exit was not captured because the combined shell command ended with successful Mypy. Mypy reported success in six source files, combined shell exit 0. Not recorded as an initial Ruff pass. |
| `apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml apps/api/src/drip/identity apps/api/src/drip/core/identifiers.py apps/api/tests/test_identity_foundation.py apps/api/tests/test_auth0_verifier.py` — after fixes | Exit 0. |
| Focused pytest command above plus `-o faulthandler_timeout=30`, outside sandbox restriction | Exit 0; initial 98 passed. After adding cache/transport/positive-dependency boundary cases, final rerun **103 passed in 3.89s**. |
| `apps/api/.venv/Scripts/python.exe -m ruff format apps/api/src/drip/identity apps/api/src/drip/core/identifiers.py apps/api/tests/test_identity_foundation.py apps/api/tests/test_auth0_verifier.py` | Exit 0; only new files formatted (4 reformatted, 4 unchanged). |
| `pnpm lint:api` and `pnpm type-check:api` — first sandbox attempts | Each exit 2: uv interpreter-cache persistence permission error. No successful lint/type result claimed for those attempts. |
| `pnpm test` — outside sandbox restriction | **Exit 0; 351 passed, 5 live integration tests deselected, 28.57s.** |
| `pnpm lint:api` — retry outside sandbox restriction | **Exit 0; all checks passed**, including application, tests, migrations and scripts. |
| `pnpm type-check:api` — retry outside sandbox restriction | **Exit 0; no issues in 22 source files.** |
| `pnpm exec tsc --ignoreConfig --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext packages/shared-types/tests/money.test.ts` | **Exit 0**; existing compile-time regression. No emitted artifact or new TypeScript runner. |

The permission-approved retries address sandbox execution restrictions; they do not relax validation or connect to services. An initial `rg` inspection using a Windows `docs/batch*` path reported an invalid-path diagnostic; subsequent explicit/scoped reads supplied the documents. It was not a test failure or evidence of a missing report.

Coverage includes valid tokens, bad signatures, wrong/missing issuer/audience/subject/expiry, future nbf/iat, invalid NumericDate types, absent/unknown key IDs, unsigned/symmetric algorithms, ambiguous JSON/headers/JWKS, bounded response/key sizes, unavailable JWKS, rotation, TTL/cooldown/concurrent refresh, safe errors/logs, guest denial, duplicate headers, same-email distinct subjects, contract immutability and UUID generation/serialization. Test-only FastAPI routes exist only inside the isolated tests.

Live Auth0, Supabase, PostgreSQL/Redis integration, native/device checks, frontend builds and clean-environment rebuild: **NOT RUN** in this bounded backend batch. Docker availability was not probed because no live test/infrastructure execution was needed or authorized. Passing offline tests does not verify actual tenant claims, deployed TLS/DNS behavior, roles, RLS, MFA, session revocation or cloud configuration.

## Deferred functionality and remaining approvals

This is **not complete login, session persistence, identity linking, account recovery or admin authentication**. No existing route's access policy changed. Public browsing remains outside this unmounted dependency; permanent wishlist authorization still requires a later internal mapping/session/ownership service.

Still required before integration: actual tenant/Google clients, issuer/API audience and realm selection; admin MFA/enrollment/recovery/freshness; named founder accounts/bootstrap/authority; C4 session custody, hard seven-day/idle enforcement, refresh/logout/revocation; C6 recovery/abuse controls; C7 audit/deletion/backup lifecycle; Supabase roles/RLS/project/version and UUID bootstrap; native credential/redirect acceptance. Auth0 provider choice is now approved, but these mechanics are not closed by this batch. No cloud, Redis/worker, media, Firebase or frontend integration occurred.

## Official compatibility references

Checked 2026-11-01: [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html) (explicit algorithm allowlist, claim requirements/verification), [PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html) (RSA/cryptography and claim validation), [Auth0 access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens) (API audience, signatures and standard checks), [Python 3.14 UUID](https://docs.python.org/3.14/library/uuid.html) (`uuid7`). These support primitive compatibility, not deployed DRIP authorization or provider configuration. Earlier architecture decisions and security obligations remain in [Batch 2A.1](batch-2a1-authentication-architecture-resolution.md) and [P2-0](p2-0-contracts-and-acceptance.md).

## Final preservation check

Final SHA-256 comparison: **all 155 baseline files unchanged**, exactly the nine additions listed above, no baseline file removed. Final branch `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`; **37 modified tracked, 136 untracked individual files, zero staged**. The untracked increase from 127 is exactly this batch's nine files.

`git diff --check` and `git diff --cached --exit-code` both exited 0; the latter confirms the empty index. Git emitted existing LF/CRLF advisories, not diff-check failures. The nine untracked additions received a separate whitespace/conflict check because ordinary `git diff --check` does not include them. Report link/structure checks exited 0: 11 local links exist and four source URLs are valid HTTPS references reviewed above. The final source/report additions were reviewed for scope, secrets and unrelated behavior; no existing tracked diff was rewritten.

Test caches/generated runner output are not treated as source edits or claimed byte-identical. No dependency, manifest, lockfile, migration, database default, environment file, frontend or existing API file changed. Nothing was staged or committed; no service/database/cloud operation occurred. This completes only Batch 2B-1 for owner review; Batch 2B-2 has not begun.
