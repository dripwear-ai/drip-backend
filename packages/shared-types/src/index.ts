/**
 * @drip/shared-types
 * React-free domain contracts and shared type definitions for DRIP 2.0.
 */

// -----------------------------------------------------------------------------
// System Health & Infrastructure
// -----------------------------------------------------------------------------
export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ServiceHealth {
  status: HealthStatus;
  latency_ms?: number;
  message?: string;
}

export interface ReadyCheckResponse {
  status: HealthStatus;
  version: string;
  environment: string;
  services: {
    postgres: ServiceHealth;
    redis: ServiceHealth;
  };
  timestamp: string;
}

export interface LiveCheckResponse {
  status: 'alive';
  timestamp: string;
}

// -----------------------------------------------------------------------------
// Financial & Monetary Types (Integer Minor Units)
// -----------------------------------------------------------------------------
export type CurrencyCode = 'INR' | 'USD';

/**
 * General INR output representation, not catalogue-price eligibility.
 * Zero is representable; catalogue price records still require positive paise.
 * TypeScript checks the wire shape, not the digit syntax or numeric bounds.
 */
export interface MoneyINR {
  currency: 'INR';
  /** Base-10 integer paise string, from "0" through "9223372036854775807". */
  amount_minor: string;
}

/** @deprecated For catalogue money use MoneyINR; this legacy numeric shape is retained for compatibility. */
export interface MoneyAmount {
  /** Value in minor units (e.g. paise for INR, cents for USD) */
  amount_minor: number;
  currency: CurrencyCode;
}

// -----------------------------------------------------------------------------
// Catalog Core Enums & Contracts
// -----------------------------------------------------------------------------
export type PurchaseMode =
  | 'external_redirect'
  | 'integrated_retailer'
  | 'drip_marketplace';

export type InventoryState =
  | 'in_stock'
  | 'out_of_stock'
  | 'unknown'
  | 'stale';

export type ListingStatus =
  | 'draft'
  | 'pending_review'
  | 'published'
  | 'unpublished'
  | 'archived';

// -----------------------------------------------------------------------------
// API Standard Error Formats
// -----------------------------------------------------------------------------
export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: ValidationErrorDetail[];
  timestamp: string;
}
