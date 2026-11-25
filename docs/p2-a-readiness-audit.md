# P2-A readiness audit and next-milestone selection

Date: 2026-10-20 (Asia/Calcutta). Scope: repository inspection and planning only.

**Recommendation: continue P2-0 with its decision, threat-model and contract preparation work. No product-code milestone is currently READY.** P2-0 is PARTIALLY READY: its independent documentation work can proceed, but its decision closure cannot be declared complete. P2-1 is the first product implementation milestone once its applicable prerequisites are resolved; do not skip it to implement public discovery or catalog persistence.

The SDK 57 patch-alignment task and latest five-test live verification are completed. They are not proposed for another run. Authentication remains paused under ADR 0002. This audit neither authorizes coding nor resolves an owner decision.

## Sources and precedence

Line references below identify the current inspected versions; headings are the durable reference if later amendments move lines.

| Source reviewed | Relevant evidence / authority |
| --- | --- |
| [Phase 2 specification and plan](phase-2-specification-and-plan.md) | Lines 3–15: approval, P2-A authorization and later amendments; 326–403: P2-0 through P2-6; 338–355: dependency checkpoint; 474–479: D2–D7; 485–503: approval checklist |
| [ADR 0002](adr/0002-cognito-authentication-decision.md) | Lines 14–39: authentication/access precedence and settled requirements; 117–129: C1–C7; 148–157: authentication review gate |
| [ADR 0001](adr/0001-modular-monolith-foundation.md) | Architecture, exact money, PostgreSQL authority, modular boundaries and approval history |
| [Gate B verification](gate-b-verification.md) | Line 3 and “Resumed live verification - 2026-10-12”: owner approval and historical foundation results, not a fresh product test |
| [Disposable-target guard verification](disposable-target-guard-verification.md) | “Case-alias correction and resumed verification” and “Owner acceptance — 2026-10-17”: accepted guard correction, 184 focused cases and recorded 219-test non-live suite; Windows mapping limitation retained |
| [SDK 57 alignment verification](expo-sdk-57-patch-alignment-verification.md) | Completed patch alignment, fresh-source software verification, actual exits and closeout evidence limits; owner approval is confirmed by the current instruction |
| [Docker/live integration report](docker-live-integration-readiness-verification.md) | “Authorized disposable execution — 2026-10-20,” lines 93–186: five tests passed, rollback/connection cleanup and scoped shutdown; earlier BLOCKED sections are historical |
| [Setup](setup.md) | Actual pinned tools, scripts, isolated service procedure and verification boundaries |

Read the saved `.verification/clean-vZlufW/verification-results.json`, `.verification/live-20261020-b00f8038/execution-results.json` and `09-after-shutdown.json`. The former records all 11 executed software checks at exit 0; the latter records 5 live tests passed / 219 deselected, exit 0, and zero remaining task containers/networks/volumes/listeners. The failed initial mount-inspection assumption and successful correction remain in the live record. No test, build, provider operation or Docker query was executed for this audit.

Repository inspection: `main`, HEAD `341a6b031a6eda018d0b3df88f2baca5f88fbe94`; initially 29 modified tracked files, 20 untracked files and nothing staged. Scoped search found no `AGENTS.md` or separately named constitution. ADRs, the approved plan and engineering rules in `apps/api/src/drip/models/base.py` apply. Existing work is user-owned and must remain intact.

On resumption, fresh inspection confirmed the same branch/HEAD, 29 modified tracked files, **21 untracked files** (including this existing draft), and nothing staged. The draft already contained the source review, seven-milestone matrix, owner-decision register and next-task plan; only closeout and evidence clarifications were needed.

Evidence limits: saved machine-readable results support the completed clean checks and live run. The SDK report explains that standalone/outer-command exit codes were recorded in the original execution-tool results, not in log footers; this audit does not independently reconstruct those shell exits. No missing evidence changes the readiness conclusion. Native/device and real identity-provider acceptance remain unperformed requirements for their future milestones, not newly failed foundation checks.

## Actual foundation versus proposed features

- `apps/api/src/drip/api/router.py` currently mounts only the health router. `api/v1/health.py` provides liveness/readiness; no identity, catalog, discovery, wishlist or admin routes exist.
- `models/base.py` supplies UUIDv7 and timestamps. Only migrations `0001_initial_baseline.py` and `0002_require_pg18_uuidv7.py` exist. They do not create the proposed identity/catalog/wishlist tables.
- `apps/mobile/app/index.tsx` and `apps/web/src/app/page.tsx` remain static shells. Their hardcoded healthy labels are not product or live-provider evidence.
- `packages/shared-types/src/index.ts` contains health/error types, broad enums and `MoneyAmount.amount_minor: number`. The approved catalog decimal-string money contract is still future work (plan lines 258–267); current enums do not implement purchase modes or inventory.
- Foundation tests cover configuration/security/errors, guard behavior, migrations/UUID defaults and health. Root `package.json` has no `test:mobile`, `test:web` or `test:contracts` script. The proposed behavior runners are not installed capabilities merely because the plan names them.

The approved plan's dated foundation inventory is stale in three concrete places: Expo 57.0.27 is now 57.0.30; the name-only target-guard concern and suggested guard work at lines 54/349–351 are completed; the old 35-test non-live evidence has a later recorded 219-test suite. The old Docker and Expo blockers in earlier reports were subsequently resolved. Treat these as historical snapshots, not reasons to redo work or weaken the remaining gates. Container digest pinning is a separate recommendation, not the next mandatory product dependency. Future publication-target protection remains its own requirement; the test-only guard does not implement it.

## Readiness matrix

READY means the scoped work has its required inputs and approvals; it does not mean implemented. PARTIALLY READY means independent preparation can proceed, while a named part of the milestone remains gated. BLOCKED means the milestone's implementation/acceptance cannot start or complete under the current dependency order. Completed foundation work is distinguished from milestone readiness.

| Milestone | Status | Documented dependencies | Finding and requirement supporting it |
| --- | --- | --- | --- |
| **P2-0 — freeze decisions, identity boundary and contracts** | **PARTIALLY READY** | Specification approval and separate P2-A authorization; applicable C1–C7, D2–D5, D7 inputs for closure | Approvals and foundation safety/verification are present. Trust boundaries, negative-test matrices, DTO examples and source-approval templates may be drafted while decisions remain visibly pending. Full contract closure still needs the decisions and compatible UI/contract tooling selection. Plan lines 326–340 and 336 expressly permit this preparation. |
| **P2-1 — identity and privileged access foundation** | **BLOCKED** | P2-0/D1; C1–C7; named D3 grant authority; real-provider/native prerequisites for acceptance | Authentication is explicitly paused. Pool/flow/session/MFA/linking/deletion details cannot be assumed from Cognito selection. No account/session/grant migrations or exposed auth routes yet. Plan lines 341, 353–363; ADR 0002 lines 121–129, 154–157. |
| **P2-2 — shared catalog persistence/publication** | **BLOCKED** | P2-0 and P2-1 operator identity; D2–D5 catalog policies and approved sources | Seven entities/publication service require authenticated operator attribution and fixed taxonomy, money ceiling, rights/hosts, destinations, freshness and retention rules. Pure examples may be planned now; that is not authorization to build catalog schema ahead of P2-1. Plan lines 342, 365–371. |
| **P2-3 — controlled admin catalog** | **BLOCKED** | P2-1/P2-2, D2/D3; current grants and approved real content | Needs the publication service plus named operators, rights approval and C1/C4 privileged assurance. A bootstrap CLI cannot substitute for the admin UI. Plan lines 343, 373–379. |
| **P2-4 — Discover API/authenticated wishlist** | **BLOCKED** | P2-1 through P2-3; D2/D4/D5, C6 public abuse controls, C3/C4/C7 private ownership/lifecycle | Guest access does not remove controlled-publication dependencies. D8/D9 are approved, but persistence, ownership, deletion and refresh must be implemented and tested separately. Plan lines 344, 381–387. |
| **P2-5 — mobile customer loop** | **BLOCKED** | P2-1/P2-4; D3 artwork, C2 callbacks, D7 native/build/distribution access | Shells/export success do not implement the loop. Requires working identity/private APIs and public catalog, behavior-test tooling and real Android/iOS evidence. D7 does not prevent drafting test cases, but blocks native acceptance. Plan lines 345, 389–397. |
| **P2-6 — P2-A acceptance and owner review** | **BLOCKED** | P2-1 through P2-5; complete section 9 evidence and explicit owner acceptance | Must demonstrate admin publication through guest browsing, confirmed authenticated save and second-device refresh on real builds/provider flows. Foundation approval and five infrastructure tests do not satisfy this. D6 is not a P2-A dependency. Plan lines 346, 399–403. |

Dependency order: **P2-0 applicable contract closure → P2-1 → P2-2 → P2-3 → P2-4 → P2-5 → P2-6.** P2-5 also directly depends on P2-1. Real source preparation and decision collection can happen alongside contract drafting; feature implementation cannot silently reorder this sequence.

P2-B/OOTD is excluded from the next work package. Plan lines 405–407 require P2-A acceptance, separate P2-B authorization, D6 editorial/source/rights inputs and D7 native access. Guest OOTD browsing is settled; it is not permission to implement the feed now. Checkout, orders, payments, settlements and spreadsheet ingestion remain outside this scope.

## Single next milestone: P2-0 decision and contract preparation

This is the only documented next milestone with work eligible now. Its first work package is documentation/specification, not a newly invented product-code milestone. The earlier independent guard package is finished. If “next implementation” means production code, **there is no eligible product-code start today**; the conditional first group is P2-1 below.

Prerequisites already satisfied: planning baseline approved, P2-A separately authorized, guard safety accepted, SDK alignment approved and live verification complete. Remaining owner decisions must remain explicitly pending while their alternatives and tests are prepared. This audit stops after the plan; it does not begin the following work package.

### Proposed files for the next P2-0 work package

| File | Planned use |
| --- | --- |
| `docs/p2-0-contracts-and-acceptance.md` — proposed new file, absent today | One bounded package: trust-boundary diagram, decision dependencies, public/private DTO examples, acceptance-case matrix and tooling proposal. No executable schemas or test fixtures. |
| `docs/adr/0002-cognito-authentication-decision.md` — existing | Record owner-supplied C1–C7 choices as dated amendments only after supplied/reviewed; preserve original history and remaining pending choices. Do not populate credentials or provider identifiers by guesswork. |
| `docs/phase-2-specification-and-plan.md` — existing | Append a current dependency checkpoint and approved operational decisions when provided; preserve historical inventories and test evidence. |
| `docs/p2-a-readiness-audit.md` — this deliverable | Update eligibility when decisions are actually resolved. |

No implementation test file, dependency, runtime configuration or migration is needed for this documentation package.

### Execution sequence and measurable exit criteria

1. **Prepare the decision packet.** For each C/D item below, record owner, exact choice needed, proposed default already in the baseline, affected behavior, evidence required and status. Do not select a default for the owner. Exit: every open item has an explicit downstream gate; no pending choice appears as deployed behavior.
2. **Specify identity and admin trust boundaries.** Separate customer/admin proof, provider credentials, DRIP authority, ephemeral abuse controls and public catalog access. Describe threats and negative cases without fixing unresolved C1–C7 mechanics. Exit: callback/session fields that depend on C2/C4 remain labelled pending; no same-email privilege/linking shortcut.
3. **Specify stable contract examples.** Document exact INR digit-string serialization/BIGINT bounds, null inventory, public DTO field exclusion, stale/missing price semantics, safe errors, source approvals and public-card-to-confirmed-save transitions. Mark D2 ceiling/taxonomy and D5 time/retention values pending. Explain the future migration from the existing numeric money type; do not alter that type now. Exit: every example traces to an approved rule and avoids real personal data, secrets or fabricated production catalog entries.
4. **Design test cases and tooling.** Map each requirement to unit/API/contract/integration/UI/native evidence. Compare compatible runner options against official version-sensitive documentation when doing that tooling proposal, without installing anything. Exit: selected future commands/versions are reviewable; proposed commands are not presented as existing scripts.
5. **Obtain targeted decisions and review.** Record dated owner resolutions in the controlling documents. P2-1 may become eligible after its security contract and named admin authority are resolved and the authentication documentation review gate is released; D2/D4/D5 do not unnecessarily block the first identity-only group. They continue to block their catalog/publication dependents. Full P2-0 closure additionally accounts for D7 and the other operational inputs.

Drafting can complete with pending decisions clearly recorded; that is completion of the preparation package, not full P2-0 acceptance or release of authentication. Rollback of a proposal is a further documentation amendment, not a Git reset or a database action.

### Acceptance cases to specify now, execute only with future implementation

| Area | Required cases, drawn from the approved plan |
| --- | --- |
| Proof/realm | Wrong issuer/client/token purpose, signature/key/algorithm errors, replay, expiry, unverified email and customer proof on admin paths; safe failure/redaction. |
| Session/admin | Seven-day policy, immediate DRIP disable/grant revocation, provider-side changes, recent-MFA evidence and lost-factor recovery; no self-grant. C1/C4 must settle exact boundaries and renewal semantics. Include no refresh-based deadline extension as a case for the proposed absolute-expiry option, not an already approved technical choice. |
| Linking/privacy | Matching-email accounts do not auto-merge; prove-both-identity flow only if approved; deletion-pending access denied, provider retries and within-30-day measurement, minimum approved audit/backup handling. |
| Money/visibility | Positive exact paise digit strings, values beyond JS safe integer precision, BIGINT overflow/invalid syntax/currency rejection; null inventory; no older-price fallback; same-variant filtering; no private/audit fields in public DTOs. D2/D5 policy constants remain pending. |
| Guest save | Preserve card on sign-in cancellation/failure; no guest account/wishlist/local authoritative save; explicit post-auth confirmation; recheck product eligibility; no success/advance until backend acknowledgement. |
| Wishlist | Two-account isolation, account-switch cache clearing, same-account two-device save/remove/clear after refresh; no offline mutation replay. |
| Publication | Named current grant/strong session, rights/source/host validation, preview writes zero rows, stale revisions/conflicts, same-key retries, atomic rejection and retained history. No production seed or fallback. |
| Abuse/outages | Anonymous browsing and identity abuse controls; rate-limit dependency failure closed; Cognito outage does not itself block otherwise healthy public browsing or permit private access. Exact quotas remain C6 decisions. |

Documentation acceptance checks for that package: valid local links, balanced fences, no stale approval statements masquerading as current status, complete requirement-to-case coverage, fresh before/after Git inventory, `git diff --check`, and `git diff --cached --quiet`. These are prose checks, not runtime verification.

## Owner decisions required, without reopening settled product choices

All seven C items remain open in ADR 0002 lines 121–127. The “default” column there is proposed, not owner approval.

| Decision | Exact owner input still needed | First affected gate |
| --- | --- | --- |
| C1 | Admin factor/assurance choice; enrollment and recent-MFA proof; lost-factor recovery, approvers and emergency process; admin session/freshness policy | P2-1 admin boundary; later P2-3 |
| C2 | Google project/consent ownership, scopes/attribute mapping, environment/client ownership, domains and exact callback/logout allowlists | P2-1 proof/callback design; later P2-5 |
| C3 | Whether linking is enabled or staged; collision handling, confirmation/proof, protected email-index/normalization policy and existing-profile reconciliation | P2-1 mapping/schema; later wishlist ownership |
| C4 | Seven-day absolute/idle enforcement; opaque-session versus JWT binding; token custody/encryption/refresh, logout scope, fresh-auth and provider-side disable propagation | P2-1 session/schema/authorization; later private actions |
| C5 | AWS/environment ownership, Cognito/SES region, residency expectations, sender/domain/reply-to/DNS, delivery operations, sandbox exit and budget | P2-1 environment/real-provider acceptance |
| C6 | Password/email-change/recovery policy, customer MFA posture, Cognito tier/protections, abuse quotas and email budget | P2-1 identity; P2-4 public abuse controls |
| C7 | Minimum audit fields/retention, deletion/suppression/retry workflow, backup restoration, deadline measurement and escalation | P2-1 persistence/privacy; later saves/admin audit |
| D2 | Exact pilot audience/cohort, approved brands/categories, size/color vocabulary and price sanity ceiling | P2-2 schema/validation and real-data acceptance; P2-4 filters |
| D3 | Named admin/grant/approval authorities; permitted source/image rights and hosts; real catalog supply; branding assets | Named authority blocks P2-1; content blocks P2-2/P2-3; artwork blocks P2-5 acceptance |
| D4 | Exact retailer destinations, disclosure and approved destination-host policy | P2-2/P2-3 publication; P2-4/P2-5 link-out behavior |
| D5 | Price freshness interval, refresh operator and source/approval evidence retention | P2-2/publication, P2-4 visibility; seven days/90 days remain proposals |
| D7 | Android/iOS device/simulator and build/signing access, pilot audience/distribution scope | Native/provider and two-device acceptance in P2-1/P2-5/P2-6; not independent documentation or server unit-test preparation |
| D6 | Editorial owner, rights/sources, presentation and release sequencing | P2-B only; not a reason to block P2-A acceptance |

Do not ask again whether to use Cognito, Google/email-password, no phone collection, guest browsing, permanent authenticated saves, cross-device wishlist, the established gestures or shared controlled admin catalog. These are settled. The seven-day policy, verified-channel recovery, immediate DRIP-side revocation, 30-day private deletion target and minimal approved audit are also settled; their implementation/security semantics still need the C decisions. External redirects are the only enabled initial purchase mode; hybrid extensibility is retained.

## Conditional first product-code group: P2-1, not eligible yet

Once C1–C7's required contract choices are recorded/reviewed, the authentication pause is released and D3 supplies named grant authority, start the plan's specified **fail-closed identity configuration and server proof-validation boundary** (plan lines 353–355). Real provider access is needed for full milestone acceptance; offline doubles alone cannot establish it. This section is a future execution plan, not permission to implement now.

Likely files for that first small group, all proposed additions unless marked existing:

- `apps/api/src/drip/identity/__init__.py`
- `apps/api/src/drip/identity/config.py` — proposed placement for validated identity configuration; integrate with existing `apps/api/src/drip/core/config.py` only as required by the approved loading convention.
- `apps/api/src/drip/identity/provider.py` — proof validation/realm boundary behind an explicit service interface.
- `apps/api/tests/test_identity_config.py`
- `apps/api/tests/test_identity_provider.py`
- `apps/api/tests/test_identity_errors.py`
- Existing `docs/adr/0002-cognito-authentication-decision.md` and proposed `docs/p2-0-contracts-and-acceptance.md` for requirement/test traceability.

Tests first: rejected issuer/client/purpose/realm/key/expiry/replay/email evidence, safe failures and log redaction, plus valid approved proof cases. No exposed login route, permissive auth stub, production mock or provider provisioning in this first group. The validation boundary must not be presented as complete revocation/session enforcement.

No schema change is required for that first group. Later independently reviewed P2-1 groups introduce `identity/models.py`, `identity/schemas.py`, `identity/service.py`, `api/v1/auth.py`, session/grant persistence and the minimal approved mobile/admin flows. Use new Alembic revisions after the then-current head (currently 0002), never rewrite 0001/0002. Exact migration identifiers are assigned at implementation; no catalog/outfit/order schema belongs in P2-1. Session/grant enforcement must be ready before exposing authenticated routes.

After those files actually exist, the proposed focused command is:

```sh
uv run --project apps/api --locked --extra dev pytest -c apps/api/pyproject.toml apps/api/tests/test_identity_config.py apps/api/tests/test_identity_provider.py apps/api/tests/test_identity_errors.py
```

Existing verification commands to use after affected future changes are `pnpm test`, `pnpm lint:api`, `pnpm type-check:api`; then the applicable shared/web/mobile checks (`pnpm build:shared`, `pnpm type-check`, `pnpm lint`, `pnpm build`, `pnpm check:mobile`, `pnpm export:mobile`) and `pnpm verify:clean` at the implementation checkpoint. New migrations/persistence require isolated live tests under the documented guarded lifecycle, with exact selection and cleanup evidence. Frozen installation/locked Python sync are part of the existing clean workflow; dependency additions require compatibility review and genuine locks. Do not run any of these now for this audit.

Before P2-1 acceptance, run real authorized Google/email verification/recovery/admin-MFA flows, approved session/revocation/deletion scenarios and native evidence. Before P2-6, add the selected web/mobile/contract runners to the root/clean workflow and demonstrate the full admin-to-cross-device-save path. `pnpm test:mobile`, `pnpm test:web` and `pnpm test:contracts` remain proposals until actually implemented. A future rollback disables affected routes and preserves user/audit data; no populated-database downgrade.

## Audit validation and stop condition

Only this audit document was created by the original audit and completed during this resume. No application source, test, migration, manifest, lockfile, environment or configuration is changed. No runtime verification is repeated, no infrastructure is started, and no provider configuration is accessed.

Fresh closeout checks (2026-10-20):

| Check | Actual result |
| --- | --- |
| PowerShell local-link/structure check | Exit 0: eight local links resolve; code fences balanced; no conflict markers or trailing whitespace; all seven milestone rows and C1–C7/D2–D5 decision rows present. |
| `git diff --check` | Exit 0. Existing LF-to-CRLF notices are Git warnings, not failed checks; no line-ending conversion was performed. The untracked audit's whitespace is covered by the separate prose check. |
| `git diff --cached --quiet` | Exit 0: nothing staged. |

The fresh resume inventory covered 74 Git-visible files. SHA-256 comparison found only this audit changed; the other 73 were byte-identical, with no additions or removals during resume. Ignored verification artifacts were only read and were not included in this hash inventory. Final Git state remains `main` at `341a6b031a6eda018d0b3df88f2baca5f88fbe94`, with 29 modified tracked files, 21 untracked files and nothing staged. A preliminary wildcard-based untracked count incorrectly included tracked entries; the corrected literal-prefix count is 21. No staging, commit or branch change occurred.

The first inventory search included an absent `.agents` directory and reported that missing path; the subsequent repository-wide scoped instruction search found no applicable instruction file. This is a search-path diagnostic, not a failed test. Reports and saved JSON were read, not generated again.

Immediate next task: prepare the bounded P2-0 decision/threat-model/contract packet above, retaining unresolved choices as pending and returning it for owner review. Stop after this audit; do not begin that preparation package, authentication or another milestone within this turn.
