# Expo SDK 57 patch-alignment verification

Date: 2026-10-20 (Asia/Calcutta). Scope: owner-authorized dependency maintenance only. This record is separate from historical Gate B and disposable-target correction evidence.

Outcome: **PASS for the authorized software verification scope.** Owner review of this uncommitted patch remains separate from command success.

## Baseline and compatibility evidence

The starting branch was `main`, HEAD `341a6b0`, with 29 modified tracked files, 18 untracked files and nothing staged. The starting SHA-256 inventory covered 71 Git-visible files, including prior untracked work. No repository work was discarded or made artificially clean.

Reviewed the root/mobile manifests, mobile `app.json`, `pnpm-lock.yaml`, runtime pins, `.npmrc`, foundation ADR, setup/verification documentation, the actual package scripts and clean runner, and `.verification/clean-IG3WTB/{9-check-mobile.log,verification-results.json}`. No applicable `AGENTS.md` was found. The October 15 snapshot failed compatibility validation; it is historical evidence, not the recommendation source for this change.

Official sources consulted on October 20:

- [Expo SDK 57 release](https://expo.dev/changelog/sdk-57).
- [SDK 57 reference](https://docs.expo.dev/versions/v57.0.0/).
- [Expo's supported upgrade and dependency-validation workflow](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/).

The repository-resolved CLI was also inspected: its dependency checker prefers online SDK recommendations over the bundled compatibility map when available. A fresh `expo install --check` reported Expo `~57.0.30`, Constants `~57.0.22`, Linking `~57.0.13`, Router `~57.0.28` and Splash Screen `~57.0.10`. This supersedes the saved Expo `~57.0.29` / Router `~57.0.27` recommendations. SDK 57 was retained; the generic documentation's instruction to choose a latest SDK was not used to upgrade the major.

## Dependency changes

| Mobile dependency | Starting range / resolved version | Final range / resolved version | Reason |
| --- | --- | --- | --- |
| `expo` | `57.0.27` / 57.0.27 | `57.0.30` / 57.0.30 | Fresh SDK 57 recommendation; preserve exact pin |
| `expo-constants` | `~57.0.21` / 57.0.21 | `~57.0.22` / 57.0.22 | Fresh compatibility recommendation and Router peer |
| `expo-linking` | `~57.0.12` / 57.0.12 | `~57.0.13` / 57.0.13 | Fresh compatibility recommendation and Router peer |
| `expo-router` | `~57.0.25` / 57.0.25 | `~57.0.28` / 57.0.28 | Fresh compatibility recommendation |
| `expo-splash-screen` | `~57.0.9` / 57.0.9 | `~57.0.10` / 57.0.10 | Fresh compatibility recommendation |
| `@expo/metro-runtime` | Undeclared direct dependency; auto-resolved 57.0.16 | `~57.0.17` / 57.0.17 | Explicitly satisfy Router 57.0.28 and router-server's `^57.0.17` peer; Expo 57.0.30's compatibility map selects this range |

The first five changes left pnpm's old auto-resolved Metro Runtime peer at 57.0.16. Declaring the compatible peer through Expo's installer removed that mismatch. This is an Expo runtime patch, not an upgrade of the Metro framework or React Native Metro configuration.

The package manager regenerated the lockfile. Beyond those six dependencies, these are all changed package versions and their dependency reasons:

| Transitive package | Before → after | Dependency path |
| --- | --- | --- |
| `@expo/cli` | 57.0.28 → 57.0.31 | Expo 57.0.30 requires `^57.0.31`; not an independent CLI upgrade |
| `@expo/fingerprint` | 0.20.13 → 0.20.14 | Expo |
| `@expo/local-build-cache-provider` | 57.0.8 → 57.0.9 | Expo |
| `babel-preset-expo` | 57.0.14 → 57.0.16 | Expo |
| `expo-asset` | 57.0.19 → 57.0.20 | Expo |
| `expo-modules-autolinking` | 57.0.14 → 57.0.16 | Expo / prebuild-config |
| `expo-modules-core` | 57.0.21 → 57.0.23 | Expo |
| `expo-modules-jsi` | 57.1.1 → 57.1.2 | modules-core |
| `@expo/inline-modules` | 0.1.7 → 0.1.8 | Expo CLI |
| `@expo/prebuild-config` | 57.0.17 → 57.0.19 | Expo CLI |
| `@expo/router-server` | 57.0.12 → 57.0.13 | Expo CLI |
| `@expo/ui` | 57.0.22 → 57.0.25 | Expo Router |

Other lockfile changes re-key peer contexts for the updated Expo packages. All other workspace direct dependency ranges and resolved base versions remain unchanged. Lock settings and metadata for unchanged package versions also remain unchanged. React/React DOM 19.2.3, React Native 0.86.3, `@react-native/metro-config` 0.86.3, TypeScript 6.0.3 and Expo Doctor 1.20.4 were retained. No package exclusions, warning suppressions or weakened verification were introduced.

## Commands and evidence

Used existing Node 24.19.0 and pnpm 9.15.9, confirmed by fresh version commands (exit 0). Commands ran from the repository root unless marked as clean-snapshot checks. Existing caches/store were selected through process-only environment variables; no runtime pins or configuration files changed.

```powershell
$env:PATH='C:\Users\batla\AppData\Roaming\npm;C:\Users\batla\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;'+$env:PATH
$env:CI='1'
$env:EXPO_NO_TELEMETRY='1'
$env:EXPO_HOME=Join-Path (Get-Location) '.cache\expo'
$env:UV_CACHE_DIR=Join-Path (Get-Location) '.cache\uv'
$env:GIT_CONFIG_GLOBAL='NUL'
$env:GIT_CONFIG_NOSYSTEM='1'
$env:GIT_OPTIONAL_LOCKS='0'
$env:npm_config_store_dir=Join-Path (Get-Location) '.pnpm-store'
$env:npm_config_cache=Join-Path (Get-Location) '.cache\npm'
```

Evidence and pre-edit manifest/lockfile copies are retained in `.verification/expo-sdk57-20261020-e2789779/`. Shell wrappers captured command output with `Tee-Object`, saved `$LASTEXITCODE` and exited with that code. The clean runner additionally records individual exit codes in its results JSON.

| Command | Exit | Actual result / log |
| --- | --- | --- |
| `pnpm --filter mobile exec expo install --check` (baseline) | 1 | Five outdated dependencies; `01-baseline-expo-check.log` |
| `pnpm view expo@57.0.30 dependencies --json` | 0 | Inspected published dependency requirements; `02-expo-target-dependencies.json` |
| `pnpm view expo-router@57.0.28 dependencies --json` | 0 | Inspected published dependency requirements; `03-router-target-dependencies.json` |
| `pnpm --filter mobile exec expo install expo@57.0.30 --pnpm -- --save-exact` | 1 | CLI rejected argument forwarding: `Unexpected: --save-exact`; no install occurred; `04-install-expo.log` |
| `pnpm --filter mobile exec expo install expo@57.0.30 --pnpm` | 0 | Retried with process-only `npm_config_save_exact=true`; `05-install-expo-retry.log` |
| `pnpm --filter mobile exec expo install expo-constants@~57.0.22 expo-linking@~57.0.13 expo-router@~57.0.28 expo-splash-screen@~57.0.10 --pnpm` | 0 | Four recommended patches; `06-install-mobile-patches.log` |
| `pnpm --filter mobile exec expo install @expo/metro-runtime --pnpm` | 0 | Expo selected `~57.0.17`; `08-align-required-expo-peer.log` |
| `pnpm install --frozen-lockfile` | 0 | Lockfile up to date; resolution skipped; `09-frozen-install.log` |
| `pnpm check:mobile` | 0 | Dependencies up to date; Doctor 21/21 passed; `10-check-mobile.log` |
| `pnpm --filter mobile exec expo-doctor` | 0 | Independent Doctor run: 21/21 passed; `11-independent-doctor.log` |
| `pnpm export:mobile` | 0 | Shared build plus web/Android/iOS JavaScript export, 52 assets; `12-export-mobile.log` |
| `pnpm verify:clean` | 0 | All 11 executed software checks passed; `13-verify-clean.log` and snapshot results below |

A read-only Node diagnostic during pnpm relinking briefly failed with `ENOENT` for the Expo manifest. The read was repeated successfully after installation completed. This was not a passed verification check or an unresolved installation failure. Install output also contained pre-existing ESLint/uuid deprecation notices; unrelated dependencies were not updated.

## Final verification and preservation

`pnpm verify:clean` created `.verification/clean-vZlufW/` from 70 Git-visible source files before this new report was written. Its preflight confirmed no copied `node_modules`, `.venv`, local `.env`, generated declarations, shared-types output or framework build output. It created a new Python environment and installed JavaScript dependencies from the frozen lockfile. The existing package/download caches were reused; this is fresh-source/environment evidence, not an empty-cache or separate-machine test.

Detailed evidence is retained in that snapshot's `verification-results.json` and numbered logs. Commands below ran inside that fresh snapshot using the same pinned tools:

| Command/check | Exit | Actual result |
| --- | --- | --- |
| `pnpm install --frozen-lockfile` | 0 | Installed 850 packages from the existing store; manifest/lockfile resolution accepted |
| `uv sync --project apps/api --locked --python 3.14.7 --extra dev` | 0 | New CPython 3.14.7 environment; 58 packages installed |
| `pnpm build:shared` | 0 | Built shared-types from source |
| `pnpm type-check` | 0 | Shared-types, web route generation/types, and mobile types passed |
| `pnpm test` | 0 | 219 passed, 5 live tests deselected, 40.96 seconds |
| `pnpm lint` | 0 | Root scripts, web/mobile ESLint and API Ruff passed; Ruff includes tests, migrations and scripts |
| `pnpm type-check:api` | 0 | Mypy: no issues in 14 application source files |
| `pnpm build` | 0 | Shared-types and Next.js production build passed; 3 static pages generated |
| `pnpm check:mobile` | 0 | Dependencies up to date; Doctor 21/21 passed |
| `pnpm export:mobile` | 0 | Web, Android and iOS JavaScript bundles exported from fresh source; 52 assets |
| `pnpm verify:static` | 0 | Static structure checks passed; does not itself verify runtime behavior |
| Lockfile hash comparison | N/A | PASS: JavaScript and Python lockfiles unchanged throughout the clean workflow |

The root `test`, `lint`, `type-check` and `build` commands were executed and individually reported by this workflow, so they were not redundantly rerun in the original working tree. No required software check was skipped or blocked.

Final checks: `git diff --check` and `git diff --cached --quiet` returned 0. Targeted report checks cover its heading, balanced fences, trailing whitespace, conflict markers and local link targets; there is no dedicated Markdown-lint package script. The task-only manifest and complete semantic lockfile delta were reviewed against the pre-edit copies. The lockfile delta is 149 added / 146 removed lines relative to this task's baseline, rather than the larger accumulated diff against HEAD.

Exactly these Git-visible files changed during this task:

- `apps/mobile/package.json`: five compatible patches and the required explicit Expo runtime peer.
- `pnpm-lock.yaml`: genuine pnpm resolution of that Expo dependency graph.
- `docs/expo-sdk-57-patch-alignment-verification.md`: this new evidence record.

The final SHA-256 comparison covered 72 Git-visible files: the two changed existing files above, this one new file, no removals, and 69 unchanged existing files. Root/web/shared manifests, runtime pins, application source, tests, migrations, configuration and previous reports remain byte-identical to the starting working tree. The mobile manifest and lockfile were also unchanged between the post-install inventory and completion of verification. Ignored package caches, installed dependencies, exports and verification artifacts were generated/updated as expected and retained.

Fresh final Git output: branch `main`, HEAD `341a6b0`, 29 modified tracked files and 19 untracked files; nothing staged. The extra untracked file is this report. All earlier tracked/untracked work was preserved. No stage, commit, branch switch, reset, clean, revert or stash operation occurred.

## Remaining limitations

- `pnpm test:integration`, Docker readiness, PostgreSQL/Redis checks and live migrations were **NOT RUN**, as required for this task. No service was started/stopped and no database, volume or service data was changed. The historical Linux-engine blocker was not reassessed here.
- Native Android/iOS compilation, signing, installation and device tests were **NOT RUN**. A JavaScript export is not evidence for those checks.
- The fresh-copy verification reuses dependency caches and the same Windows host. It does not establish offline installation from an empty cache, separate-machine reproducibility or native runtime behavior. Exported filenames differ between working-tree and snapshot builds; byte-identical builds are not claimed.
- Expo recommendations can advance after this dated check. The exact current resolution is recorded in the lockfile; future changes need their own review.
- The unchanged clean runner prints the older generic footer “Gate B acceptance remains pending.” That footer is stale status text, not a new owner decision: Gate B remains owner-approved. This task did not alter the runner or historical reports.
- Non-failing output included empty-build-cache notices and Node color-environment warnings. No validation was suppressed to obtain these passes.

No product implementation, authentication/provider setup or further milestone was begun. This patch remains uncommitted for owner review.

## Resumed closeout audit — 2026-10-20

The report was already complete on resume. This amendment clarifies evidence provenance; it does not record a new test run or dependency change.

Re-read the saved command logs and `.verification/clean-vZlufW/verification-results.json`. The JSON directly records exit code 0 for all 11 executed checks, a passing clean-source preflight, unchanged lockfiles, and the explicit live/native NOT RUN entry. The test log confirms 219 passed / 5 deselected; both saved Doctor logs confirm 21/21. The standalone logs and outer clean-workflow log do not include their shell wrappers' final `EXIT_CODE` lines. Their exact exit codes in the tables above come from the original execution-tool results, not from newly running those commands or inferring numeric codes from success text. In particular, the original `pnpm verify:clean` tool result recorded exit 0; the saved JSON independently supports all of its constituent results.

A fresh SHA-256 comparison found all 70 source files listed by that verified snapshot byte-identical to the current working tree, including both lockfiles and all manifests. Comparison with the saved pre-edit mobile manifest and lockfile confirms the six direct changes and 12 additional transitive patches listed above, with no additional dependency changes. The original 71-file starting hash map was held in the earlier execution session rather than persisted as an artifact: the earlier 69-unchanged-file result is retained as original tool evidence, but cannot be independently reconstructed solely from that hash-map file on disk. This closeout does not present it as a newly repeated pre-task inventory check.

This resumed run changes only this report. A separate before/after closeout inventory, fresh `git diff --check`, staged-state check and focused documentation checks verify preservation during the resumed run. No installation, test, build, export, network compatibility refresh, service action or database operation was repeated. Final branch and HEAD remain `main` / `341a6b031a6eda018d0b3df88f2baca5f88fbe94`, with 29 modified tracked files, 19 untracked files and nothing staged.
