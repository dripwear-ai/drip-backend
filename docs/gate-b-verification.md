# Gate B corrective verification - 2026-10-12

**Current approval status: Gate B is owner-approved**, following the corrective verification dated 2026-10-12. This document remains the historical Gate B verification record; this status update does not rerun or change any verification evidence. The owner approved the [Phase 2 specification and plan](phase-2-specification-and-plan.md) as the planning baseline on 2026-10-13 and separately authorized P2-A implementation on 2026-10-14, subject to resolving blocking decisions. P2-B is not authorized.

**P2-A authentication change record — 2026-10-14:** the owner selected Amazon Cognito, Google federation plus email/password, no required phone/routine SMS OTP, and separate admin authentication with strong MFA plus DRIP grants. This explicitly amends the previously approved OTP proposal. [ADR 0002](adr/0002-cognito-authentication-decision.md) records approved lifecycle/privacy requirements, proposed technical defaults and unresolved configuration approvals. This is documentation only: no Cognito implementation, AWS configuration, new runtime verification or P2-A acceptance is claimed. Authentication implementation awaits review of this documentation diff and resolution of blocking decisions; P2-B remains unauthorized.

**P2-A guest access and wishlist change record — 2026-10-15:** the owner approved D8 guest read-only discovery/swipes, search, filters, eligible published product details and approved external retailer links in the initial release, without an account; D9 PostgreSQL-backed permanent wishlist persistence and online cross-device synchronization are approved in P2-A. Account-specific functions require sign-in. A guest save preserves the card, prompts authentication and requires explicit confirmation plus backend acknowledgement; no guest wishlist, silent merge or account-specific guest session is introduced. Initial customer authentication does not collect phone numbers. Cognito Google/email-password, separate strong-MFA admin authentication with current DRIP grants and approved lifecycle/privacy requirements remain. DRIP checkout/orders/payments/settlements stay outside P2-A/P2-B; future DRIP order placement must require authentication. [ADR 0002](adr/0002-cognito-authentication-decision.md) and the [Phase 2 baseline](phase-2-specification-and-plan.md) record this dated amendment; C1-C7 remain unresolved where applicable. Authentication implementation is paused for documentation review and required security approvals. No provider configuration, implementation, rerun of tests or P2-A acceptance is claimed; historical evidence below is unchanged and P2-B remains unauthorized.

**Final OOTD guest-access change record — 2026-10-15 (subsequent decision):** the owner approved guest access to all available P2-A/P2-B customer browsing/discovery, explicitly including the OOTD feed, public outfit images/titles/captions/eligible products, product details, Discover/search/filter/swipes and approved retailer links without account/phone. Outfits must be published and rights-cleared with all required products publicly eligible; suppress an ineligible outfit and expose no unpublished/private/admin/wishlist-membership data. Authenticated confirmed permanent saves and future authenticated DRIP order placement remain distinct; DRIP checkout/orders/payments/settlements are excluded from P2-A/P2-B, and retailer websites may require their own login. The [Phase 2 plan](phase-2-specification-and-plan.md) contains the P2-A readiness checkpoint and [ADR 0002](adr/0002-cognito-authentication-decision.md) the public/private boundary. D6/D7 and C1-C7 remain open. This is documentation/planning only, with no implementation, provider setup, deployment, runtime rerun or acceptance claim. Historical Gate B evidence and earlier approvals remain unchanged; authentication stays paused for documentation/security review and P2-B implementation remains unauthorized.

The verification runs below preceded owner acceptance; Gate B has since been explicitly approved. This historical report covers the uncommitted working tree verified on `main`, based on `341a6b0`; no branch changes or commits were made during those runs.

Recorded result after resumed live verification: **5 integration tests passed, 35 non-live tests deselected, exit 0**. Docker was available for that run, resolving the earlier infrastructure blocker. Disposable services were stopped and removed. The owner subsequently approved Gate B. See the resumed-run evidence at the end of this report.

## Prioritized changes

1. Production settings normalize and validate environment names, reject development credentials and SQL/debug logging, and hide sensitive validation inputs. Request errors use static log messages; Uvicorn exceptions use the redacting formatter. Local Compose ports default to 127.0.0.1.
2. Genuine pnpm/uv locks and runtime pins support fresh installation. The API now declares its build backend. All TypeScript consumers build shared contracts first. Mobile React/DOM and native dependencies follow Expo SDK 57 compatibility; the missing icon reference and removed legacy splash configuration are corrected.
3. UUID primary keys now use only PostgreSQL's UUIDv7 server default. New revision `0002_require_pg18_uuidv7` checks native capability. Revision 0001's executable upgrade and downgrade ASTs are unchanged. Alembic accepts percent-encoded credentials. Live migration tests use a unique, transactional schema and an explicit version-table schema.
4. 404/405 and other HTTP exceptions use the error envelope and preserve intended headers. Root test/lint/type/build/export commands are repaired. Static verification states its limits; clean verification records actual command outcomes and preserves logs.

## Verification evidence

The final clean run is in `.verification/clean-Cxxqq3`; its `verification-results.json` contains exact executable arguments, exit codes, source inventory, preflight evidence, and per-command log filenames. The earlier failed run remains in `.verification/clean-Qvb2Hk`.

Final clean-run status: **PASS, exit 0** for every listed software check. At that point live service verification was blocked; the resumed run below resolved that blocker. Gate B is now owner-approved; these are historical test results, not a fresh execution.

The runner copies current Git-visible source into a new directory. It excludes node_modules, virtualenvs, local dotenv, shared declarations/build output, Next/Expo output, next-env/expo-env declarations and TypeScript build metadata. Download caches are reused; installed environments and generated output are fresh. This verifies an uncommitted source snapshot, not the original Git commit alone. No native device behavior or live database behavior is inferred from software checks.

## Regression coverage

- Environment normalization, unknown names, signing-key validation, encoded development passwords, missing database/Redis passwords, DEBUG and LOG_LEVEL rejection, dotenv/process precedence, and sensitive input omission.
- HTTP 404/405 envelopes, Allow/Retry-After headers, generic HTTP detail redaction, custom password validator and unexpected exception redaction, structured log redaction, and Uvicorn exception logging.
- UUID DDL/server default with no competing UUIDv4 client default; actual Alembic offline upgrade with synthetic `%40`, `%25`, `%2F` credentials and preserved historical revision.
- Five separate live tests cover PostgreSQL/Redis health, readiness, native UUIDv7/version, and migration roundtrip plus direct INSERT/ORM server defaults. All five passed in the resumed live verification documented below.

## Dependency decisions

| Dependency | Final resolution / decision |
| --- | --- |
| Node / pnpm / Python | 24.19.0 / 9.15.9 / 3.14.7; uv 0.12.7 used |
| Expo | 57.0.27 |
| React Native / Metro config | 0.86.3 / 0.86.3 |
| Mobile React / React DOM | 19.2.3 / 19.2.3 |
| Mobile React / DOM types | 19.2.18 / 19.2.7 |
| Web React / React DOM / Next | unchanged 19.3.0 / 19.3.0 / 16.4.0 |
| Reanimated / Worklets | 4.5.1 / 0.10.1, matching Expo's installed map |
| Safe area / Screens / Gesture Handler | 5.7.0 / 4.26.2 / 2.32.0 |
| Required Expo peers | direct constants 57.0.21 and linking 57.0.12 |
| Expo configuration support | system-ui 57.0.4, splash-screen 57.0.9; existing splash background preserved through the supported plugin |
| React Native Web | 0.21.4 |
| TypeScript | 6.0.3 in all four workspaces, per Expo validation |
| Lint/Doctor | ESLint 9.39.5, eslint-config-expo 57.0.2, expo-doctor 1.20.4 |
| Python core versions | unchanged Pydantic 2.14.0 / pydantic-core 2.50.0, SQLAlchemy 2.1.4, Alembic 1.20.0, greenlet 3.5.6, asyncpg 0.32.0 |
| Python packaging | uv_build 0.12.7; proper editable project installation; lock supports 3.14.x |
| Container pins | unchanged postgres:18.6-alpine and redis:8.2.10-alpine |

Official references: [Expo SDK upgrade workflow](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/), [SDK 57 splash plugin](https://docs.expo.dev/versions/v57.0.0/sdk/splash-screen/). Native versions were resolved using the installed compatibility map and official CLI, not manual lock edits. Shared-types retains no React dependency and web/mobile retain separate React graphs.

## Earlier failures and corrective commands

- Initial Expo installation encountered `ERR_PNPM_UNEXPECTED_STORE`. `pnpm install --force --no-frozen-lockfile` rebuilt only generated dependency installations in Drip; no source or user data was reset.
- `pnpm --filter mobile exec expo install react-native react-native-reanimated react-native-worklets react-native-safe-area-context react-native-screens expo-haptics expo-router expo-secure-store expo-status-bar expo-constants expo-linking expo-system-ui react-dom react-native-web --pnpm` completed. Direct Metro and React DOM type peers were then corrected and resolved by `pnpm install --no-frozen-lockfile`.
- `pnpm check:mobile` initially failed because TypeScript 5.6.3 did not match Expo's expected ~6.0.3. `pnpm --filter mobile exec expo install typescript --dev --pnpm` passed. All workspace TypeScript manifests were aligned, then `pnpm install --no-frozen-lockfile` passed.
- `uv lock --project apps/api --python 3.14.7` and `uv sync --project apps/api --locked --python 3.14.7 --extra dev` passed. The lock retains 59 package records and unchanged core package versions; incompatible-version wheel entries were pruned by uv.
- A new logging regression initially failed (34 passed, 1 failed, 5 deselected) because Alembic's logging setup disabled existing loggers. Preserving existing loggers fixed it; `pnpm test` then passed 35 tests with 5 live tests deselected.
- First `pnpm verify:clean` exited 1: backend tests had 33 passes and 2 temporary-directory setup errors; Expo Doctor passed 20/21 and rejected the legacy `splash` field. Every other executed software check in that run passed, including all-platform export. Those failures remain recorded in its logs.
- The pytest temporary directory was made self-contained. `pnpm --filter mobile exec expo install expo-splash-screen --pnpm` passed; splash settings moved to its supported config plugin. The second clean run also excludes generated next-env/expo-env declaration files.
- Final working-tree `pnpm install --frozen-lockfile` passed (exit 0, 2.8 seconds), as well as the fresh-copy frozen installation.

## Earlier blockers and remaining recommendations

**Earlier blocker, now resolved:** Docker engine access. `docker info --format '{{.ServerVersion}}'` exited 1: `dockerDesktopLinuxEngine` named pipe was not found. Both Compose `config --quiet` commands passed. During that earlier software-only run, no services were started, databases reset, volumes removed, or live migration/integration tests executed.

**NOT RUN:** Native Android/iOS compilation, simulator/device launch, signing and store builds. Expo exports are bundle verification only.

**Recommendation:** ESLint 9.39.5 is deprecated, but installed eslint-plugin-react 7.37.5 only declares ESLint support through 9. Do not force an unsupported major; update once the framework lint graph supports it. The transitive uuid 7.0.3 package also emits a deprecation notice. Container tags are patch pinned but not immutable digests; digest pinning is a later hardening option.

The resumed run below used the documented disposable stack and explicit test URLs. All required software and live foundation checks passed in the recorded runs; the owner subsequently approved Gate B. Native compilation/device validation remains outside the checks performed.

## Earlier software-verification command results

Working directory for these commands: `.verification/clean-Cxxqq3`. `pnpm verify:clean` itself was invoked from the repository root and exited 0. Node 24.19.0 was explicitly placed on PATH; the machine default Node 20.17.0 was not used.

| Command | Actual result | Evidence |
| --- | --- | --- |
| `pnpm install --frozen-lockfile` | PASS (exit 0) | 850 packages installed in a new node_modules; no peer mismatch; log `1-Frozen JS install.log` |
| `uv sync --project apps/api --locked --python 3.14.7 --extra dev` | PASS (exit 0) | New .venv, 58 installed packages; API built from the snapshot; log `2-Locked Python sync.log` |
| `pnpm build:shared` | PASS (exit 0) | tsc -b; declarations generated from source; log `3-build-shared.log` |
| `pnpm type-check` | PASS (exit 0) | Shared build/check, Next typegen + web tsc, mobile tsc all pass; log `4-type-check.log` |
| `pnpm test` | PASS (exit 0) | 35 passed; 5 live tests deselected; log `5-test.log` |
| `pnpm lint` | PASS (exit 0) | Root scripts, web/mobile ESLint, Ruff across API/migrations/tests/scripts; log `6-lint.log` |
| `pnpm type-check:api` | PASS (exit 0) | Mypy: no issues in 14 source files; log `7-type-check-api.log` |
| `pnpm build` | PASS (exit 0) | Next 16.4 production build; 3 static pages generated; log `8-build.log` |
| `pnpm check:mobile` | PASS (exit 0) | Expo dependencies up to date; Doctor 21/21; log `9-check-mobile.log` |
| `pnpm export:mobile` | PASS (exit 0) | New web JS and iOS/Android Hermes bundles, 52 assets; log `10-export-mobile.log` |
| `pnpm verify:static` | PASS (exit 0) | Limited structural checks only; log `11-verify-static.log` |
| `SHA-256 before/after comparison in verify-clean.mjs` | PASS | Both lockfiles unchanged |
| `docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet` | PASS (exit 0) | Executed in repository root |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml config --quiet` | PASS (exit 0) | Executed in repository root |
| `docker info --format '{{.ServerVersion}}'` | BLOCKED (exit 1) | Docker engine pipe unavailable |
| `pnpm test:integration` | BLOCKED / NOT EXECUTED | Docker unavailable; no live check claimed as passed |
| Native compilation/device execution | NOT RUN | Export does not validate native binaries or device behavior |

Expanded check commands (as defined in the checked manifests):

```sh
pnpm --filter @drip/shared-types build
pnpm --filter @drip/shared-types type-check
pnpm --filter web type-check
# web type-check: pnpm --filter @drip/shared-types build && next typegen && tsc --noEmit
pnpm --filter mobile type-check
# mobile type-check: pnpm --filter @drip/shared-types build && tsc --noEmit
uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml apps/api/tests
eslint scripts eslint.config.mjs
pnpm --filter web lint
pnpm --filter mobile lint
uv run --project apps/api --locked --extra dev ruff check --config apps/api/pyproject.toml apps/api/src apps/api/tests apps/api/migrations scripts
uv run --project apps/api --locked --extra dev mypy --config-file apps/api/pyproject.toml apps/api/src
pnpm --filter web build
pnpm --filter mobile exec expo install --check
pnpm --filter mobile exec expo-doctor
pnpm --filter mobile export
# mobile export: expo export --platform all --output-dir dist --clear
uv run --project apps/api --locked --extra dev python scripts/verify_foundation.py
```

Final code/manifests/locks were byte-compared against the passing source copy. Only post-run documentation reporting differs. The clean preflight listed 14 absent generated/environment paths and copied 64 source files. No stale installed environment or generated declaration was copied.

## Final diff review and changed files

Reviewed tracked changes and new files, both lock graphs, migration operations, setup/ADR consistency, and synthetic credential use. No new product routes or shared catalog contracts were implemented. A limited credential-pattern scan found no private keys or provider-token patterns; this is not a comprehensive external security audit. Existing local dotenv files and database volumes were preserved. No AGENTS.md was present and none was introduced.

`git diff --check` passed. Tracked diff summary (new files listed separately below):

```text
.env.example                                       |    1 +
 .gitignore                                         |    3 +
 apps/api/README.md                                 |   14 +-
 apps/api/alembic.ini                               |    3 +-
 apps/api/migrations/env.py                         |   22 +-
 .../migrations/versions/0001_initial_baseline.py   |   19 +-
 apps/api/pyproject.toml                            |   18 +-
 apps/api/src/drip/core/config.py                   |   52 +-
 apps/api/src/drip/core/database.py                 |    2 +-
 apps/api/src/drip/core/errors.py                   |   37 +-
 apps/api/src/drip/core/logging.py                  |   17 +-
 apps/api/src/drip/core/redis.py                    |    2 +-
 apps/api/src/drip/main.py                          |    2 +-
 apps/api/src/drip/models/base.py                   |    5 +-
 apps/api/tests/conftest.py                         |   26 +-
 apps/api/tests/test_config.py                      |  102 +-
 apps/api/tests/test_errors.py                      |    3 +-
 apps/api/tests/test_live_infrastructure.py         |   70 +-
 apps/api/uv.lock                                   |  616 +--------
 apps/mobile/app.json                               |   15 +-
 apps/mobile/package.json                           |   37 +-
 apps/web/package.json                              |    6 +-
 docs/adr/0001-modular-monolith-foundation.md       |    5 +-
 docs/setup.md                                      |  140 +-
 infra/docker-compose.yml                           |    4 +-
 package.json                                       |   26 +-
 packages/shared-types/package.json                 |    2 +-
 pnpm-lock.yaml                                     | 1369 +++++++++++---------
 scripts/verify_foundation.py                       |  120 +-
 29 files changed, 1262 insertions(+), 1476 deletions(-)
```

Complete changed-file list relative to the repository root:

```text
 M .env.example
 M .gitignore
 M apps/api/README.md
 M apps/api/alembic.ini
 M apps/api/migrations/env.py
 M apps/api/migrations/versions/0001_initial_baseline.py
 M apps/api/pyproject.toml
 M apps/api/src/drip/core/config.py
 M apps/api/src/drip/core/database.py
 M apps/api/src/drip/core/errors.py
 M apps/api/src/drip/core/logging.py
 M apps/api/src/drip/core/redis.py
 M apps/api/src/drip/main.py
 M apps/api/src/drip/models/base.py
 M apps/api/tests/conftest.py
 M apps/api/tests/test_config.py
 M apps/api/tests/test_errors.py
 M apps/api/tests/test_live_infrastructure.py
 M apps/api/uv.lock
 M apps/mobile/app.json
 M apps/mobile/package.json
 M apps/web/package.json
 M docs/adr/0001-modular-monolith-foundation.md
 M docs/setup.md
 M infra/docker-compose.yml
 M package.json
 M packages/shared-types/package.json
 M pnpm-lock.yaml
 M scripts/verify_foundation.py
?? .node-version
?? .npmrc
?? .nvmrc
?? .python-version
?? apps/api/migrations/versions/0002_require_pg18_uuidv7.py
?? apps/api/tests/test_migrations.py
?? apps/api/tests/test_security_errors.py
?? apps/mobile/eslint.config.cjs
?? apps/web/eslint.config.mjs
?? docs/gate-b-verification.md
?? eslint.config.mjs
?? infra/compose.test.yml
?? scripts/verify-clean.mjs
```

## Resumed live verification - 2026-10-12

Evidence directory: `.verification/live-cko3btzs`. Detailed results are also saved in `live-verification-results.json` there. This run started from the same uncommitted `main` tree at `341a6b0`. All source/manifests/lockfiles matched the passing clean snapshot; only the existing ADR reporting differed. No application, test, migration, dependency, or configuration source changes were necessary. Only this report and `docs/adr/0001-modular-monolith-foundation.md` were updated during this resumed run.

### Isolation and execution

The effective Docker context was `desktop-linux`, endpoint `npipe:////./pipe/dockerDesktopLinuxEngine`, engine Linux 28.4.0. Neither DOCKER_HOST nor DOCKER_CONTEXT overrode it. No containers existed under project `drip-gate-b-tests`, and neither host test port had a listener before startup.

Resolved Compose configuration and actual container inspection confirmed:

- PostgreSQL 18.6: `127.0.0.1:55435`, database `drip_gate_b_test`, role `drip_test`, tmpfs `/var/lib/postgresql`, no volume/bind mounts.
- Redis 8.2.10: `127.0.0.1:56381`, database 0, tmpfs `/data`, no volume/bind mounts.
- No production/development stack was started or modified. The only created containers/network belonged to the explicitly named disposable project.

The test process used these exact settings; process variables were scoped to its shell:

```powershell
$env:PATH='C:\Users\batla\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;'+$env:PATH
$env:UV_CACHE_DIR='C:\Users\batla\Desktop\Drip\.cache\uv'
$env:DRIP_ENV_FILE=''
$env:ENVIRONMENT='test'
$env:PYTHONPATH=''
$env:PYTEST_ADDOPTS='-v'
Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
$env:DRIP_TEST_DATABASE_URL='postgresql+asyncpg://drip_test:disposable_test_only@127.0.0.1:55435/drip_gate_b_test'
$env:DRIP_TEST_REDIS_URL='redis://127.0.0.1:56381/0'
$env:DATABASE_URL=$env:DRIP_TEST_DATABASE_URL
$env:REDIS_URL=$env:DRIP_TEST_REDIS_URL
pnpm test:integration
```

The current fixture validates the database name and presence of a Redis URL; it does not independently restrict all possible hosts/ports. For this run, both URLs were explicitly fixed to the verified disposable endpoints above. Local dotenv and inherited Python environment overrides were disabled. No ambiguous target was used.

### Commands and actual results

All commands ran from `C:\Users\batla\Desktop\Drip`.

| Exact command | Exit | Actual result / log |
| --- | --- | --- |
| `docker context show` | 0 | desktop-linux |
| `docker context inspect desktop-linux --format '{{.Endpoints.docker.Host}}'` | 0 | Local named pipe |
| `docker info --format '{{.OSType}} {{.ServerVersion}}'` | 0 | linux 28.4.0 |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml config --quiet` | 0 | Valid configuration |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml config --format json` | 0 | Exact disposable database/ports/tmpfs verified |
| `docker ps -a --filter label=com.docker.compose.project=drip-gate-b-tests --format '{{.ID}} {{.Names}} {{.Status}}'` | 0 | Empty before startup |
| `docker compose --progress plain -p drip-gate-b-tests -f infra/compose.test.yml up -d --wait` | 0 | Both services healthy; `01-compose-up.log` |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml ps --format json` | 0 | Both healthy; `02-compose-ps.log` |
| `docker inspect drip-gate-b-tests-postgres-test-1 drip-gate-b-tests-redis-test-1 --format '{{.Name}} {{json .Mounts}} {{json .NetworkSettings.Ports}} {{.State.Health.Status}}'` | 0 | No volume mounts; correct loopback ports; `03-isolation.log` |
| `pnpm test:integration` | 0 | **5 passed, 35 deselected in 1.36s**, Python 3.14.7; `04-integration.log` |
| `docker inspect drip-gate-b-tests-postgres-test-1 drip-gate-b-tests-redis-test-1 --format '{{.Name}} tmpfs={{json .HostConfig.Tmpfs}} mounts={{json .Mounts}}'` | 0 | Correct tmpfs paths; `05-tmpfs.log` |
| PostgreSQL evidence command reproduced below | 0 | Native UUIDv7, version 18.6, cleanup counts zero; `06-postgres-evidence.log` |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T redis-test redis-cli ping` | 0 | PONG; `07-redis-evidence.log` |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T redis-test redis-cli DBSIZE` | 0 | 0 keys; `07-redis-evidence.log` |
| `docker compose -p drip-gate-b-tests -f infra/compose.test.yml logs --no-color` | 0 | Saved `08-services.log`; no ERROR/FATAL entries; Alpine locale warning noted |
| `docker compose --progress plain -p drip-gate-b-tests -f infra/compose.test.yml down` | 0 | Both containers and only their project network removed; `09-compose-down.log` |
| `docker ps -a --filter label=com.docker.compose.project=drip-gate-b-tests --format '{{.ID}} {{.Names}}'` | 0 | Empty after cleanup; `10-after-down.log` |
| `docker network ls --filter label=com.docker.compose.project=drip-gate-b-tests --format '{{.ID}} {{.Name}}'` | 0 | Empty after cleanup |
| `docker volume ls --filter label=com.docker.compose.project=drip-gate-b-tests --format '{{.Name}}'` | 0 | No named project volumes |
| `git diff --check` | 0 | No whitespace errors |

Exact read-only PostgreSQL evidence command:

```powershell
docker compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T postgres-test psql -U drip_test -d drip_gate_b_test -v ON_ERROR_STOP=1 -c "WITH generated AS MATERIALIZED (SELECT pg_catalog.uuidv7() AS id) SELECT current_database(), current_user, current_setting('server_version') AS server_version, id, pg_catalog.uuid_extract_version(id) AS uuid_version FROM generated; SELECT count(*) AS remaining_test_schemas FROM pg_namespace WHERE nspname LIKE 'gate_b_%'; SELECT count(*) AS remaining_test_tables FROM pg_class WHERE relname IN ('alembic_version', 'gate_b_uuid_probe'); SELECT count(*) AS remaining_pgcrypto_extensions FROM pg_extension WHERE extname = 'pgcrypto';"
```

### Live evidence and migration review

All five selected tests passed; none failed or were blocked:

1. `test_live_database_connection`: successful PostgreSQL query.
2. `test_live_postgresql18_uuidv7`: native function call, Python UUID.version == 7, PostgreSQL version in the 18.x range, and native uuid_extract_version == 7.
3. `test_live_redis_connection`: successful Redis PING.
4. `test_live_readiness_probe_integration`: HTTP 200, overall healthy, PostgreSQL and Redis healthy with positive latencies.
5. `test_migration_roundtrip_and_actual_uuid_defaults`: upgrade head, downgrade base, re-upgrade head; revision `0002_require_pg18_uuidv7`; direct INSERT DEFAULT VALUES and ORM flush both generate version-7 IDs using the actual UUIDPrimaryKeyMixin. The test uses a separate declarative metadata base and temporary probe table, not a product entity.

Independent SQL evidence returned PostgreSQL **18.6**, database `drip_gate_b_test`, role `drip_test`, UUID `01a13052-f2df-7aa6-bb96-8529ad187da8`, and native UUID version **7**. After the integration transaction, remaining test schemas, probe/Alembic tables, and pgcrypto extensions were each **0**. This confirms the transaction rolled back the test migration artifacts. Redis remained empty.

Migration `0001_initial_baseline.py` compared with `341a6b0` changes only: trailing whitespace/blank-line cleanup, import of Sequence from collections.abc instead of typing, removal of unused sqlalchemy and Union imports, modern `str | None` annotations, quote style, and comments clarifying pgcrypto history. Revision values are unchanged. An AST comparison of both functions passed: upgrade still executes exactly `CREATE EXTENSION IF NOT EXISTS pgcrypto;`, and downgrade is still `pass`. No historical executable migration behavior was rewritten.

Migration `0002_require_pg18_uuidv7.py` correctly follows 0001, rejects PostgreSQL below 18, and calls schema-qualified native pg_catalog functions to require UUID version 7. It has no table/data mutations and no-op downgrade. Its normal upgrade and downgrade paths passed in the disposable PostgreSQL 18.6 round-trip; its rejection path on older PostgreSQL was not executed. The live test's unique schema and Alembic version-table schema are inside an external transaction, rolled back in finally.

### Cleanup, limits, and owner recommendation

The run created only disposable tmpfs database/cache state plus its containers/network. Test migrations temporarily created the isolated schema, version table, pgcrypto extension, and UUID probe data; transaction rollback removed them. The documented `down` command then stopped/removed the disposable services and network, releasing tmpfs contents. No named volumes were created or deleted, no user database was reset, and no unrelated data was changed.

`pnpm verify:clean` was **NOT RERUN in this resumed run**: no application, test, migration, dependency, or configuration source changed. Their bytes still match the previous passing clean snapshot. The prior 35-test non-live run, Ruff/ESLint/Mypy, all type checks, web build, Expo Doctor 21/21, and all-platform exports remain prior evidence, not newly executed results. Only reporting documentation changed now.

Native Android/iOS compilation, signing, simulator/device execution, and a production deployment were **NOT RUN**. The Alpine PostgreSQL image logged that no usable system locales were found; locale-specific behavior was not tested. Strict test-URL host/port enforcement could be strengthened separately; the controlled endpoints for this run were verified explicitly.

Git state recorded at the end of that verification run was `main` at `341a6b0`, 29 modified tracked files and 13 untracked files, no staged changes. The resumed-run source fingerprint comparison showed only the two documentation files changed. No commit or branch change occurred, and the original uncommitted work was preserved. The completed software and disposable live evidence was subsequently reviewed and Gate B explicitly approved by the owner. **Gate B is owner-approved. Subsequent authorization: P2-A only, dated 2026-10-14; P2-B remains unauthorized.**
