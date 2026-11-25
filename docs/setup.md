# DRIP 2.0 foundation setup and verification

For owner-led setup of Supabase PostgreSQL, Auth0, Cloudflare R2/DNS, Firebase/Expo and current integration limits, see the [provider setup guide](provider-setup.md).

Gate B is **owner-approved** following the corrective verification dated 2026-10-12. These commands verify foundation infrastructure only. The [Phase 2 specification and plan](phase-2-specification-and-plan.md) is the **owner-approved planning baseline as of 2026-10-13**; P2-A implementation was separately authorized on 2026-10-14, with unresolved prerequisites still gating affected work. P2-B requires P2-A acceptance and separate authorization. Recording approval/authorization does not rerun verification.

## Runtimes and installation

Use Node **24.19.0** (`.node-version` / `.nvmrc`), pnpm **9.15.9** (`packageManager`), Python **3.14.7** (`.python-version`), and uv **0.12.7** or a compatible newer release. Python support is currently 3.14.x. Do not use Node 20.17.

From the repository root:

```sh
pnpm install --frozen-lockfile
uv sync --project apps/api --locked --python 3.14.7 --extra dev
pnpm build:shared
```

The API uses the uv build backend and is installed as `drip`. No manual editable install, PYTHONPATH, or pre-existing `.pth` file is required. uv commands below use the locked environment. Do not hand-edit either lockfile.

Expo SDK 57 dependencies follow the installed `expo/bundledNativeModules.json` compatibility map and `expo install` validation ([official upgrade guidance](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/)). Mobile React/React DOM stay together at 19.2.3; web retains its separate 19.3.0 pair. React Native and its Metro configuration use 0.86.3, and all workspaces use TypeScript 6.0.3. Do not override native peer versions independently of Expo's compatibility check.

ESLint 9.39.5 is deprecated upstream, but the installed React lint plugin currently declares support only through ESLint 9. Keep the compatible graph until the framework lint plugins support a newer major; do not bypass peer checks to force ESLint 10.

## Environment convention

Copy `.env.example` to **repository-root `.env`** once, without overwriting an existing file. For PowerShell:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

The API loads this root file independent of its working directory. It ignores legacy `apps/api/.env`; preserve any existing file while manually reconciling its values into the root file. Real process environment variables override dotenv values. `DRIP_ENV_FILE` can explicitly select an absolute deployment dotenv path; setting it to an empty string disables dotenv loading. Installed distributions outside this source layout use process configuration unless an explicit dotenv path is supplied.

Compose commands explicitly use the same root `.env`. Ports are PostgreSQL **5435**, Redis **6381**, API **8000**, admin web **3001**, seller web **3002**, Expo native bundler **8081**, and Expo web preview **8083**. If ports or credentials change, update DATABASE_URL/REDIS_URL as well as the corresponding Compose values; URLs are not assembled from separate fields.

Next and Expo run from their own workspaces and do not automatically load the repository-root dotenv. The mobile discovery and product-detail screens use the public API when `EXPO_PUBLIC_API_URL` is set to the API origin (scheme and host only); otherwise they show an explicit not-connected state. Discover uses `POST /api/v1/discover` with a short-lived signed cursor and one-card response. Public catalog routes require Redis-backed abuse controls and explicit `CATALOG_PUBLIC_RATE_PER_MINUTE` plus `CATALOG_PUBLIC_RATE_BURST` settings; leave catalog access unavailable until the owner-selected limits are configured. For a physical device, configure a host-reachable development URL rather than `localhost`. The web admin/seller shells remain disconnected, and `NEXT_PUBLIC_API_URL` is not yet consumed. Never put secrets in public variables.

Production configuration accepts only normalized environment names (development, test, staging, production), rejects the development signing key, rejects missing/default database and Redis credentials, and rejects DEBUG/SQL echo. Supply deployment credentials through environment variables or an explicitly selected secret file. Do not use the local Compose stack for production.

## Development infrastructure and API

```sh
docker compose --env-file .env -f infra/docker-compose.yml up -d --wait
docker compose --env-file .env -f infra/docker-compose.yml ps
uv run --project apps/api --locked alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api --locked uvicorn drip.main:create_app --factory --reload --port 8000
```

Both services bind to 127.0.0.1. DEV_BIND_ADDRESS is an explicit override. Existing development volume names, data mounts, and migration revision IDs are preserved. PostgreSQL/Redis image tags are patch pinned, but not digest immutable.

Health endpoints: `/api/v1/health/live` and `/api/v1/health/ready`. Development OpenAPI: `/docs`.

## Migration policy

`0001_initial_baseline` retains its original upgrade/downgrade operations. It creates pgcrypto and intentionally retains that extension on downgrade; it may be shared with other objects. Its formatting cleanup does not change database behavior.

`0002_require_pg18_uuidv7` checks native PostgreSQL UUIDv7 capability without modifying application data. `0003_portable_identity_checkpoint` provides the approved guarded PG17 checkpoint path. Revisions `0004_identity_foundation` and `0005_catalog_foundation` define the identity and catalog foundations; they must execute under their specified role model. Models generate new identifiers in the application with the existing Python UUIDv7 utility and store them in PostgreSQL UUID columns. Do not infer that the migration/security foundations have live acceptance from their offline tests; use the recorded database-acceptance report and current disposable-target checks before treating them as verified.

Never reset, drop, or recreate an existing database to verify this work. Never downgrade a user database as a test. Use the isolated test service below.

## Routine checks

Run each command from the repository root; a failed command must remain a failed check.

```sh
pnpm test
pnpm lint
pnpm type-check:api
pnpm type-check
pnpm build
pnpm check:mobile
pnpm export:mobile
pnpm verify:static
```

- `test` runs backend pytest, including security, HTTP envelopes, UUID DDL, and real Alembic offline URL regressions; live tests are explicitly deselected.
- `lint` runs web/mobile ESLint plus Ruff over API source, tests, migrations, and scripts.
- `type-check:api` runs strict Mypy on API source with the Pydantic plugin.
- `type-check` builds shared-types before all TypeScript consumers; the web command also generates Next route types.
- `build` builds shared-types and the web production bundle.
- `check:mobile` runs Expo dependency validation and the pinned Expo Doctor.
- `export:mobile` builds shared-types and exports iOS, Android, and web bundles. This does **not** prove native compilation, signing, device launch, or platform behavior.
- `verify:static` checks a limited set of structural requirements and asset references. It does not certify security, absence of fake data, dependency compatibility, clean installs, or acceptance.

For development: `pnpm dev:web`, `pnpm dev:mobile`.

## Disposable live integration verification

The separate test Compose file uses tmpfs, distinct service names and ports, and **no existing development volumes**. Do not point these tests at a user database. Start only this isolated stack:

```sh
docker compose -p drip-gate-b-tests -f infra/compose.test.yml up -d --wait
docker compose -p drip-gate-b-tests -f infra/compose.test.yml ps
```

In PowerShell, set these explicit test-only URLs:

```powershell
$env:DRIP_TEST_DATABASE_URL = 'postgresql+asyncpg://drip_test:disposable_test_only@127.0.0.1:55435/drip_gate_b_test'
$env:DRIP_TEST_REDIS_URL = 'redis://127.0.0.1:56381/0'
pnpm test:integration
```

The test-only preflight in `apps/api/tests/disposable_targets.py` runs from `pytest_configure` before application settings/engine imports during collection. It requires both `DRIP_TEST_DATABASE_URL` and `DRIP_TEST_REDIS_URL` for integration selection and accepts only the exact canonical strings shown above: `postgresql+asyncpg` with the documented disposable PostgreSQL user/password, literal `127.0.0.1:55435/drip_gate_b_test`, and credential-free `redis://127.0.0.1:56381/0`. No new configuration variables or alternate schemes are accepted. This deliberately rejects alternate credentials, localhost/IPv6/encoded hosts, noncanonical ports/paths, whitespace/control characters, user-info tricks, query strings (even an empty `?`), fragments and percent encoding instead of normalizing them. Errors identify the variable/service without echoing supplied values. If the disposable Compose contract changes, update the guard, regression tests and documentation together; never point it at another database.

Only the existing exact `not integration` marker exclusion can omit both test variables. Non-live collection then uses the canonical disposable URLs for its effective application settings, without populating the explicit DRIP_TEST_* variables or authorizing live tests. Supplied empty, partial or invalid test variables fail even in non-live runs. Other marker expressions, including an empty expression or compound exclusions, conservatively require both explicit targets. Inherited DATABASE_URL/REDIS_URL and case aliases cannot override the test targets; dotenv is disabled. The effective settings are checked before test-module imports, and each live test rechecks environment/settings consistency. Offline guard tests use fresh-process engine/pool/client/DNS/socket spies and require no services:

```sh
uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml apps/api/tests/test_disposable_targets.py -q
```

Test-target variable names must be exactly uppercase. Any lowercase/mixed-case DRIP_TEST_DATABASE_URL or DRIP_TEST_REDIS_URL key visible in the environment mapping is rejected, even alongside a valid uppercase key, for both live and non-live selection. Rejection uses a fixed redacted message and leaves the mapping unchanged. Python on Windows normalizes process-environment keys to uppercase before the guard sees them; original shell spelling cannot be recovered there. Alias startup regressions use a case-preserving mapping double with the real pytest hook and existing infrastructure spies to exercise this boundary on Windows as well.

The integration suite checks actual service health, PostgreSQL 18, native UUID version 7, migration upgrade/downgrade/re-upgrade, direct INSERT defaults, and ORM-generated IDs. Migration testing creates a unique schema inside a transaction and rolls it back; it never resets a database. Redis testing uses PING only. URL validation restricts addresses, not service identity: Docker readiness and the approved disposable Compose lifecycle must still be checked before running live tests. Do not connect if another service occupies the approved ports.

When finished, `docker compose -p drip-gate-b-tests -f infra/compose.test.yml down` stops only these disposable services. Do not run `down -v` against the development stack. Clear the two DRIP_TEST_* process variables before ordinary development.

If Docker is unavailable, report live health and migration verification as **BLOCKED**, never passed.

## Clean source verification

```sh
pnpm verify:clean
```

This creates a fresh source snapshot inside `.verification/clean-*`, using current Git-visible source (including remediation files not yet committed). It excludes local dotenv files, node_modules, virtualenvs, dist, Next/Expo output, generated next-env/expo-env declarations, and TypeScript build metadata. Its preflight records that these artifacts were absent before installation. It does not delete or mutate the original checkout's generated artifacts.

In the snapshot it performs frozen pnpm installation, locked Python 3.14 sync, shared build, type checks, backend tests, lint, web build, Expo checks, all-platform exports, and structural checks. It verifies both lockfiles remain byte-identical. Package download caches may be reused; installed environments and generated artifacts are new. Logs and JSON results remain in that snapshot. A snapshot of uncommitted work is not a claim that the current Git commit alone contains these corrections.

Live service and native device checks remain separate and are explicitly reported as NOT RUN by this runner. Successful software checks do not constitute owner acceptance of Gate B.
