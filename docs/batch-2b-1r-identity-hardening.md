# Batch 2B-1R — Identity foundation hardening

Date: 2026-11-02. Owner-authorized offline hardening of Batch 2B-1. Implemented and tested for owner review; this is not acceptance of Batch 2B-2 or complete authentication.

## Scope and preservation baseline

Reviewed [Batch 2B-1](batch-2b-1-identity-foundation.md), its identity configuration, verifier, FastAPI dependency and tests, backend scripts/conventions and existing engineering constraints. No applicable AGENTS.md or separately named constitution was found in the scoped repository instruction search. Earlier architecture/approval records remain historical; this report supersedes the earlier cache/transport behavior description only.

Initial branch `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`: **37 modified tracked, 136 untracked individual files, zero staged**. SHA-256 baseline: 164 existing Git-visible regular files, excluding `.gradle/` and `.idea/` caches. The report path was absent. Existing source, manifests, lockfiles, migrations, environment files and unrelated documentation were treated as user-owned work.

## Findings and implemented changes

| Finding | Correction | Evidence |
| --- | --- | --- |
| Failed unknown-key refresh discarded an otherwise fresh verified snapshot. | Preserve it only until its original expiry; failures never extend expiry. Unknown keys still fail. | Flood/outage/expiry/recovery tests. |
| Cache lock covered network I/O; concurrent callers could queue behind a stalled refresh. | One in-flight refresh per verifier; I/O outside the lock. Fresh known keys remain usable; other concurrent callers fail immediately. | Cold and warm concurrent flood tests with a blocked mock fetch. |
| Socket timeout was not an overall DNS/connect/read deadline. | Isolate fetch in a killable standard-library helper process; parent enforces a monotonic response deadline, with bounded process capacity. | Deadline, late response, startup, capacity, cleanup and real sleeping-helper tests. Platform caveat below remains. |
| Token `typ` handling did not select a single Auth0 profile explicitly. | Add immutable `token_profile`, default `auth0`; require its exact header/claims. No automatic profile negotiation. | Profile/ID-token-audience tests. |
| Permissive whitespace splitting accepted malformed bearer headers. | Require one bounded Authorization header with Bearer scheme and one compact JWT; reject tabs, CR/LF, surrounding whitespace, combined credentials and duplicates. | Dependency and existing API-envelope tests. |

No external identity mapping, authorization grant, user persistence, refresh/revocation service or route integration was added. Existing identity contracts and UUIDv7 utility remain unchanged.

## Cache security and availability policy

The verifier must be reused per trusted issuer/audience/profile configuration. Its immutable configuration is exposed read-only; callers must not reconstruct one per incoming request. These limits are not a distributed abuse-control system.

| Situation | Policy |
| --- | --- |
| Fresh known `kid` | Use the verified snapshot without I/O, including while another refresh is running. |
| Unknown `kid` | Never use another key. Attempt one refresh only when no refresh is running and cooldown has elapsed; otherwise reject. No per-attacker-kid negative-cache entries accumulate. |
| Concurrent cold/unknown requests | Fail fast during the single refresh; no blocking network wait queue in the cache. Clients may retry later through future approved abuse controls. |
| Successful refresh | Atomically replace the whole eligible key set, removing retired keys. TTL starts at refresh initiation, not after delayed I/O. |
| Failed refresh | Retain the previous snapshot and its original expiry; record attempt completion and release the in-flight flag. Subsequent retries can recover after cooldown. |
| Expiry | Never use an expired snapshot as fallback. Refresh must succeed before verifying with a key from that snapshot again. |
| Signature failure with known key | Reject without forced refresh. Reused-key-ID material changes are picked up on expiry, not on each attacker signature. |

Defaults remain TTL **300 seconds**, retry cooldown **30 seconds**, request timeout **3 seconds**, clock leeway **0**. Existing accepted bounds remain TTL 30–3600, cooldown 1–60 (at most TTL), timeout 1–10, leeway 0–60. Cooldown is measured from completion of every refresh attempt, including failure and successful fetch without the requested key. Thus the ordinary per-verifier refresh rate is at most one attempt per cooldown, plus fetch time. An attacker can delay a new key by triggering a preceding attempt, but cannot authorize an unknown key or extend a failed snapshot.

Availability trade-off: an outage preserves valid known-key service only for the remaining original TTL. After expiry, authentication fails closed until a successful retry. A successful response is authoritative even if it removes a previously known key. Cached key revocation is bounded by configured TTL for new key lookups, not immediate; in-flight verification is not cancelled. This is not DRIP administrative/session revocation. Application-level immediate denial and in-flight authorization behavior remain separately gated.

## Transport boundary and remaining deadline limitation

`jwks_transport.py` uses only the standard library. The previous urllib socket timeout remains a secondary per-operation timeout inside the helper; it is no longer relied on as the sole request deadline.

1. Permit at most **two helper processes per API process**, using a module-level nonblocking semaphore. Exhausted capacity fails closed immediately; there is no helper queue. Multi-worker deployments multiply this cap and require a reviewed process count/egress budget.
2. Start the same installed Python executable with isolated mode (`-I`), a fixed local worker script, no shell and a hidden window on Windows. Pass only the derived public JWKS URL and timeout over stdin. Only `SystemRoot`/`WINDIR`, when present, are inherited; application secrets, bearer tokens and environment-proxy credentials are not passed. Worker stderr is discarded and failures are sanitized.
3. Derive the HTTPS URL exclusively from trusted issuer configuration; the worker also validates its restricted endpoint shape. Token `jku`, `jwk`, `x5u` and unsupported critical extensions remain rejected before fetch. No header can choose a URL.
4. Use the default verified TLS context (certificate validation and hostname checking), explicit empty proxy handler, no redirects, HTTP 200 only and no compressed body. Bound the body to **65,536 bytes**; reject invalid/oversized Content-Length and observed length mismatches. The verifier separately bounds the set to 32 keys and validates eligible public RSA material.
5. Establish a monotonic deadline before process creation. Give `communicate()` only the remaining time. Reject output arriving at/after the deadline. On timeout/error, kill an active helper and wait up to 0.25 seconds for cleanup. Slow DNS, TLS, reads or incomplete bodies occur inside this disposable child, not an indefinitely running request thread.
6. If exit cannot be confirmed promptly, retain its capacity slot and use a daemon reaper. Capacity is released only after confirmed exit. At most two such children/reapers can exist; an unconfirmed OS wait failure retains the slot rather than risking additional connections. Ordinary timeouts/startup failures recover without permanently poisoning verifier/cache state.

**Not a hard real-time guarantee:** Python/OS process creation cannot be interrupted on all platforms; process termination, pipe cleanup and OS scheduling also lack a universal wall-clock guarantee. Elapsed startup is charged to the deadline and late output is rejected, but this does not promise that every caller returns within exactly `timeout_seconds`. The implementation bounds ordinary network work and capacity, not a malfunctioning operating system. Tests verify a real local sleeping child is killed; they do not establish production DNS/TLS or host scheduling guarantees.

If deployment requires a strict externally enforced request SLA, evaluate a separately supervised key-fetch process/service with bounded local IPC and host/container resource supervision, or a reviewed async transport with demonstrable resolver cancellation and process supervision. That is a deployment/design gate, not an implemented service or an excuse to claim urllib alone solves total deadlines. No new dependency was needed here; adding a transport library still requires owner approval.

The subprocess model adds startup cost on cold/refresh requests and requires an installed readable worker module, executable Python, outbound HTTPS trust roots and permission to create child processes. Confirm these on the selected hosting platform before wiring routes. Injected fetchers are trusted test/application code; arbitrary custom synchronous fetchers do not inherit the default transport's deadline/capacity controls.

## Explicit access-token profile

Auth0 documents two access-token dialect families. This implementation selects one, never either implicitly:

| Configuration | Accepted header and claims |
| --- | --- |
| `token_profile="auth0"` (default) | Exact `typ="JWT"`; require `iss`, API `aud`, `sub`, `exp`. `nbf` and `iat` are optional but validated when present. |
| `token_profile="rfc9068"` | Exact `typ="at+jwt"`; additionally require `iat`, nonblank `client_id` and `jti`. |

Both require RS256, verified signature, exact configured issuer and intended API audience membership. NumericDate values are nonnegative integers; expiry and future `nbf`/`iat` fail subject to configured leeway. Present `azp`, `client_id` and `jti` must be nonblank strings. Duplicate JSON members, malformed headers and missing type are rejected. This is a deliberately restricted accepted profile, not acceptance of arbitrary JWTs or every possible RFC extension.

The audience must be the DRIP **API identifier**, never the OAuth client ID. Default-profile ID/access tokens can share `typ="JWT"`; the header alone cannot distinguish them. Correct API issuer/audience configuration is mandatory and ID-token client audiences fail the regression test. No tenant-specific claim or real configuration was invented. Confirm actual tenant dialect and an offline sanitized token-claim contract before integration. Provider subjects can represent applications as well as people; this verifier proves an external subject, not a customer/admin identity. Future identity mapping must restrict acceptable flows and subjects rather than infer human status, roles, MFA or ownership from a signed token. [Auth0 profile documentation](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles) and [access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens) support these distinctions.

## Changed-file inventory

Four pre-existing files edited within the authorized identity scope:

- [config.py](../apps/api/src/drip/identity/config.py): explicit validated token profile.
- [dependencies.py](../apps/api/src/drip/identity/dependencies.py): strict bounded bearer-header grammar.
- [verifier.py](../apps/api/src/drip/identity/verifier.py): single-flight cache policy, transport delegation, read-only configuration binding and token-profile validation.
- [test_auth0_verifier.py](../apps/api/tests/test_auth0_verifier.py): 33 additional cases; adapt existing transport test to the worker and warm-cache concurrency test to the documented fail-fast cold behavior. Duplicate/header tests retain valid surrounding fields so rejection exercises the intended condition.

Three new files:

- [jwks_transport.py](../apps/api/src/drip/identity/jwks_transport.py): isolated bounded transport.
- [test_jwks_transport.py](../apps/api/tests/test_jwks_transport.py): 21 offline transport cases.
- This report.

## Verification performed in this batch

Python **3.14.7**, Node **24.19.0**, pnpm **9.15.9** confirmed. No install/upgrade or dependency change. Package commands use process-only `UV_OFFLINE=1` and the existing pinned Node path, with the repository's locked uv environment. Tests use the existing non-live selection and disposable-target guard. Known Windows asyncio/uv sandbox restrictions from Batch 2B-1 were handled through approved outside-sandbox execution; those historical failures are not claimed as new attempts. No fresh sandbox test attempt failed in this batch.

Working directory: repository root. Exact setup for package commands:

```powershell
$env:PATH='C:\Users\batla\AppData\Roaming\npm;C:\Users\batla\.cache\codex-runtimes\codex-primary-runtime.previous-a436b125-7c66-4b09-97dd-2f8da95a73da\dependencies\node\bin;'+$env:PATH
$env:UV_OFFLINE='1'
```

| Command | Actual exit / result |
| --- | --- |
| `apps/api/.venv/Scripts/python.exe -m ruff check --fix apps/api/src/drip/identity/config.py apps/api/src/drip/identity/dependencies.py apps/api/src/drip/identity/verifier.py apps/api/src/drip/identity/jwks_transport.py apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py` | 0; three style findings fixed using inferred configuration. This was not the final repository lint result. |
| `apps/api/.venv/Scripts/python.exe -m ruff format apps/api/src/drip/identity/config.py apps/api/src/drip/identity/dependencies.py apps/api/src/drip/identity/verifier.py apps/api/src/drip/identity/jwks_transport.py apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py` | 0; five files formatted, one unchanged. |
| `apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml apps/api/tests/test_identity_foundation.py apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py -o faulthandler_timeout=30` | **0; 157 passed in 7.33s** (33 foundation, 103 verifier/dependency, 21 transport). |
| `pnpm test` | **0; 405 passed, 5 live tests deselected in 38.81s**. Includes existing UUID, money, errors, configuration, target guards and non-live migration regressions. |
| `pnpm lint:api` — first attempt | **1; two import-order findings** in the two touched test modules. Inferred Ruff config differed from the root script's explicit config. Not a pass. |
| `apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml --fix apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py` | 0; two import-order findings fixed. No behavior changed. |
| `pnpm lint:api` — retry | **0; all checks passed**, including application, tests, migrations and scripts. |
| `pnpm type-check:api` | **0; Mypy passed all 23 source files**. |

Fifty-four focused cases were added relative to the previous batch's 103. Tests cover unknown-key flooding, concurrent cold/warm refresh, repeated outages/recovery, original expiry, delayed refresh TTL/cooldown, rotation/retired keys, profile requirements, ID-token audience, malformed/duplicate headers, redaction, worker deadline/capacity/cleanup, late output, incomplete/oversized bodies, redirects/proxy/TLS settings and unauthorized destinations. Only ephemeral test RSA keys and local mocks are used. The real subprocess test sleeps without networking and confirms its child exited. Asyncio local socket-pair machinery is not provider/database access.

Live Auth0/Supabase, real TLS/DNS and deployment-process behavior, PostgreSQL/Redis integration, browser/native checks, TypeScript checks and clean rebuild: **NOT RUN**. No shared TypeScript contract changed. No Docker probe or service startup was necessary. Tests do not prove tenant configuration, production transport behavior or session revocation.

## Batch 2B-2 acceptance gates and limitations

Before the next batch, require separate owner acceptance/authorization and:

1. Approved scope and actual issuer/API audience/profile/allowed authentication flows; evidence that ID tokens and non-customer principals cannot be promoted to DRIP accounts. Keep no automatic email linking.
2. Reusable verifier composition, process count/capacity/rate controls and supported hosting transport. Verify deadline/cleanup/TLS behavior on the deployment OS in an authorized isolated environment; do not claim a universal hard deadline.
3. Explicit database/version/UUID bootstrap and forward-only migration approval. Existing PostgreSQL 18 assertion/defaults are untouched; passing non-live migration tests is not a managed database acceptance result.
4. Approved identity mapping `(issuer, subject)` to stable internal UUIDs with uniqueness/account isolation tests; owner-approved transactional creation and recovery/linking rules. Never use email as the mapping key.
5. Applicable C1–C7/D3 closure: founder designation/bootstrap, admin assurance and emergency procedure, session/revocation/idle policy, recovery and audit/deletion lifecycle. This verifier grants none of these authorities.
6. Tests proving guest/public boundaries, authenticated ownership and fail-closed mapping/authorization. Do not infer application access from JWT validity alone or bypass outstanding policy gates to wire routes.

## Sources and evidence limits

Checked 2026-11-02 using official documentation only:

- [Auth0 Access Token Profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles), profile/token-format comparison: documents dialects, headers and claims, not this project's tenant settings.
- [Auth0 Validate Access Tokens](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens), standard validation and audience: requires API-directed proof; DRIP permissions remain application responsibilities.
- [Python 3.14 subprocess](https://docs.python.org/3.14/library/subprocess.html), `Popen.communicate`, timeout handling and process creation caveat: supports isolated deadline/kill strategy, not hard real-time OS guarantees.
- [Python 3.14 urllib.request](https://docs.python.org/3.14/library/urllib.request.html), timeout, HTTPS and handler APIs: blocking-operation timeout is not an aggregate request deadline.

## Final preservation and stop condition

Final branch `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`, unchanged. Final inventory: **37 modified tracked, 139 untracked individual files, zero staged**. Relative to this task's baseline, exactly the four authorized existing files above changed, the three listed files were added and no baseline file was removed. **All 160 other baseline-hashed files remain byte-identical**, including manifests/lockfiles, migrations, environment/configuration files, existing frontend work and historical reports. Existing tracked diff remains 37 files, 1,613 insertions and 1,736 deletions; this task's identity files were already untracked, so ordinary Git diff does not display their edits. Their current contents, tests and baseline hashes were reviewed separately.

`git diff --check` exited **0** (existing LF/CRLF advisories only); `git diff --cached --exit-code` exited **0**. An inline read-only Python documentation check exited **0**: heading/fence structure, seven existing local links and six HTTPS reference occurrences validated. All seven touched files passed an additional trailing-whitespace/conflict-marker check, covering untracked additions that ordinary Git diff omits. The four distinct official source URLs were opened during research; this is not provider connectivity testing.

Ignored/generated test caches and the excluded `.gradle/`/`.idea/` caches are not covered by the byte-identity claim. No source/dependency/migration/environment/frontend file outside the four authorized edits changed in the baseline comparison. No provider, database, cloud or service operation occurred. Local helper processes were used only by offline tests. No prior report was rewritten to imply these checks were performed in Batch 2B-1. All work remains uncommitted and unstaged; Batch 2B-2 has not begun.

## Owner-review correction and fresh final verification — 2026-11-02

The owner requested the explicit parenthesized exception tuple at line 116 of `jwks_transport.py`: `except (OSError, subprocess.TimeoutExpired):`. Only that source line was changed; no formatter or autofix was run afterward. A local compile probe of the prior unparenthesized form exited 0 on pinned Python 3.14.7, so the previous form was not a syntax failure on this project's runtime. The requested explicit tuple is now retained. The preceding verification remains historical; the following fresh results apply to the corrected final source.

Correction-start inventory: `main` at `341a6b031a6eda018d0b3df88f2baca5f88fbe94`, 37 modified tracked files, 139 untracked individual files, zero staged. All 192 Git-visible regular files were hashed for this correction, including the .gradle/.idea files excluded from the original batch's narrower baseline. Ignored generated caches/bytecode remain outside that claim.

Using the same pinned toolchain and offline package-command setup documented above:

| Exact command | Exit | Fresh result |
| --- | --- | --- |
| `apps/api/.venv/Scripts/python.exe -m py_compile apps/api/src/drip/identity/config.py apps/api/src/drip/identity/dependencies.py apps/api/src/drip/identity/verifier.py apps/api/src/drip/identity/jwks_transport.py apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py` | 0 | All six source/test files compiled. |
| `apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml apps/api/tests/test_identity_foundation.py apps/api/tests/test_auth0_verifier.py apps/api/tests/test_jwks_transport.py -o faulthandler_timeout=30` | 0 | 157 passed in 3.40s. |
| `pnpm test` | 0 | 405 passed, 5 live tests deselected in 28.71s. |
| `pnpm lint:api` | 0 | All checks passed; no source rewrites. |
| `pnpm type-check:api` | 0 | Mypy passed 23 source files. |
| `git -c core.safecrlf=false diff --check` | 0 | Whitespace check passed; per-command line-ending warning control only, no Git configuration edit. |
| `git diff --cached --exit-code` | 0 | Index empty. |

No failed verification attempt occurred in this correction run. Checks used approved outside-sandbox execution where required by the already documented Windows runner restrictions. No dependencies, provider configuration or real network/database services were involved.

The following SHA-256 hashes identify the six compiled and freshly tested source/test files. They were captured immediately after compilation and must match at closeout; only this report is edited after verification.

| Final source/test file | SHA-256 |
| --- | --- |
| `apps/api/src/drip/identity/config.py` | `cb18e3c521644e3573676cdea3c4bfb35007a9635fb0ec3bbe592394127b4c53` |
| `apps/api/src/drip/identity/dependencies.py` | `ece7f0550467bc9ea6ae42be53ecf02d6c5584ef192ddcaa30976af08fbc5179` |
| `apps/api/src/drip/identity/verifier.py` | `6db877d876bc9f7877c92a61de27e4788d355c8f3b34b7a767f46d776347a713` |
| `apps/api/src/drip/identity/jwks_transport.py` | `864eeb523d25b3346d2da7c3deb67df6c949b4437e6d8d5612c761409378fbdb` |
| `apps/api/tests/test_auth0_verifier.py` | `a9ba8f15d15ecf9c458cf117dc913b969dfea4b21c5bbe251238c0d72db8c6ec` |
| `apps/api/tests/test_jwks_transport.py` | `80f03e746e486fbbb4493561e0693258125747c9ca04258e07d3b3f0ebf2cfda` |

The seven-file Batch 2B-1R inventory remains the four identity source files, two tests and this report listed above. Within this correction run, only `apps/api/src/drip/identity/jwks_transport.py` and this report changed; no files were added or removed. The transport content equals its correction-start content with exactly the requested one-line replacement. All six compiled/tested hashes match the final on-disk files. All 190 other correction-baseline files are byte-identical; all 160 unrelated files from the original batch baseline also remain unchanged. Report links/structure/whitespace validation exited 0.

Final Git state remains `main` at `341a6b031a6eda018d0b3df88f2baca5f88fbe94`: **37 modified tracked, 139 untracked, zero staged**. Nothing was committed, no service/database/provider operation occurred, and no unrelated source, test, dependency, migration or configuration was modified. Python compilation/test caches are generated artifacts, not source changes. These results identify the final local files; no separate upload or deployment was performed. Batch 2B-2 remains unstarted; the previously documented transport/platform and deployment limitations still apply.

