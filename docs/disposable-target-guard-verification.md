# Disposable integration-target guard: implementation and verification

Date: 2026-10-15 (Asia/Calcutta). Scope: the separately authorized P2-0 test-target safety change from the [Phase 2 readiness report](phase-2-specification-and-plan.md). This records current results, not acceptance of another milestone. Gate B remains historically owner-approved. Authentication, catalog and P2-B implementation are outside this change.

## Change and safety boundary

The old autouse fixture checked only the PostgreSQL database path and whether the Redis variable was nonempty. Application imports could construct the SQLAlchemy engine during collection before that fixture ran. It did not constrain schemes, hosts, ports, Redis database, URL query overrides or ambiguous authority/encoding forms.

The new pure test helper accepts only both complete canonical URLs documented in [setup](setup.md): PostgreSQL's `postgresql+asyncpg` scheme, documented disposable credentials, literal `127.0.0.1:55435/drip_gate_b_test`; and credential-free `redis://127.0.0.1:56381/0`. Exact matching intentionally rejects alternate credentials and every alternate representation, including empty query/fragment delimiters, encoded components, control characters, extra user-info and noncanonical ports/database paths. No configuration names or accepted schemes were added. Fixed errors name the variable/service but never include supplied values or complete URLs.

`pytest_configure` validates both supplied DRIP_TEST_* variables before importing application settings, engine or Redis modules. Settings are then checked for the same effective targets before test collection. Environment changes occur only after both targets pass. Case-insensitive aliases and inherited application URLs cannot override the test targets; dotenv loading remains disabled. The live fixture rechecks for environment/settings drift.

Only the repository's exact `not integration` exclusion can omit both variables. It uses safe canonical targets for non-live collection without setting DRIP_TEST_* or authorizing live execution. Explicit empty/partial/invalid variables still fail; other marker expressions conservatively require both variables. The accepted-input unit test and existing non-live suite exercise valid startup; rejected-input subprocess tests prove invalid startup is stopped before infrastructure creation.

The [pytest configuration hook](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_configure) provides the pre-collection boundary. Exact matching avoids relying on [URL splitting as validation](https://docs.python.org/3.14/library/urllib.parse.html#url-parsing-security), including parser normalization of control characters. This is a test-entry guard, not a production configuration change or a security sandbox for arbitrary third-party pytest plugins.

## Files changed in this run

| File | Change |
| --- | --- |
| `apps/api/tests/disposable_targets.py` | New pure canonical-target preflight and atomic test-environment setup |
| `apps/api/tests/test_disposable_targets.py` | New 154 offline regression cases, including 10 fresh-process startup probes |
| `apps/api/tests/conftest.py` | Validate during configuration; defer infrastructure/application imports |
| `apps/api/tests/test_live_infrastructure.py` | Replace incomplete fixture guard with full validation and effective-settings recheck |
| `apps/api/tests/test_config.py` | Isolate the existing model-default test from harness environment overrides; assertions unchanged |
| `docs/setup.md` | Document canonical targets, conservative marker policy, focused test command and service-identity limitation |
| `docs/disposable-target-guard-verification.md` | This evidence record |

All five live-test bodies are unchanged compared with this run's starting working tree. Unique-schema migration upgrade/downgrade/re-upgrade and UUID-default tests still run inside a rolled-back transaction; Redis testing remains PING only. No migrations, dependencies, application source, runtime configuration or Compose lifecycle commands changed.

## Regression evidence

Cases cover each target independently: missing/empty configuration; wrong or malformed schemes; host aliases, remote hosts and alternative IP forms; missing/invalid/alternate ports; wrong or ambiguous database paths; Redis DB syntax; queries and fragments, including empty delimiters; user-info/multiple-host tricks; encoded components; whitespace and controls. A valid target cannot compensate for an invalid other target. Failure does not partially mutate the environment.

Ten subprocess probes invoke the real pytest entry point against the live-test module with `--collect-only --showlocals`. Fail-on-call spies cover SQLAlchemy engine/pool construction, asyncpg connections/pools, synchronous and asynchronous Redis clients/pools, DNS and socket connection entry points. Every rejected case reports pytest usage exit 4, zero spy calls and zero application settings/database/Redis/main imports. Output contains neither synthetic secret markers nor complete connection URLs. These probes need no services; they are not live integration tests.

## Commands and actual results

Commands ran from `C:\Users\batla\Desktop\Drip` unless stated otherwise. After the initial Node mismatch, process-only runtime selection was:

```powershell
$env:PATH='C:\Users\batla\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;'+$env:PATH
$env:UV_CACHE_DIR=Join-Path (Get-Location) '.cache\uv'
```

No project runtime pin was changed. `node --version` reported `v24.19.0` (exit 0).

| Exact command | Exit | Result |
| --- | --- | --- |
| `uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml apps/api/tests/test_disposable_targets.py -q` | 0 | 154 passed, 26.19s |
| `pnpm test` | 0 | 189 passed, 5 integration tests deselected, 22.14s |
| `pnpm lint:api` | 0 | Ruff passed across application, tests, migrations and scripts |
| `pnpm type-check:api` | 0 | Mypy passed, 14 application source files |
| `uv run --project apps/api --locked --extra dev mypy --config-file apps/api/pyproject.toml apps/api/tests/disposable_targets.py` | 0 | New pure helper also type-checked, 1 file |
| `docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml config --quiet` | 0 | Compose configuration valid |
| `docker --context desktop-linux info --format '{{.OSType}}'` | 1 | Linux engine named pipe `dockerDesktopLinuxEngine` unavailable |
| `docker --context desktop-linux compose -p drip-gate-b-tests -f infra/compose.test.yml ps -a` | 1 | Same unavailable engine; could not inspect live service state |
| `pnpm test:integration` | NOT RUN | BLOCKED by unavailable Docker engine; no live connection attempted |
| `pnpm verify:clean` | 1 | Fresh-copy checks ran; Expo dependency check failed as detailed below |

Preliminary attempts were not passes: interpreter inspection via `uv run --project apps/api --locked --extra dev python -c "import pytest; print(pytest.__version__)"` hit sandbox interpreter-access denial; the accompanying default-context `docker info --format '{{.OSType}}'` diagnostic also failed. The diagnostic batch exited 1. Authorized checks were retried outside that sandbox restriction. The first `pnpm lint:api` attempt exited 1 because the default Node was 20.17.0, outside the existing 24.19.x pin; the successful run above used the existing bundled runtime. No runtime/dependency installation was used to work around that mismatch. `docker context ls` showed `desktop-linux` as the active context; explicit Linux-engine checks remained unavailable.

## Fresh-copy verification evidence

The established runner created `.verification/clean-IG3WTB`, copying 69 Git-visible source files from the uncommitted working tree. Its preflight passed: no node_modules, virtualenv, local dotenv, framework output, shared-types output or generated framework declarations existed in the copy before installation. Package-download caches were reused; installed/generated artifacts were rebuilt inside the snapshot. This report was written after the run and was not part of that snapshot.

The [machine-readable results](../.verification/clean-IG3WTB/verification-results.json) preserve exact executable paths, arguments and per-step log filenames. Commands below ran in the fresh snapshot:

| Command | Exit | Actual outcome |
| --- | --- | --- |
| `pnpm install --frozen-lockfile` | 0 | PASS |
| `uv sync --project apps/api --locked --python 3.14.7 --extra dev` | 0 | PASS |
| `pnpm build:shared` | 0 | PASS |
| `pnpm type-check` | 0 | PASS: shared types, web and mobile |
| `pnpm test` | 0 | PASS: 189 passed, 5 deselected, 43.21s |
| `pnpm lint` | 0 | PASS: scripts, web, mobile and API Ruff |
| `pnpm type-check:api` | 0 | PASS: 14 source files |
| `pnpm build` | 0 | PASS: shared types and web production build |
| `pnpm check:mobile` | 1 | FAIL: `expo install --check`; subsequent Expo Doctor was NOT RUN because the script uses `&&` |
| `pnpm export:mobile` | 0 | PASS: fresh Android/iOS/web JavaScript bundles; not native compilation |
| `pnpm verify:static` | 0 | PASS: limited static structure check only |

Snapshot lockfile hashes were unchanged (PASS; in-process comparison, no separate command exit). The clean runner explicitly records live migrations/services and native device checks as NOT RUN. Its legacy final console sentence says Gate B acceptance is pending; that is not a new approval-status decision and does not supersede the [historical owner-approved Gate B record](gate-b-verification.md).

The [Expo check log](../.verification/clean-IG3WTB/9-check-mobile.log) reports these existing installed versions versus newly expected SDK 57 patches:

| Package | Installed | Expected by check |
| --- | --- | --- |
| expo | 57.0.27 | ~57.0.29 |
| expo-constants | 57.0.21 | ~57.0.22 |
| expo-linking | 57.0.12 | ~57.0.13 |
| expo-router | 57.0.25 | ~57.0.27 |
| expo-splash-screen | 57.0.9 | ~57.0.10 |

This is a separate dependency-maintenance issue, not caused by a manifest/lockfile change in this task. Dependencies were deliberately left unchanged. The overall clean workflow is FAIL, despite successful frozen installations, tests, builds and export; no all-green reproducibility claim is made.

## Final preservation and documentation checks

Fresh `git diff --check` and `git diff --cached --quiet` both returned 0. A PowerShell documentation check returned 0 for both edited documents: titles, balanced fences, whitespace and all six local Markdown links; an additional check covered whitespace/conflict markers in all three new files. No repository documentation-lint script is defined, so these were targeted checks, not a claimed full Markdown lint run.

The initial SHA-256 inventory covered 68 Git-visible files. The final comparison found exactly four existing files changed (the three existing test files and setup documentation listed above), three new files, and no removals. All other 64 existing files, including prior untracked work, retained their original hashes. Application source, manifests, lockfiles, migrations, runtime configuration and previous decision records match the starting working tree.

Fresh `git branch --show-current`, `git log -1 --format='%h %s'` and `git status --short` returned 0: branch `main`, commit `341a6b0`, 29 modified tracked files and 18 untracked files, nothing staged. The starting state was 29 modified tracked and 15 untracked files; the existing modifications were preserved. These counts include earlier work, not just this task's seven files.

## Remaining limits and review gate

- Docker/live PostgreSQL, Redis, UUIDv7 and migration round-trip tests are BLOCKED in this run. Historical successes are not fresh evidence. Docker Desktop's Linux engine must become available before the separately documented disposable procedure can be executed.
- No disposable service was started or stopped; no database, volume or service data was reset/deleted/modified. Build/test caches and the fresh verification snapshot were created or updated within the project and retained as evidence.
- URL validation cannot prove what process owns an approved local port. Check Docker readiness and intended disposable service identity before live execution; never connect to an unrelated service occupying those ports.
- Native Android/iOS compilation/device tests were NOT RUN. JavaScript export is not equivalent evidence.
- Review the guard diff and these limitations before accepting this safety change. No authentication, catalogue or P2-B work is authorized by this report; no commit, staging or branch change was performed.

## Case-alias correction and resumed verification — 2026-10-15

This amendment preserves the earlier results above. Source review found that exact-uppercase presence detection treated a lowercase/mixed-case DRIP_TEST_* alias as absent during `not integration`. Such aliases could not redirect effective targets, but silently ignoring them violated the explicit-input contract.

`prepare_test_environment` now scans keys before selection or mutation and rejects any visible case variant of either documented test variable with one fixed, value-free error. This also rejects aliases alongside uppercase keys, irrespective of their values. Canonical URLs, normal uppercase validation, no-input non-live defaults and inherited application-environment isolation remain unchanged. No further code correction was needed after resuming.

The correction changes `apps/api/tests/disposable_targets.py`, `apps/api/tests/test_disposable_targets.py`, and `docs/setup.md`; this resumed run additionally appends this verification record. No other source/configuration file was edited by the correction. The new tests comprise 26 alias cases (13 inputs under both live and non-live selection), two uppercase success cases and two fresh-process startup cases: 30 added cases, bringing the focused suite to 184. They cover lower/mixed case for each service, empty/malformed alias values, aliases alongside valid/invalid exact keys, both aliases together, fixed redacted errors and unchanged environment mappings on rejection. Existing no-input and invalid-URL regressions remain intact.

### Windows startup evidence and limits

The startup probe launches a fresh Python interpreter, receives case-preserving input through stdin JSON, and, for alias cases only, replaces that process's `os.environ` with `dict(os.environ) | payload["environment"]`. It then invokes real `pytest.main`, loading the unchanged real conftest `pytest_configure` hook; the guard is not mocked. Existing fail-on-call engine/pool/client/DNS/socket spies remain active. The non-live PostgreSQL-alias case omits both uppercase keys; the live Redis-alias case includes valid uppercase keys. Both assert pytest usage exit 4, no application-module imports, no infrastructure calls, and no URL/secret-marker disclosure, including with `--showlocals`.

This proves pre-collection rejection when aliases are visible to the hook, including ambiguous duplicate keys in a case-preserving mapping. It does not prove native Windows shell-key behavior or recover spelling lost by Windows/Python's uppercase normalization. Native Windows `os.environ` cannot represent those distinct aliases as separate keys. The guard's mapping-level gap is closed; no OS-level spelling enforcement is claimed. Neither test opens a network connection or executes a live integration test.

### Commands and outcomes for this correction

Commands ran from the repository root using the existing locked environment, with process-only settings:

```powershell
$env:PATH='C:\Users\batla\AppData\Roaming\npm;C:\Users\batla\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;'+$env:PATH
$env:UV_CACHE_DIR=Join-Path (Get-Location) '.cache\uv'
$env:UV_OFFLINE='true'
```

Fresh runtime output on resume: `node --version` = v24.19.0, `pnpm --version` = 9.15.9, `uv run --project apps/api --locked --extra dev python --version` = Python 3.14.7; all exit 0. No installation or upgrade was performed.

| Command/check | Exit | Evidence |
| --- | --- | --- |
| `uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml apps/api/tests/test_disposable_targets.py -q` | 0 | Pre-interruption tool output: 184 passed in 31.92s. Not redundantly rerun alone; all 184 cases also ran in the fresh full suite below. |
| `pnpm test` | 0 | Resumed run: 219 passed, 5 live tests deselected, 29.13s. |
| `pnpm lint:api` | 0 | Pre-interruption tool output: all Ruff checks passed. No code changes after that result. |
| `pnpm type-check:api` | 0 | Pre-interruption tool output: Mypy passed, 14 application source files. No code changes after that result. |
| `git diff --check` | 0 | Fresh resumed check passed. |
| `git diff --cached --quiet` | 0 | Fresh resumed check: nothing staged. |
| PowerShell documentation/file checks | 0 | Titles, balanced fences, local Markdown link targets, whitespace and untracked guard-file conflict markers checked. No separate repository Markdown-lint script is defined. |

Earlier failed/blocked attempts are retained: the first focused-test attempt exited 1 with `Failed to query Python interpreter: Access is denied (os error 5)` under the sandbox. The initial PATH exposed pnpm 11.25.0; the existing pinned pnpm executable was then selected without installation. The successful focused/Ruff/Mypy retries above followed. A pre-interruption `pnpm test` request was not executed because automatic approval review hit the usage limit (no process exit code); the resumed `pnpm test` completed successfully. These failures are not counted as passes.

No `pnpm test:integration`, Docker/service commands, native device tests or `pnpm verify:clean` were run for this correction. The earlier clean-workflow exit 1 at Expo SDK 57 compatibility validation remains unresolved and outside scope; its historic evidence is unchanged.

Fresh resume inventory contained 71 Git-visible files. A comparison against the original clean snapshot found changes only in the guard, its regression tests and setup documentation among its 69 recorded source files, corroborating the preserved correction. The resumed verification itself changes only this report; the other 70 inventoried files remain byte-identical. Branch remains `main` at `341a6b0`, with 29 modified tracked and 18 untracked files, nothing staged. No commit, branch switch, dependency/lockfile change, migration change, service action or database/volume change occurred. The correction remains uncommitted for owner review; no next milestone was started.

## Owner acceptance — 2026-10-17

The owner explicitly accepted the disposable-target case-alias correction on 2026-10-17 (Asia/Calcutta). This closes the correction's owner-review gate, with the documented environment-mapping boundary and Windows normalization limitation preserved. The earlier pending-review statements above describe their historical state.

This acceptance records the owner's decision; no tests, lint/type checks, builds, Expo validation or clean verification were independently rerun during this closeout. The 2026-10-15 correction evidence remains as recorded. Historical Gate B verification is unchanged and is not evidence of verification of this newer correction.

Live integration verification of the corrected working tree remains outstanding: the read-only `docker --context desktop-linux info --format '{{.OSType}}'` check exited 1 during this closeout because the `dockerDesktopLinuxEngine` named pipe was missing. No integration tests or service start/stop commands were run. The previous clean-workflow Expo dependency-validation failure remains unresolved; accepting this correction does not accept that failure, authorize dependency changes or authorize another implementation milestone. All changes remain uncommitted.
