# DRIP product vision: implementation status and recommendations

**Prepared:** 2026-11-20 (Asia/Kolkata)
**Purpose:** Reconcile the expanded product idea with the repository and recommend a realistic, staged product and technical direction. This is a planning document, not implementation authorization.

## Executive recommendation

DRIP can become a fashion-discovery product with four complementary experiences: eligible product discovery, curated complete looks, a private digital wardrobe, and progressively more advanced try-on. Build them in that order. The first two already have meaningful API and UI foundations; account-backed saves and administrator operations still need to be connected before they can form a complete product journey.

Do not start by training a bespoke vision model or promise an “exact” 3D representation or exact fit. Start with a rights-cleared catalogue, structured product attributes, curated OOTD, and a transparent content-based recommendation baseline. Collect only explicitly approved and privacy-reviewed interaction signals. Evaluate image-based virtual try-on as a clearly labelled visualization. True fit prediction requires garment construction/measurement data, user measurement quality, validation across body types and sizes, and a separate privacy and product review.

The approved provider direction in the current DRIP records is **Auth0 for authentication, Supabase PostgreSQL as the source of truth, FastAPI for business logic and authorization, Cloudflare for edge/media evaluation, and Firebase only for approved mobile-support services**. “Supabase” here means PostgreSQL; it does not imply changing back to Supabase Auth. The current Supabase documentation still describes automatic same-email identity linking, which conflicts with DRIP’s no-automatic-linking policy; the repository’s later Auth0 decision remains controlling. [Supabase identity-linking documentation](https://supabase.com/docs/guides/auth/auth-identity-linking)

## 1. Repository snapshot and evidence boundary

Inspected the Phase 2 plan, infrastructure realignment, identity and database reports, API routes/models, mobile routes and API adapter, and web admin/seller routes and components. Findings below are based on checked-in/current working-tree source as observed on 2026-11-20. A route or screen is not counted as complete merely because it exists.

| Snapshot item | Observed |
|---|---|
| Branch / HEAD | `main` / `341a6b031a6eda018d0b3df88f2baca5f88fbe94` |
| Git state at inspection | 38 tracked status entries, 192 untracked files, empty index. This is a heavily modified working tree; those files are pre-existing task/user work and must be preserved. |
| Mobile framework | Expo SDK `57.0.30`, React Native `0.86.3` from `apps/mobile/package.json`. |
| Database migration source | Migrations through `0006_curated_outfits` are present in the working tree. |
| Latest retained verification known to this session | Previous execution reported 456 non-live API tests passing and 8 live PG18 integration tests passing, reaching migration `0006_curated_outfits`. Those checks were not rerun for this document. The latest mobile type-check in the prior execution failed on a nullable-result error in the new outfit detail screen; that defect remains unverified/unfixed here. |
| Services during this document task | No services were started, stopped, or accessed. |

The prior mobile type-check failure is specifically at `apps/mobile/app/outfit/[id].tsx`: TypeScript flags a possible null access in the request-result identity check. The likely correction is to use optional narrowing for both fields or assign a narrowed local before reading `retry`, then rerun the mobile type-check. This document does not make that code change.

## 2. Feature status matrix

Statuses describe source-level capability, not a production deployment or a complete user journey.

| Area | Present in the repository | Status | What remains for a usable pilot |
|---|---|---|---|
| Public product catalogue | FastAPI list, detail, facets and discovery routes; catalogue models/migration; eligibility filters for publication, price freshness, sources and media. | **Implemented; live PG18 path recently verified** | Add real approved catalogue content and operational admin write access; verify final client behavior with configured endpoints and device/browser use. |
| Discovery search and filters | Mobile search/filter controls and one-card discovery adapter; server supports bounded cursor intents for similar/different-brand requests. | **Partially connected** | Configure public API, exercise real data, improve filter controls to use returned facets, verify gestures/accessibility on devices. No personalized model exists. |
| Product detail | Mobile product detail screen fetches public detail and shows variant, price/freshness, unknown inventory and external destination when available. | **Partially connected** | Verify with real approved records and retailer destinations; improve variant-level selection if backend contract returns it; device test. |
| Product-card gestures | Existing mobile component maps right to save, left to similar, up to different brand, tap to details, with accessible alternatives. | **UI behavior present; save is not connected** | Right swipe must remain pending/sign-in until authentication/wishlist exists; test the gesture recognizers on Android and iOS. Keep first-level category selection separate from product-card gestures. |
| OOTD public feed | Migration `0006`, eligibility-filtered public feed/detail API, and mobile feed/detail routes. It suppresses an outfit if required products cease to be eligible. | **Implemented at source level; PG18 integration recently passed** | Add rights-cleared editorial content, exercise on devices, decide whether an outfit itself can be saved, and define editorial cadence/brand rotation. No sample outfit content exists. |
| OOTD administration | FastAPI draft/update/preview/publish/archive operations are present behind fail-closed admin and writer-session dependencies. | **API surface present, operationally blocked** | No web OOTD management screen; Auth0 admin grants and a configured least-privilege writer session are not established. Do not weaken fail-closed dependencies. |
| Authentication | Auth0 JWKS/JWT verification primitives and provider-independent identity repository/contracts exist. Internal identity tables/migrations exist. | **Security foundation only** | No completed login UX integration, configured Auth0 tenant, approved bootstrap/activation path, persistent session/recovery flow, admin grants/MFA, or account lifecycle completion. The new-user lifecycle is disabled-first. |
| Wishlist | Guest-safe UI messaging exists. | **Not implemented as a connected feature** | No wishlist API, ownership persistence, idempotent mutations, cross-device refresh, or authenticated client flow. Must wait on authenticated internal-user resolution and database/API authorization. |
| Cart | Separate empty/not-connected mobile screen exists. | **Presentation only** | Cart persistence/contract is unresolved. Keep it clearly separate from wishlist; no checkout, order, payment, settlement, or purchase claim. |
| Admin catalogue portal | Next.js admin shell, catalogue list/form/activity/review routes and preparation UI exist. | **Presentation prototype** | No connected read/write workflow, login, server authorization session, listing/brand/merchant management experience backed by API, publication/withdrawal acknowledgements, or audit feed. APIs fail closed until authority and writer access are configured. |
| Seller portal | Separate seller routes and profile/submission shell exist. | **Presentation prototype** | Seller login, submission persistence, review lifecycle and permissions are absent and not required for the first admin-curated pilot. Keep seller publishing off. |
| Product media | Rights/media metadata and URL validation exist in catalogue contracts/models. | **Metadata only** | No R2 bucket, upload signer, object lifecycle, image processing, moderation/rights workflow, or production delivery domain configured. |
| Smart wardrobe | No wardrobe route, tables, upload flow, image labeling or outfit-to-wardrobe matching found in the inspected implementation. | **Not implemented** | Requires a separate privacy/data contract, private media storage, user identity/ownership, deletion, image-label review and recommendation logic. |
| Virtual try-on | No person-measurement capture, 2D VTON service, 3D avatar, garment mesh, or fit-validation flow found. | **Not implemented** | Requires modality choice, user-photo/measurement privacy, licensed garment assets, model/runtime evaluation, and a no-fit-guarantee UX. |
| Personalized feed | Discovery supports request intents and bounded cursors, not a user-specific ranking model or durable behavioral profile. | **Not implemented** | Requires an approved signal/consent policy, event taxonomy, minimum clean data, evaluation and user controls. |
| Push/crash diagnostics | No Firebase FCM/Crashlytics integration was found in the inspected app source. | **Not implemented; optional** | Add only if the pilot needs it and privacy/build distribution requirements are accepted. |

## 3. Suggested customer UI structure

### Navigation

Keep the established bottom navigation focused on **Discover** and **OOTD**. Put Wardrobe and Try-on in a clearly named **Studio** entry from the account/profile area or a secondary Discover module after those features are authorized. Four or five equal-weight bottom tabs would make the primary fashion loop harder to understand and would imply that currently gated features are ready.

### Discover landing

1. Center the DRIP wordmark in a restrained editorial header.
2. Place the search field immediately below, with server-backed category/brand/size/color filters.
3. Use a horizontal category selector or tap-to-open category tiles. Do not use right-swipe as both “open category” and “save product.”
4. Show one real, eligible product card at a time. Put brand, title, current INR price, price observation status and a quiet source/retailer cue around the image without crowding it.
5. Keep gesture meanings stable on the product card: right = wishlist save intent, left = similar, up = different brand, tap = detail. Provide visible accessible buttons for all four actions.
6. Where no real products/outfits are returned, show the existing honest empty states rather than editorial placeholders that look like actual inventory.

### OOTD

Use a separate, immersive editorial feed where one approved full-look image leads to a concise title, distinct featured brand and eligible component products. Tapping a look opens its detail view; each piece opens the normal product detail. Avoid implying stock or fit is guaranteed. If the owner wants Tinder-style outfit swipes too, specify what left/right/up mean and whether an outfit can be saved before implementing those gestures; the existing approved product-save semantics do not automatically define outfit-save behavior.

### Style direction proposal

This palette is a design proposal, not an approved brand system: warm ivory `#F5F0E9` canvas, near-black `#191714` text, deep plum `#56394B` editorial accent, muted olive `#798270` secondary accent, and restrained terracotta `#C57458` for highlights. Use a high-contrast serif display face only for editorial headlines and a highly legible sans serif for controls, price and body copy. Keep broad image margins, fine dividers, generous vertical rhythm, and minimal badges. Check all text/control combinations for WCAG contrast and large-text layouts before treating the palette as final.

The existing mobile theme and components should remain the source of truth while the Lovable design is inspected. The repository inspection did not establish whether a separate Lovable artifact exists or whether the current app matches it; compare the actual screens/design file before replacing visual work.

## 4. Backend and provider setup direction

### Authentication and database

- Keep Auth0 responsible for proving the external identity; FastAPI verifies access tokens and maps `(issuer, subject)` to a stable internal DRIP UUID. Do not map by email or expose database credentials to clients.
- Keep Supabase PostgreSQL as application source of truth. Mobile and browser call FastAPI only. Do not put the Supabase service-role secret in Expo or Next.js client bundles.
- Complete Auth0 tenant settings, Google OAuth callback/logout allowlists, audience, MFA, admin/founder designation, account recovery, disabled-first activation and session/revocation decisions before enabling protected features.
- Keep public catalogue reads separate from identity access. The owner-selected direction allows read-only catalogue SELECT for runtime while identity remains function-only. Runtime writes to catalogue or direct identity-table access must not be inferred from that selection.
- Keep Redis ephemeral for bounded rate-limits/cache/coordination; losing it must not lose catalogue, account, wishlist or outfit truth.

### Cloudflare media

Recommended future object split: a public delivery namespace for rights-approved catalogue/editorial media, and a private namespace for user wardrobe/person images. FastAPI authenticates the user/admin and authorizes a single object key; it issues a short-lived, operation-specific R2 presigned URL. The client uploads directly to that one key, then calls FastAPI to finalize metadata and validation. Never return R2 account credentials to the client. Verify content type, actual file signature, pixel dimensions and byte limits server-side, strip location metadata, generate normalized derivatives, and keep original user photos private with explicit deletion controls.

Cloudflare documents presigned URLs as temporary authorization for a specific S3 operation/object; the signed URL itself grants bearer access until expiry. Its R2 S3 presigned URLs use the R2 S3 API domain and do not work on a custom domain, so upload authorization and public CDN delivery should be treated as distinct paths. Do not choose public access, retention, cache invalidation, or spending limits until the owner approves the media/privacy policy. [R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/), [R2 pricing](https://developers.cloudflare.com/r2/pricing/)

### Firebase and Expo

Firebase is not an authentication or database replacement. If push is needed, the lowest-complexity first evaluation is `expo-notifications` with the Expo Push Service and the required FCM/APNs credentials, then decide if direct FCM is operationally necessary. Expo’s SDK 57 docs say remote notifications are unavailable in Android Expo Go from SDK 53 onward and require a development build; export alone cannot validate delivery. Crashlytics is a native SDK integration and should be assessed in an EAS/native development build, not assumed to work in Expo Go. Analytics should be deferred until a specific product question, event-minimization policy and consent/retention review exist. [Expo SDK 57 Notifications](https://docs.expo.dev/versions/v57.0.0/sdk/notifications/), [Firebase Crashlytics setup](https://firebase.google.com/docs/crashlytics/get-started)

## 5. Wardrobe and AI recommendation plan

### Phase W0: Human-confirmed wardrobe capture

After identity and private storage are ready, let a customer upload an item image, crop it, choose category/color/occasion and confirm machine-suggested attributes. Store private media, not a public product object. Make removal/deletion clear. Do not train on personal uploads by default. The upload and derived labels must remain owned by that user and must not enter the public catalogue.

### Phase W1: Useful non-generative outfit matching

Start with a transparent rules/content baseline: occasion, season/weather only if approved, category compatibility, user-selected color/fit preferences, and a simple wardrobe gap query against the currently eligible public catalogue. Explain the recommendation in user-facing terms. Never claim a product is needed or available when the source says stale/missing.

### Phase W2: Vision attributes and similarity

Use a pretrained image encoder or hosted inference first to produce candidate color/category/silhouette/material tags and visual embeddings. Keep confidence and allow correction. Use embeddings for “visually similar” retrieval only after evaluating false matches and image rights. Do not train a model from scratch on a few thousand outfits; that dataset can support a narrow experiment if labels, licensing, class balance and train/evaluation splits are sound, but it does not by itself establish robust personalization or fit.

### Phase W3: Personalized ranking

First define privacy-reviewed event records such as impression, card action, product detail, wishlist save/remove and external retailer redirect. A redirect is not a purchase event. Record only minimum needed identifiers, timestamp, surface and item, with retention and opt-out controls. Keep guests usable without a server-side identity profile. Start with content ranking plus editorial constraints and diversity; compare against a non-personalized baseline offline. Add collaborative ranking only after enough consenting, representative interactions exist. Avoid copying an “Instagram algorithm”: a fashion feed needs controllable categories/brands, freshness/eligibility filters, diversity, user reset controls and clear non-personalized fallback.

Research on image-based VTON (for example VITON-HD) describes synthesized imagery and rough garment fitting; it is not evidence of exact measurement-level fit. [VITON-HD paper, CVPR 2021](https://arxiv.org/abs/2103.16874)

## 6. Virtual try-on recommendation

Treat these as separate products:

| Level | What it can credibly show | Needs | Product wording |
|---|---|---|---|
| 2D image-based preview | A generated visualization of an item on a provided full-body image, subject to pose, occlusion, garment-image and generation artifacts. | Rights-cleared garment/person images, consent, secure private image processing, quality and safety evaluation, deletion policy. | “Visualization” / “style preview”; explicitly not a size or fit guarantee. |
| Measurement-assisted fit estimate | Approximate size/fit recommendation calibrated against actual brand sizing and observed fit outcomes. | Reliable user measurements, garment measurement/spec data per SKU/size, brand size charts, outcome labels, representative validation and uncertainty display. | A probabilistic guide, never “exact.” |
| 3D avatar and drape | A controllable 3D body and garment simulation. | A validated body scan/measurement method, 3D garment patterns/material parameters, avatar rigging, simulation/rendering stack, mobile performance and consented body data lifecycle. | A 3D simulation, with limitations and fit uncertainty. |

The current idea of entering measurements and rendering “exactly how that person will look” should be revised. Body measurements alone do not specify pose, body shape, ease, garment construction, fabric stretch/drape, lighting or motion. A generated 2D preview and physically credible 3D fit system are different technical scopes. Start with a sandboxed 2D feasibility prototype on licensed sample material and a small opt-in user study; keep uploads ephemeral until storage/deletion decisions are approved. Do not make shopping conversion or size accuracy claims before measured validation.

## 7. Suggested implementation sequence

Effort bands are rough engineering estimates for planning, excluding owner response time, real content acquisition, external account setup, and native store review.

| Stage | Scope | Dependencies / gate | Indicative effort |
|---|---|---|---:|
| 0 — Demo baseline | Fix the known mobile TypeScript issue; run mobile export and web lint/type/build; review Lovable design against actual mobile/web screens; test common Android sizes and one browser. | Existing local runtime; no backend credentials required for honest empty states. | 1–3 days |
| 1 — Real catalogue pilot | Approve content/source/rights, merchant domains, image/media policy and freshness rules; provision non-production Auth0/Supabase/Cloudflare only after separate owner resource approval; import or manually create a small real approved catalogue through admin API. | D2–D5, project/region, credentials/configuration and admin-authority decisions. No fake records. | 1–2 weeks after decisions/content |
| 2 — Identity and wishlist | Complete Auth0 login, internal identity resolution/activation, session/recovery, admin MFA/grants; implement PostgreSQL wishlist API and client acknowledgement/retry. | C1/C4/C6/C7 and founder/D3 authority; PG17/18 database/security acceptance and runtime grants. | 1–3 weeks |
| 3 — Admin operations | Connect list/detail/create/edit/preview/publish/withdraw and OOTD editorial screens; file upload workflow; audit view. | Working admin grants and writer role, approved rights/source/media workflow. | 1–3 weeks |
| 4 — Curated OOTD pilot | Add approved editorial records and rights-cleared images; operator runbook for expiry/withdrawal; feed/detail on devices. | OOTD editorial owner, rights, product eligibility and approved image delivery. | 3–7 days after content |
| 5 — Wardrobe beta | Private upload, labeling review/edit, item ownership/deletion, deterministic wardrobe-to-catalog recommendations. | User photo privacy, consent, private R2 design, deletion/backups, account and API controls. | 2–4 weeks |
| 6 — Personalization experiment | Minimum event schema, consent/retention, offline content ranker, diversity and holdout evaluation; only later consider learned ranking. | Sufficient real item and user signal data, privacy approval, objective metrics and rollback. | 2–6 weeks for experiment; production model timing data-dependent |
| 7 — Try-on research | Evaluate an external/hosted 2D VTON or research prototype with licensed content; compare body consistency, garment preservation, latency, safety and unit economics. Consider measurement/3D work only after evidence. | Separate product/privacy/security approval, sample rights, native capability and budget. | 2–6 weeks for feasibility; production 3D/fit is a larger program |

### Immediate recommended work package

1. Fix and verify the current mobile type-check failure.
2. Inspect the Lovable screens and write a screen-by-screen mapping to existing Expo routes and the existing theme; choose the visual direction after comparison, not by replacing the app wholesale.
3. Make the demo path robust with honest empty/error states and reliable public API configuration.
4. Decide the minimal real pilot catalogue: categories, source, image rights, approved retailer domains, minimum eligible item count and price freshness.
5. Only then wire the non-production providers and enable admin authority. Keep the sample/demo dataset in a clearly marked test environment and never present it as real inventory.

## 8. Unresolved owner decisions and blockers

1. **Pilot data:** source(s), approved brands/merchants, rights evidence, destinations and operator to review/withdraw records.
2. **Authentication operations:** Auth0 tenant ownership/region, Google OAuth settings, customer session/recovery, disabled-account activation, named founders/admins, MFA method and emergency access.
3. **Database/security acceptance:** PG17 live migration path and the final runtime/catalog writer permissions; do not treat PG18-only evidence as PG17 acceptance.
4. **Media:** public/private bucket layout, account ownership/region, upload size/type rules, delivery domain, content moderation, retention, backups and deletion.
5. **Wishlist:** whether implementation may proceed once identity mapping is ready; define save idempotency and guest transition around an acknowledged API response.
6. **OOTD:** editorial source/owner, cadence/brand rotation, whether complete looks can be saved, image rights record and content removal runbook.
7. **Wardrobe:** explicit consent for body/item images, private storage and processing location, user deletion, retention, model-training opt-in (default recommendation: off), and whether inference may use a third party.
8. **Virtual try-on:** choose 2D visualization feasibility vs true 3D; acceptable quality/latency/cost, devices, body-data processing and truthful fit-language.
9. **Personalization:** allowed events, guest/local behavior, opt-out/reset, retention, ranking objective, diversity constraints and evidence threshold before training.
10. **Firebase:** whether push/crash diagnostics are needed for the pilot; if yes, native build/testing, data collection, alert ownership and retention.
11. **Product direction:** seller self-service is not needed for the first admin-curated pilot unless explicitly prioritized; no public seller publication.

## 9. Recommended product add-ons (after core journey)

- **Style preference onboarding:** optional, skippable choices (colors, occasions, silhouettes, budget range) to improve cold-start without asking sensitive demographic questions.
- **“Why this look” explanation:** a short attribute-based rationale, e.g. color/occasion pairing, only when supported by catalog facts.
- **Wardrobe gap list:** compare user-confirmed wardrobe categories with eligible catalog categories; no pressure language or false scarcity.
- **Price watch:** only after owner approves notification, retailer price freshness, currency and user privacy contracts.
- **Outfit planning/calendar:** save a confirmed OOTD to a private plan after wishlist/account behavior is implemented.
- **Taste controls:** hide brand/category, reset preference history and choose more/less similar. These give users control rather than making opaque feed ranking the only experience.
- **Fit feedback:** only after there is an approved structured feedback contract; distinguish customer self-report from validated sizing ground truth.

## 10. Acceptance gates for the proposed roadmap

### Investor-demo gate (local/non-production)

- Mobile builds/type-checks; Discover, product detail, OOTD feed and OOTD detail navigate correctly on target Android devices and one browser where supported.
- Every product/outfit shown comes from an approved backend response; empty data remains an honest empty state.
- API and UI do not claim authentication, permanent save, upload, purchase or publication succeeded without server acknowledgement.
- Admin routes remain fail-closed. Do not use hardcoded admin credentials or fake dashboard metrics.
- No real user photo, wardrobe image or measurement is collected for the demo.

### Catalogue pilot gate

- PG17 and PG18 migration paths are accepted from disposable evidence; schema and constraints match metadata.
- Runtime role is read-only for catalogue and function-only for identity, and admin writing has a separately reviewed least-privilege path.
- Each published product has real source approval, rights-cleared image, allowed retailer destination, current price evidence and required variant details.
- Public DTO excludes private rights references, provider claims, admin identity and audit data.

### Authenticated wishlist gate

- Auth0 access token is verified by FastAPI; external `(issuer, subject)` maps to an internal ID; email is never the join key.
- Disabled accounts and missing/ambiguous identity mappings fail closed.
- Wishlist add/remove/clear is server-owned, idempotent and cross-account isolated; guest attempts do not persist and require explicit sign-in/confirmation.
- Revoked/suspended admin and session authorization is enforced on subsequent protected API calls.

### AI/wardrobe gate

- Upload consent, private object policy, EXIF stripping, size/type limits, user-scoped access, retention/deletion, vendor training policy and incident ownership are approved.
- Model evaluation has representative rights-cleared data, a locked held-out split, baseline comparison, subgroup quality checks, opt-out and rollback.
- Generated previews are labelled as visualizations and are never represented as exact fit or guaranteed size.

## 11. Sources and project records

### Current project records reviewed

- [Phase 2 specification and plan](phase-2-specification-and-plan.md)
- [P2-A readiness audit](p2-a-readiness-audit.md)
- [P2-0 contracts and acceptance](p2-0-contracts-and-acceptance.md)
- [Infrastructure architecture realignment](infrastructure-architecture-realignment.md)
- [Batch 2B-1 identity foundation](batch-2b-1-identity-foundation.md)
- [Batch 2B-1R identity hardening](batch-2b-1r-identity-hardening.md)
- [Batch 2B-2 database foundation specification](batch-2b-2-database-foundation-spec.md)
- [Batch 2B-2b database security specification](batch-2b-2b-database-security-spec.md)

### Official/primary technical sources checked 2026-11-20

- [Supabase Auth identity linking](https://supabase.com/docs/guides/auth/auth-identity-linking) — current managed Auth same-email automatic linking and documented manual-linking behavior; this supports keeping Supabase Auth out of the approved design, not changing DRIP’s provider decision.
- [Cloudflare R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) — temporary, object/operation-scoped signed URL behavior and S3 endpoint constraints.
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) — current billing dimensions; exact account terms and DRIP volume are unverified, so no monthly estimate is claimed.
- [Expo SDK 57 Notifications](https://docs.expo.dev/versions/v57.0.0/sdk/notifications/) — Expo Push Service/device-token paths and Android Expo Go limitation for remote notifications.
- [Expo SDK 57 ImagePicker](https://docs.expo.dev/versions/v57.0.0/sdk/imagepicker/) — native image selection/capture capability; it does not implement secure storage or backend upload authorization.
- [Firebase Crashlytics setup](https://firebase.google.com/docs/crashlytics/get-started) — native platform setup baseline; it does not prove Expo SDK 57 integration or a DRIP build works.
- [VITON-HD, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/html/Choi_VITON-HD_High-Resolution_Virtual_Try-On_via_Misalignment-Aware_Normalization_CVPR_2021_paper.html) — image-synthesis research, not evidence of exact 3D fit.
- [FIT: A Large-Scale Dataset for Fit-Aware Virtual Try-On](https://johannakarras.github.io/FIT/static/pdf/paper.pdf) — research dataset/model direction using person/garment measurements; it does not establish a licensed, representative or production-ready DRIP dataset.

**Overall assessment:** DRIP has a promising discovery/catalogue foundation and a useful OOTD public path. It is not yet a fully connected authenticated marketplace or AI styling product. The fastest credible next outcome is a rights-cleared, admin-curated product/OOTD pilot with reliable public browsing; wardrobe, personalization and try-on should be staged as separate validated products rather than presented as completed capabilities.
