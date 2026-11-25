# ADR 0001: DRIP 2.0 Modular Monolith Architecture & Foundation

## Context
DRIP 2.0 is an isolated, new fashion discovery and shopping platform. The system requires high consistency across catalog records, reliable gesture-driven mobile discovery, multi-tenant portal management, and robust verification before introducing live checkout.

## Decisions

1. **Modular Monolith:**
   We reject premature microservices in favor of a single modular backend (`apps/api`) with strictly decoupled service boundaries (`identity`, `merchant`, `catalog`, `ingestion`, `discovery`, `outfit`, `cart`, `commerce`).

2. **Authoritative Single Source of Truth:**
   PostgreSQL 18 is the sole authoritative data store. Redis 8.2 is strictly ephemeral (caching, rate-limiting, distributed locks, session revocation) and is never treated as the source of truth.

3. **Strict Monetary Arithmetic:**
   All monetary amounts are stored as integer minor units (`BIGINT` paise for INR) or `Numeric`. Floating-point arithmetic (`float`) is forbidden in all financial and pricing operations.

4. **React-Free Shared Contracts:**
   `packages/shared-types` contains pure TypeScript interfaces and types shared between web (`apps/web` on Next.js 16) and mobile (`apps/mobile` on Expo SDK 57 / React Native 0.86). It does not import React, ensuring clean workspace isolation.

5. **Security & Production Fail-Closed Policy:**
   - Production environments immediately fail closed if default development secrets are detected.
   - Zero hardcoded secrets, OTPs, or credentials in version control.
   - All error responses adhere to a consistent contract without leaking stack traces or sensitive internal details.

## Status
Gate A architecture approved. Gate B corrections have passed local software verification
and all five disposable PostgreSQL/Redis integration tests, including UUIDv7 and migration round-trip.
The owner explicitly approved Gate B following the corrective verification dated 2026-10-12.
The owner approved the [Phase 2 specification and plan](../phase-2-specification-and-plan.md)
as the planning baseline on 2026-10-13. Its unresolved milestone prerequisites remain open;
The owner separately authorized P2-A implementation on 2026-10-14, subject to resolving
blocking milestone decisions. P2-B requires P2-A acceptance and separate authorization.
See [the corrective verification report](../gate-b-verification.md) for commands and limitations.
