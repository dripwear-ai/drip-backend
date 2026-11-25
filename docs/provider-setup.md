# DRIP provider and local setup guide

Checked on 2026-11-20. This guide describes the current code boundaries and the manual dashboard setup required. No cloud resources or credentials have been configured by this repository change.

## Current integration status

| Service | Intended responsibility | Current application state |
| --- | --- | --- |
| Supabase PostgreSQL | Authoritative database | FastAPI uses SQLAlchemy/asyncpg through `DATABASE_URL`. The actual Supabase project, connection mode, TLS policy, role provisioning, and live migration acceptance are not configured or verified. Do not point the app at a Supabase project or run migrations until the database-security and role acceptance work has been reviewed. |
| Authentication | Auth0 is the approved provider | The hardened Auth0 JWT verifier exists, but the FastAPI routes, internal identity resolution, sessions, admin grants, and login UI are not wired. The catalog admin dependency intentionally fails closed. Do not substitute Supabase Auth without a new owner decision. |
| Cloudflare | DNS/CDN and R2 media evaluation | No zone, bucket, upload API, object client, or media authorization flow is configured. Existing catalog publication still depends on the approved source/media rules. |
| Firebase | Mobile push/crash reporting | No Firebase project, app configuration, Expo push registration, send service, or Crashlytics native SDK is configured. Analytics is not enabled. |
| Redis | Ephemeral abuse controls and coordination | Local Compose configuration exists. Redis is not a source of truth. Public catalog endpoints fail closed unless Redis and owner-approved request limits are available. |
| Hosting | API, web portals, database, Redis | No production host or deployment is configured. Local app ports do not imply a deployed service. |

The mobile Discover and OOTD screens now request real public API content. They show honest empty/error/not-connected states instead of bundled sample products and outfits. Wardrobe and 3D try-on are still unavailable; the screens do not create pretend results or collect body/photos.

## 1. Supabase PostgreSQL

### Create the project

1. Sign in to the Supabase Dashboard with the owner-controlled organization.
2. Create a separate project for each environment that will actually be used. Do not reuse a production project for development or tests.
3. Choose the exact region after checking latency and any data-residency requirements. Supabase currently lists **South Asia (Mumbai, `ap-south-1`)**; this is a reasonable latency candidate for India, not a legal-compliance conclusion. [Available regions](https://supabase.com/docs/guides/platform/regions)
4. Set a unique, strong database password and store it in the organization’s password manager. Never paste it into chat, source control, a mobile environment variable, or a screenshot.
5. In the project dashboard, inspect the actual PostgreSQL version and project status. Do not infer the version from upstream PostgreSQL release notes.

### Connection information

1. Open **Connect** in the project dashboard and select the connection mode based on where FastAPI will run.
2. For a persistent API host, prefer a direct connection when its IP family is reachable. If the host is IPv4-only, review the supported session pooler. Do not use transaction pooling for migrations or without testing asyncpg prepared-statement/session behavior. Supabase notes that transaction mode does not support prepared statements. [Connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
3. Keep separate credentials/roles for application runtime and migrations. The proposed role restrictions and role bootstrap are not accepted against a managed project yet.
4. The API expects `DATABASE_URL` in SQLAlchemy asyncpg form, for example a **redacted placeholder** shape: `postgresql+asyncpg://<role>:<password>@<dashboard-host>:<port>/<database>`. Copy the actual host, user and port from the dashboard; do not construct pooler hostnames yourself. URL-encode reserved password characters.
5. Current API configuration does not enforce Supabase TLS certificate/hostname validation as a deployment policy. Do not connect production data until that transport configuration and the approved role model are implemented and tested.

### Migration stop gate

The repository’s migration chain includes a PostgreSQL 18 assertion and a guarded checkpoint path. Live PostgreSQL acceptance, role provisioning, and the latest identity/catalog migration sequence must be confirmed before applying anything to a managed project. The historical migration files are already modified in this working tree; do not treat the current diff or offline tests as managed-database acceptance. The owner must approve the exact project version, migration runner identity, roles/grants/RLS setup, backups and recovery plan first.

Do **not** enable Supabase Auth for DRIP based only on the word “Supabase” in this setup request. Auth0 remains the later approved authentication-provider direction; its app flow is not integrated yet.

## 2. Auth0 authentication (required before private/admin features)

Auth0 configuration is separate from Supabase database setup.

1. Create the owner-controlled Auth0 tenant and record its region/ownership decision.
2. Create an API resource for DRIP and choose its API audience. Configure RS256 signing.
3. Record the tenant issuer including its trailing slash and the API audience in the server’s secret/configuration manager. The existing verifier requires explicit issuer, audience and RS256 settings; it does not read environment variables or attach itself to routes yet.
4. Choose the correct native/mobile and web application types only after the callback/deep-link scheme, allowed origins, logout URLs, admin realm, MFA and recovery decisions are reviewed. The current app has no approved callback URLs; do not invent them in the Auth0 dashboard.
5. Never put client secrets, signing keys, access tokens or refresh tokens in `EXPO_PUBLIC_*`, `NEXT_PUBLIC_*`, source code, or a browser bundle.
6. Before enabling admin access, complete founder account mapping, individual grants, remote MFA, recent-auth policy, mutual approval, emergency suspension and restoration operations. The current catalog authorization dependency fails closed.

## 3. Cloudflare DNS/CDN and R2

### DNS and web/API delivery

1. Add a domain only if the organization owns and controls it. The domain name and production API/web hosts have not been selected.
2. Add the domain as a zone in the owner-controlled Cloudflare account and verify its DNS records before changing registrar nameservers.
3. Configure DNS records only after the web/API hosting origins exist. Cloudflare DNS/CDN does not host the FastAPI or Next.js processes by itself.
4. Keep API and web origins separate. Auth, admin, wishlist, signed uploads and other private responses must not be cached as public catalogue responses.

### R2 image storage

R2 buckets are private by default. [Create buckets](https://developers.cloudflare.com/r2/buckets/create-buckets/)

1. After the owner approves image storage, create separate environment buckets in the relevant account. Do not put real product images into a development bucket unless their usage rights allow it.
2. Keep upload quarantine and rights/approval evidence private. Only approved public derivatives should be exposed through an approved custom media domain.
3. A custom R2 domain must be connected from **R2 → bucket → Settings → Custom Domains** and the domain must be in the same Cloudflare account. Public delivery through a custom domain is public internet access; it is not authorization. [Public bucket/custom domain setup](https://developers.cloudflare.com/r2/buckets/public-buckets/)
4. Create a least-privilege R2 API token for the approved bucket and store it only in the server’s secret manager. Do not create an account-wide key for the browser or mobile app.
5. Later, FastAPI should authorize the admin, generate a server-chosen object key and short-lived upload capability, then verify actual bytes/content, size, image decoding, metadata removal and rights approval before publication. No such upload endpoint exists now.
6. R2 presigned URLs are bearer capabilities, work against the R2 S3 API endpoint (not custom domains), and should have short expiry and narrow methods/object scope. [Presigned URL behavior](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
7. Decide retention, deletion, immutable/versioned object keys, cache lifetime and purge behavior before production image uploads. No specific bucket names, domain, size limits or retention policy are approved here.

## 4. Firebase with Expo

### Push notifications: recommended first integration

For this Expo app, use `expo-notifications` with the **Expo Push Service** initially. Expo Push Service forwards to FCM on Android and APNs on iOS; it is distinct from an app directly sending FCM HTTP requests. Expo supports configuring FCM V1 credentials through EAS. [Expo push setup](https://docs.expo.dev/push-notifications/push-notifications-setup/), [FCM V1 credentials](https://docs.expo.dev/push-notifications/fcm-credentials/)

1. Create an owner-controlled Firebase project. Add an Android app with the current package ID `com.drip.fashion`; add an Apple app with bundle ID `com.drip.fashion` when iOS push is in scope.
2. Enable/configure FCM V1 in the Firebase project. Create a service-account key only when ready to upload it to EAS credentials; keep the JSON outside Git and remove local copies from Downloads when safely stored.
3. Download `google-services.json` only as part of the separately authorized integration. It contains public-facing app configuration, but do not commit it before the repository’s configuration/file-handling review.
4. The mobile app has no `expo-notifications` package, notification code, or EAS project ID today. After an implementation slice is approved, install an SDK-compatible package using `pnpm --filter mobile exec expo install expo-notifications`, add the plugin/config, establish the EAS project, register device tokens with FastAPI, and test on a development build/device.
5. iOS remote push requires APNs credentials and an Apple Developer account; Expo’s setup guide describes this prerequisite. Do not expect an Expo web export or TypeScript check to verify push delivery.
6. Notification payloads should contain no sensitive profile, wishlist or admin details; opening a notification must refetch authoritative state from FastAPI.

### Crashlytics

Crashlytics is a native SDK integration. React Native Firebase native modules are not included in Expo Go; testing requires a custom/native development or release build and compatible config plugins. [React Native Firebase Expo note](https://rnfirebase.io/), [Crashlytics setup](https://firebase.google.com/docs/crashlytics/get-started)

The current mobile app has no Firebase native packages, Firebase app config, Crashlytics plugin, symbol upload, or crash consent/privacy review. Do not enable collection until the owner approves the data/retention policy and the native build path. Firebase Analytics is optional and not approved/enabled by this guide.

## 5. Local environment and ports

Copy `.env.example` to the repository-root `.env` only if `.env` does not already exist. Preserve an existing `.env`; update values manually. Keep all real values out of source control. The app currently reads:

| Variable | Purpose | State |
| --- | --- | --- |
| `DATABASE_URL` | API’s async PostgreSQL connection | Required for DB-backed routes; local placeholder only in `.env.example`. |
| `REDIS_URL` | Local/hosted ephemeral Redis | Required for public catalog abuse controls. |
| `CATALOG_PUBLIC_RATE_PER_MINUTE`, `CATALOG_PUBLIC_RATE_BURST` | Owner-selected public API limits | Required together; no default because limits remain an owner/security decision. Public routes fail closed until set. |
| `CATALOG_PRICE_FRESHNESS_HOURS`, `CATALOG_MAX_PRICE_MINOR`, `CATALOG_ALLOWED_CATEGORIES` | Eligibility/publication policy | Freshness and maximum price must be explicitly approved/configured before publication; do not guess. |
| `EXPO_PUBLIC_API_URL` | Public FastAPI origin for mobile | Set to `http://localhost:8000` for web/emulator on the same machine. For a physical phone, use a reachable LAN HTTPS/HTTP dev host address, not the phone’s `localhost`. Never place secrets here. |
| `NEXT_PUBLIC_API_URL` | Intended web API origin | Present as a template but not consumed by the current admin/seller shells. |
| `CORS_ORIGINS` | API browser origins | Include the exact local origin when overriding the default, e.g. admin `http://localhost:3001`, seller `http://localhost:3002`, mobile web `http://localhost:8083`. |

Current local ports:

| Process | Command | Port |
| --- | --- | ---: |
| FastAPI | `uv run --project apps/api --locked uvicorn drip.main:create_app --factory --reload --port 8000` | 8000 |
| Admin web | `pnpm --filter web dev:admin` | 3001 |
| Seller web | `pnpm --filter web dev:seller` | 3002 |
| Expo native Metro | `pnpm dev:mobile` | 8081 by default |
| Expo web preview | `pnpm --filter mobile web` | 8083 |

`pnpm dev:web` launches the admin portal only. The admin/seller pages remain presentation shells: they do not submit catalogue writes, and the API currently fails closed on catalog-admin authorization and catalog-writer sessions. No admin or seller operation should be represented as persisted until those dependencies are implemented and approved.

Local PostgreSQL/Redis Compose uses existing persistent development volumes. If the owner chooses to start it, use the documented command in [setup.md](setup.md), first confirm the ports and understand the data is persistent. Do not use it for migration acceptance or point it at Supabase. No services were started by this guide.

## 6. What is still needed before the app is investor-demo ready

- Owner: create/own the projects, choose project region/hosting, keep credentials in a password manager, and approve any costs/data residency.
- Database: complete non-superuser role provisioning, managed-project compatibility review, PG17/18 live acceptance, connection TLS configuration, and migration approval before attaching Supabase.
- Backend: wire Auth0 verifier to protected APIs, internal identity/session/account state and admin grants; implement catalog-writer role/session dependency; configure approved price freshness, maximum price, taxonomy and rate limits.
- Catalog/admin: connect admin portal forms/import to authenticated FastAPI operations and seed only real source-approved records through the controlled admin workflow. Import UI currently does not write.
- Wishlist: server persistence, authentication, ownership/idempotency and refresh behavior are not implemented.
- Media: R2 upload authorization, quarantine/validation/rights pipeline, delivery domain and deletion policy are not implemented.
- OOTD: public feed and details read through FastAPI, but publishing/admin controls require the currently disabled admin authorization and writer database role.
- Mobile: live Discover/OOTD API presentation is implemented; Expo Go/device checks and data-backed behavior need a reachable API/database and approved content. Wardrobe and 3D try-on are intentionally unavailable.
- Firebase: push and Crashlytics packages/native config/backend token lifecycle are not implemented.
- Deployment: choose and secure API/web hosting, Redis, domains, backups/alerts, log redaction and release workflows. A successful local export is not a deployment or native build.

## Sources

- [Supabase available regions](https://supabase.com/docs/guides/platform/regions)
- [Supabase PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Cloudflare R2 create buckets](https://developers.cloudflare.com/r2/buckets/create-buckets/)
- [Cloudflare R2 public buckets and custom domains](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Cloudflare R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [Expo push notifications setup](https://docs.expo.dev/push-notifications/push-notifications-setup/)
- [Expo FCM V1 credentials](https://docs.expo.dev/push-notifications/fcm-credentials/)
- [React Native Firebase](https://rnfirebase.io/)
- [Firebase Crashlytics setup](https://firebase.google.com/docs/crashlytics/get-started)
