# Docker readiness and live integration verification

**Current outcome: PASS.** The owner subsequently authorized disposable-stack startup, the existing transactional schema/migration test, and task-owned shutdown. The execution amendment below records five passing live tests and completed cleanup. The earlier readiness findings are preserved as history.

Date: 2026-10-20 (Asia/Calcutta). Outcome: **BLOCKED**. Docker's Linux engine is reachable, but the documented disposable stack is absent. No live tests were executed.

The owner-approved Expo SDK 57 patch-alignment milestone is closed. Its dependency changes and evidence were preserved. This report does not reopen that milestone or change historical Gate B evidence.

## Repository and read-only preflight

Confirmed working directory: `C:\Users\batla\Desktop\Drip`.

Starting branch: `main`; HEAD: `341a6b031a6eda018d0b3df88f2baca5f88fbe94`. Starting Git status: 29 modified tracked files, 19 untracked files, nothing staged. A SHA-256 inventory captured all 72 Git-visible files before the documentation edit. No applicable `AGENTS.md` or constitution-named file was found by the scoped file search; ADR 0001's foundation constraints were reviewed.

Reviewed:

- `apps/api/tests/disposable_targets.py`, `conftest.py`, and `test_live_infrastructure.py`.
- `infra/compose.test.yml`, root `package.json`, and `apps/api/pyproject.toml`.
- `apps/api/migrations/env.py`, `0001_initial_baseline.py`, and `0002_require_pg18_uuidv7.py`, by source inspection only.
- `docs/setup.md`, `docs/gate-b-verification.md`, `docs/disposable-target-guard-verification.md`, `docs/expo-sdk-57-patch-alignment-verification.md`, and `docs/adr/0001-modular-monolith-foundation.md`.

The earlier five-test success in Gate B is historical. The later guard/alias corrections have not received fresh live verification in this run. The old missing-engine-pipe blocker is not the current finding: this run reached the Linux engine successfully outside the sandbox.

## Commands and actual outcomes

Commands ran from the repository root. Docker queries explicitly targeted `desktop-linux`; no default-context switch or machine configuration change was made.

| Command/check | Exit | Actual result |
| --- | --- | --- |
| `Get-Location` | 0 | Exact DRIP repository path |
| `git branch --show-current` | 0 | `main` |
| `git rev-parse HEAD` | 0 | `341a6b031a6eda018d0b3df88f2baca5f88fbe94` |
| `git status --short` | 0 | Starting counts above; final counts below |
| `git diff --cached --stat` | 0 | Empty |
| `Get-Command docker` (Source only) | 0 | Docker CLI installed under `C:\Program Files\Docker\Docker\resources\bin` |
| `docker context ls --format '{{.Name}}'` | 0 | `default`, `desktop-linux` |
| `docker context inspect desktop-linux` (captured, parsed, endpoint compared without dumping configuration) | 0 | Endpoint exactly matches the local `dockerDesktopLinuxEngine` named pipe |
| `docker --context desktop-linux info --format '{{.OSType}}'` — sandbox attempt | 1 | Local named-pipe access denied; this alone does not establish engine unavailability |
| Same read-only `docker info` command — approved execution outside sandbox | 0 | `linux` |
| `docker --context desktop-linux ps --all --filter label=com.docker.compose.project=drip-gate-b-tests --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}} {{.Ports}}'` | 0 | Empty output: no running or stopped containers under the documented project label |
| `pnpm test:integration` / five-test pytest selection | N/A | **NOT RUN / BLOCKED**; required disposable infrastructure unavailable |

The empty project listing is not a claim that no other database service or port listener exists on the machine. No connection to either database/Redis port was attempted. No unlabelled or unrelated service was substituted.

## Disposable targets and test behavior

The source guard requires both exact uppercase `DRIP_TEST_DATABASE_URL` and `DRIP_TEST_REDIS_URL` inputs and compares their entire strings to the documented canonical constants. This report intentionally omits credential-bearing URLs.

| Service | Scheme | Host and port | Database | Declared container |
| --- | --- | --- | --- | --- |
| PostgreSQL | `postgresql+asyncpg` | `127.0.0.1:55435` | `drip_gate_b_test` | `postgres-test`, `postgres:18.6-alpine` |
| Redis | `redis` | `127.0.0.1:56381` | `0` | `redis-test`, `redis:8.2.10-alpine` |

Source inspection confirms exact-string matching, both-target validation before environment mutation, case-alias rejection, disabled dotenv loading for tests, and settings revalidation before engine/client imports. A per-test fixture rechecks effective settings. No runtime target preflight or pytest collection was executed after infrastructure absence was established.

The Compose file declares loopback-only host bindings, separate test service names, tmpfs PostgreSQL/Redis storage, and readiness checks (`pg_isready` for the test database and Redis PING). These are configuration facts, not observed container health: there are no matching containers to inspect.

The five existing tests are all in `apps/api/tests/test_live_infrastructure.py`, under its module-level integration marker:

| Test | Source line | Intended verification | This run |
| --- | --- | --- | --- |
| `test_live_database_connection` | 30 | PostgreSQL health and positive latency | BLOCKED |
| `test_live_postgresql18_uuidv7` | 38 | PostgreSQL 18, native UUID generation, Python UUID version 7, native extracted UUID version 7 | BLOCKED |
| `test_live_redis_connection` | 53 | Redis PING health and positive latency | BLOCKED |
| `test_live_readiness_probe_integration` | 61 | In-process HTTP readiness, PostgreSQL and Redis health | BLOCKED |
| `test_migration_roundtrip_and_actual_uuid_defaults` | 73 | Upgrade/downgrade/re-upgrade, direct SQL and ORM UUIDv7 server defaults | BLOCKED |

**Counts:** 5 existing live test functions identified by source inspection; 0 executed, 0 passed, 0 failed. No pytest test-count output is claimed.

## Cleanup review and authorization boundary

Source review shows connection cleanup in `conftest.py`: the fixture disposes the SQLAlchemy engine and closes Redis connections after each test. The HTTP fixture exits the application lifespan context. Redis testing performs no application writes.

The fifth test begins a transaction, creates a unique `gate_b_<random>` schema, sets a transaction-local search path, supplies the same connection to Alembic and uses that schema for the version table. It runs upgrade to head, downgrade to base, and upgrade to head; creates the UUID probe table; inserts directly and through the ORM; and calls transaction rollback in `finally` (line 106). Revision 0001 can create pgcrypto if absent; revision 0002 asserts native UUIDv7 capability. These operations are intended to be contained in the disposable transaction.

This is a review of cleanup code, **not fresh rollback evidence**. No test transaction, schema, table, extension or record was created in this run, so no database cleanup was needed or performed. No services were started, stopped or removed, and no volume or service data was changed.

The request also prohibits schema changes and running migrations. The unchanged fifth test explicitly performs both, even though it rolls them back. Before that test can run, the owner must clarify that its existing transactional schema/migration operations on the disposable database are permitted. No test body was altered or silently omitted to evade that boundary.

## Next authorized step and preservation

Two prerequisites remain:

1. Separate authorization to start only the documented disposable Compose project, or provision of that already-running infrastructure. Then recheck project identity, image, loopback bindings, tmpfs mounts, database identity and health before connecting. Current port ownership was not assessed.
2. Explicit permission for the existing fifth test's transactional schema creation and Alembic round-trip. No migration against an unrelated database is proposed.

Only after both are satisfied should the unchanged five tests run with canonical process-only target inputs, followed by evidence of rollback and connection cleanup. Any service teardown requires appropriate authorization; this run performs none.

This task adds only `docs/docker-live-integration-readiness-verification.md`. The final SHA-256 comparison found all 72 starting Git-visible files byte-identical, this one added report, and no removals. The approved Expo changes, prior reports and every pre-existing tracked/untracked file were preserved.

`git diff --check` and `git diff --cached --quiet` both returned 0. Focused report checks for the heading, trailing whitespace, conflict markers and credential-bearing URLs returned 0. Fresh Git output remains `main` / `341a6b0`, with 29 modified tracked files and 20 untracked files, nothing staged. No commit or branch change occurred. The extra untracked file is this report.

## Authorized disposable execution — 2026-10-20

The owner's subsequent instruction explicitly permitted startup of the documented test stack, all five unchanged live tests including the fifth test's temporary schema and Alembic operations, and shutdown of only task-created containers. Both earlier authorization blockers are resolved for this execution. Gate B and Expo patch-alignment owner approvals remain unchanged; no new product milestone is authorized.

Initial Git state was freshly checked: `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`, 29 modified tracked files, 20 untracked files, nothing staged. Before editing, 73 Git-visible files were hashed. Evidence is retained in `.verification/live-20261020-b00f8038/`, including `baseline-hashes.json`, `execution-results.json`, command logs and `live-tests.xml`.

### Isolation and target validation

The effective `docker compose ... config --format json` result was captured and validated without printing its credentials. Checks confirmed:

- Project exactly `drip-gate-b-tests`; services exactly `postgres-test` and `redis-test`; approved image tags, loopback bindings, database name, PGDATA and health checks.
- No named volumes, bind mounts, privilege/network overrides, command/entrypoint overrides or build directives. Tmpfs paths cover the cached images' declared data volumes.
- No project containers, networks or volumes existed before startup. Windows' active TCP-listener inventory showed neither test port occupied.
- The unchanged guard's canonical URLs matched the effective Compose credentials and the exact approved schemes, host, ports and database paths. `prepare_test_environment(..., "integration")` and validation of actual application settings passed without importing the database or Redis infrastructure modules. No inherited application target or dotenv supplied an alternative destination.

After startup, both containers' project/service labels, image tags, environment values, actual port bindings and healthy states matched the validated configuration. Docker reported `Mounts=[]` and the expected entries in `HostConfig.Tmpfs`. `stat -f -c '%T'` inside each container confirmed its data filesystem was `tmpfs`. Both approved loopback ports were then reachable.

One inspection attempt **failed with exit 1** before any database connection because the audit script incorrectly expected tmpfs inside Docker's `Mounts` array. A read-only inspection exposed the actual representation; the corrected metadata check plus filesystem check passed. This was an inspection-script assumption, not a modified service configuration or weakened test. It is retained in `execution-results.json`.

### Commands and actual results

All commands used the DRIP repository as working directory and explicit `desktop-linux` Docker context. Read-only Docker access and the authorized lifecycle/test commands used execution outside the sandbox. Runtime output confirmed Node 24.19.0, pnpm 9.15.9 and Python 3.14.7. Existing locked environments were used; no dependency installation or upgrade was requested.

| Command/check | Exit | Result / evidence |
| --- | --- | --- |
| `docker context inspect desktop-linux` (captured, not dumped) | 0 | Approved local Linux-engine pipe |
| `docker --context desktop-linux info --format '{{.OSType}} {{.ServerVersion}}'` | 0 | `linux 28.4.0` |
| `docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml config --format json` (captured) | 0 | Effective configuration passed assertions |
| Project-filtered `docker ps -a`, `network ls`, `volume ls` and Windows TCP-listener inventory | 0 | Empty project resources; zero listeners on 55435/56381 |
| Pure guard/effective-settings preflight using `apps/api/.venv/Scripts/python.exe` | 0 | Both canonical targets accepted; infrastructure modules not imported |
| `docker --context desktop-linux image inspect postgres:18.6-alpine redis:8.2.10-alpine --format '{{.RepoTags}} declared-volumes={{json .Config.Volumes}}'` | 0 | Data-volume paths exactly covered by configured tmpfs |
| `docker --context desktop-linux compose --progress plain -p drip-gate-b-tests -f infra/compose.test.yml up -d --wait` | 0 | Both healthy; `01-compose-up.log` |
| Initial actual-mount assertion | 1 | Representation assumption described above; stopped before connecting |
| `docker --context desktop-linux inspect drip-gate-b-tests-postgres-test-1 drip-gate-b-tests-redis-test-1 --format '{{.Id}} {{.Name}} mounts={{json .Mounts}} tmpfs={{json .HostConfig.Tmpfs}} ports={{json .NetworkSettings.Ports}} health={{.State.Health.Status}}'` | 0 | Read-only diagnostic; correct tmpfs/bindings |
| Corrected identity/environment/mount checks and `docker --context desktop-linux exec <recorded-container-id> stat -f -c '%T' <verified-data-path>` for each container | 0 | Both actual filesystems tmpfs; `02-container-identity.json` records full IDs |
| `TcpClient.ConnectAsync('127.0.0.1', port)` for each approved port, followed by disposal | 0 | Both reachable after identity checks |
| PostgreSQL baseline read query below | 0 | PostgreSQL 18.6, correct database, zero test objects; `03-before-database.log` |
| `docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T redis-test redis-cli DBSIZE` | 0 | 0 keys before tests; `04-before-redis.log` |
| `pnpm test:integration --basetemp=.verification/live-20261020-b00f8038/pytest-tmp --junitxml=.verification/live-20261020-b00f8038/live-tests.xml -v` | 0 | **5 passed, 219 deselected, 3.39s**; `05-live-tests.log` |
| PostgreSQL post-test read query below | 0 | Zero residual test objects/connections; native UUID version 7; `06-after-database.log` |
| Same Redis `DBSIZE` command after tests | 0 | 0 keys; `07-after-redis.log` |
| `docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T redis-test redis-cli INFO clients` (connected-client count only) | 0 | 1 client, the inspection command itself; `07-after-redis.log` |
| Task container-ID and project-network membership comparison | 0 | Only the two recorded task-created containers attached |
| `docker --context desktop-linux compose --progress plain -p drip-gate-b-tests -f infra/compose.test.yml down` | 0 | Only those containers and their network removed; `08-compose-down.log` |
| Project-filtered container/network/volume lists and TCP-listener inventory after shutdown | 0 | All counts zero; `09-after-shutdown.json` |

The project inventory commands used `--filter label=com.docker.compose.project=drip-gate-b-tests` with ID/name-only formats, including `ps -a --no-trunc` for shutdown ownership comparison. No unrelated resources were selected. Compound PowerShell assertion commands are recorded in the execution-tool evidence; the persisted JSON distinguishes their successful retries from the failed attempt.

For pytest, process-only PATH selected the pinned Node/pnpm tools; `UV_CACHE_DIR` pointed to the existing project cache and `UV_OFFLINE=true`. The two `DRIP_TEST_*` variables were obtained from the reviewed guard constants without echoing them. The real pytest startup hook independently validated the effective settings. Output was filtered for credential-bearing URLs and the disposable password before saving/display. A unique `--basetemp` preserved prior test artifacts. The command collected 224 tests but executed only the five integration-marked functions; no test bodies/assertions/guards were changed.

Both PostgreSQL inspections used:

```sh
docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml exec -T postgres-test psql -U drip_test -d drip_gate_b_test -v ON_ERROR_STOP=1 -c "<read-only SQL below>"
```

Baseline SQL:

```sql
SELECT current_database() AS database, current_setting('server_version') AS version;
SELECT count(*) AS test_schemas FROM pg_namespace WHERE nspname ~ '^gate_b_';
SELECT count(*) AS test_tables FROM pg_class
WHERE relname IN ('alembic_version','gate_b_uuid_probe');
SELECT count(*) AS pgcrypto_extensions FROM pg_extension WHERE extname='pgcrypto';
```

The post-test command repeated those statements and appended:

```sql
SELECT pg_catalog.uuid_extract_version(pg_catalog.uuidv7()) AS native_uuid_version;
SELECT count(*) AS other_client_connections FROM pg_stat_activity
WHERE datname=current_database() AND backend_type='client backend'
AND pid<>pg_backend_pid();
```

No migration was run outside the existing fifth test.

### Test and cleanup evidence

All five test names listed in the historical preflight passed. JUnit independently records exactly 5 tests, 0 failures, 0 errors and 0 skipped. Passing assertions establish PostgreSQL 18, native UUIDv7/Python UUID version 7, Redis health, HTTP readiness, migration upgrade/downgrade/re-upgrade to revision `0002_require_pg18_uuidv7`, and version-7 IDs from both direct SQL and ORM server defaults.

After pytest exited, separate read-only inspection found zero `gate_b_` test schemas, zero probe/version tables and zero pgcrypto extensions, matching the initial zero counts. PostgreSQL had zero other client connections. Redis still had zero keys and only its current inspection client. This supports completed transaction rollback and connection cleanup, rather than relying only on the cleanup source code.

Before shutdown, full container IDs were compared with `02-container-identity.json` and network membership was checked. The documented `down` command used no `-v`, volume removal, prune, reset or unrelated-container operation. Both task-created containers and their sole network were removed. Post-shutdown inspection found zero project containers, networks or volumes and zero test-port listeners. Temporary tmpfs contents ceased to exist with shutdown; no persistent volume, user database or unrelated service data was changed.

This closes the live-verification gap for this tested working tree. It does not claim native Android/iOS compilation/device verification or authorize authentication, P2-B or other product work. No unrelated software suite was rerun.

Final `git diff --check`, `git diff --cached --quiet` and focused report checks returned 0. The report checks covered its title, whitespace, conflict markers, balanced fences and credential-bearing URL exclusion.

The final inventory still contains 73 Git-visible files. Only this report differs from the saved starting hashes; the other 72 files, including all pre-existing tracked/untracked source, tests, migrations, guards, manifests, lockfiles and Expo evidence, remain byte-identical. No Git-visible file was added or removed during this execution. Ignored verification logs/JUnit/temp artifacts were added under the evidence directory and retained.

Final Git state: `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`; 29 modified tracked files, 20 untracked files, nothing staged. No commit, branch switch or destructive Git operation occurred. **PASS; all work remains uncommitted and unstaged for owner review.**
