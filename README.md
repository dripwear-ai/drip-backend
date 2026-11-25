# DRIP 

DRIP is an early-stage fashion discovery product with an Expo mobile client, Next.js web portals, shared TypeScript contracts, and a FastAPI backend. This repository contains active implementation work; a feature appearing in source code does not mean its infrastructure or end-to-end behavior has been accepted.

## Repository layout

- apps/api/ — FastAPI application, SQLAlchemy models, Alembic migrations, identity and catalog services, and tests.
- apps/mobile/ — Expo / React Native customer application.
- apps/web/ — Next.js admin and seller portal shells.
- packages/shared-types/ — shared TypeScript contracts.
- infra/ and scripts/ — local and disposable test infrastructure and verification helpers.
- docs/ — architecture decisions, setup instructions, product specifications, and verification records.

## Intended architecture

- Auth0 is the approved external identity provider; DRIP internal UUIDv7 user IDs are intended to remain the application identity.
- PostgreSQL is the source of truth. Supabase PostgreSQL is the intended managed host.
- FastAPI owns business logic and server-side authorization.
- Redis is for ephemeral limits and coordination, never durable application state.
- Cloudflare R2 is the intended product-media direction; Firebase is reserved for mobile support capabilities where configured.

These are architecture directions, not evidence that external projects or production services have been configured.

## What is present

- FastAPI health, readiness, public catalog discovery/list/detail/facets, and public curated OOTD API code.
- Catalog draft, preview, publish, and withdrawal API code, plus admin OOTD authoring routes.
- SQLAlchemy identity, catalog, and outfit metadata, with Alembic revision files through 0006_curated_outfits.
- Auth0 JWT/JWKS verification primitives and an internal identity persistence boundary.
- Expo customer UI and Next.js admin/seller presentation shells.
- Unit, contract, and database-focused tests and PostgreSQL 17/18 test harness code.

## What is not yet operational or accepted

- **Authentication and identity:** Auth0 verification is not wired into the API request routes. Login/session lifecycle, account activation, account recovery, and the approved admin-grant model are not complete.
- **Admin catalog/OOTD writes:** routes exist, but admin authorization and catalog-writer session dependencies currently fail closed until configured. These operations therefore cannot be used as working admin APIs yet.
- **Wishlist:** authenticated wishlist API and persistence workflows are not present.
- **Catalog ingestion and seller operations:** there is no complete seller/brand import API and portal workflow connected to the catalog.
- **Media:** Cloudflare R2 upload, access control, rights-evidence workflow, and deletion lifecycle are not connected.
- **Personalization and AI:** current catalog discovery is not a trained recommendation system. AI wardrobe tagging, outfit generation, and virtual try-on are not implemented as backend services.
- **Database acceptance:** migration files and disposable PG17/PG18 harnesses are present, but this README does not certify live migration/security acceptance through revisions 0004–0006.
- **Deployment:** Auth0, managed PostgreSQL, R2, Firebase, production secrets, hosting, monitoring, and release configuration still require owner setup and verification.

Checkout, orders, payments, and settlement are intentionally outside the current implementation scope.

## Local development

Use the versions pinned by the repository: Node 24.19.0, pnpm 9.15.9, Python 3.14.7, and uv 0.12.7 (or a compatible newer uv release).

    pnpm install --frozen-lockfile
    uv sync --project apps/api --locked --python 3.14.7 --extra dev
    pnpm build:shared

The repository root setup guide at docs/setup.md documents the environment convention, local PostgreSQL/Redis Compose stack, migration safeguards, API commands, Expo preview, portal ports, and verification commands. Read it before starting services or applying migrations. Never point test or migration commands at production or a non-disposable database.

Common development commands:

    pnpm dev:web
    pnpm dev:mobile
    uv run --project apps/api --locked uvicorn drip.main:create_app --factory --reload --port 8000

pnpm dev:web starts the admin portal. Separate admin/seller scripts are listed in apps/web/package.json; pnpm dev:mobile starts Expo. See the setup guide for port and device-network details.

## Verification

Available repository checks include:

    pnpm test
    pnpm lint:api
    pnpm type-check:api
    pnpm type-check
    pnpm build
    pnpm test:integration

Integration tests require the exact disposable targets and preflight documented in docs/setup.md. A successful type check or JavaScript export does not establish live database migration acceptance or native iOS/Android device behavior.

## Current status

Reviewed 25 November 2026. This README is a source inventory and implementation-gap summary, not a release-readiness claim. Check the linked specifications and verification reports for the evidence and current acceptance gates.
