import type { Filters, PriceView, ProductView, VariantView } from './presentation';

type JsonObject = Record<string, unknown>;
export type CatalogFacets = {
  brands: { id: string; name: string }[];
  categories: { code: string; label: string }[];
  colors: { code: string; label: string }[];
  sizes: string[];
};
type DiscoveryResult = { items: JsonObject[]; nextCursor: string | null; emptyReason: string | null };
export type OutfitView = {
  id: string;
  title: string;
  caption: string;
  brand: { id: string; name: string };
  image: { url: string; alt: string };
  products: { id: string; title: string; image: { url: string; alt: string } }[];
};
export type OutfitPage = { items: OutfitView[]; nextCursor: string | null };

export class CatalogueApiError extends Error {
  constructor(readonly kind: 'not-configured' | 'request-failed' | 'invalid-response') {
    super(kind);
    this.name = 'CatalogueApiError';
  }
}

function object(value: unknown): JsonObject | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonObject : null;
}

function string(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function mapApprovedImage(value: unknown): { url: string; alt: string } | null {
  const image = object(value), urlValue = string(image?.url), alt = string(image?.alt);
  if (!urlValue || !alt) return null;
  try {
    const url = new URL(urlValue);
    if (url.protocol !== 'https:' || !url.hostname || url.username || url.password || url.search || url.hash ||
        (url.port && url.port !== '443')) return null;
    return { url: url.href, alt };
  } catch {
    return null;
  }
}

function mapOutfit(value: unknown): OutfitView | null {
  const outfit = object(value), id = string(outfit?.id), title = string(outfit?.title);
  const caption = string(outfit?.caption), image = mapApprovedImage(outfit?.image);
  const rawBrand = object(outfit?.brand), brandId = string(rawBrand?.id), brandName = string(rawBrand?.name);
  if (!id || !title || caption === null || !image || !brandId || !brandName || !Array.isArray(outfit?.products)) return null;
  const products = outfit.products.flatMap((raw): OutfitView['products'] => {
    const product = object(raw), productId = string(product?.id), productTitle = string(product?.title);
    const productImage = mapApprovedImage(product?.image);
    return productId && productTitle && productImage ? [{ id: productId, title: productTitle, image: productImage }] : [];
  });
  if (products.length < 2 || products.length !== outfit.products.length) return null;
  return { id, title, caption, brand: { id: brandId, name: brandName }, image, products };
}

function apiOrigin(): string | null {
  const configured = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (!configured) return null;
  try {
    const url = new URL(configured);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.search || url.hash || (url.pathname !== '/' && url.pathname !== '')) return null;
    return url.origin;
  } catch {
    return null;
  }
}

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const origin = apiOrigin();
  if (!origin) throw new CatalogueApiError('not-configured');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const response = await fetch(`${origin}/api/v1${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) throw new CatalogueApiError('request-failed');
    try {
      return await response.json() as unknown;
    } catch {
      throw new CatalogueApiError('invalid-response');
    }
  } catch (error) {
    if (error instanceof CatalogueApiError) throw error;
    throw new CatalogueApiError('request-failed');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}

async function postJson(path: string, payload: JsonObject, signal?: AbortSignal): Promise<unknown> {
  const origin = apiOrigin();
  if (!origin) throw new CatalogueApiError('not-configured');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });
  try {
    const response = await fetch(`${origin}/api/v1${path}`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) throw new CatalogueApiError('request-failed');
    try { return await response.json() as unknown; }
    catch { throw new CatalogueApiError('invalid-response'); }
  } catch (error) {
    if (error instanceof CatalogueApiError) throw error;
    throw new CatalogueApiError('request-failed');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}

function mapPrice(value: unknown): PriceView | null {
  const price = object(value), money = object(price?.money);
  const amountMinor = string(money?.amount_minor);
  const observedAt = string(price?.observed_at), validUntil = string(price?.valid_until);
  if (money?.currency !== 'INR' || !amountMinor || !observedAt || !validUntil || !/^\d+$/.test(amountMinor)) return null;
  return { amountMinor, observedAt, validUntil };
}

function approvedDestination(value: unknown): VariantView['destination'] {
  const raw = string(value);
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.port || url.search) return null;
    return { url: url.href, approvedHost: url.hostname };
  } catch {
    return null;
  }
}

function mapCard(value: JsonObject): ProductView | null {
  const brand = object(value.brand), image = object(value.image), price = mapPrice(value.price);
  const id = string(value.id), brandId = string(brand?.id), brandName = string(brand?.name);
  const imageUrl = string(image?.url), imageAlt = string(image?.alt);
  const representative = object(value.representative), variantId = string(representative?.variant_id);
  const categoryCode = string(value.category_code);
  if (!id || !brandId || !brandName || !imageUrl || !imageAlt || !variantId || !categoryCode || !price) return null;
  return {
    id, brandId, brand: brandName, title: string(value.title) ?? '',
    description: '', categoryCode, eligible: true,
    image: { url: imageUrl, alt: imageAlt },
    variants: [{ id: variantId, size: null, color: null, inventory: null, price,
      image: { url: imageUrl, alt: imageAlt }, destination: null }],
  };
}

function mapDetail(value: unknown): ProductView | null {
  const product = object(value), brand = object(product?.brand), rawListings = product?.listings;
  const id = string(product?.id), brandId = string(brand?.id), brandName = string(brand?.name);
  if (!id || !brandId || !brandName || !Array.isArray(rawListings)) return null;
  const variants: VariantView[] = [];
  for (const rawListing of rawListings) {
    const listing = object(rawListing);
    if (!Array.isArray(listing?.variants)) continue;
    const destination = approvedDestination(listing.destination_url);
    for (const rawVariant of listing.variants) {
      const item = object(rawVariant), variantId = string(item?.id), imageUrl = string(item?.image_url);
      const imageAlt = string(item?.image_alt), state = string(item?.price_state);
      if (!variantId || !imageUrl || !imageAlt || !['current', 'stale', 'missing'].includes(state ?? '')) continue;
      variants.push({
        id: variantId, size: string(item?.size_label), color: string(item?.color_label),
        inventory: null, price: mapPrice(item?.price), priceStatus: state as VariantView['priceStatus'],
        image: { url: imageUrl, alt: imageAlt }, destination,
      });
    }
  }
  if (!variants.length) return null;
  return {
    id, brandId, brand: brandName, title: string(product?.title) ?? '',
    description: string(product?.description) ?? '', categoryCode: string(product?.category_code) ?? '',
    eligible: true, image: variants[0].image, variants,
  };
}

export async function getCatalogFacets(signal?: AbortSignal): Promise<CatalogFacets> {
  const response = object(await getJson('/catalog/facets', signal));
  if (!Array.isArray(response?.brands) || !Array.isArray(response.categories) ||
      !Array.isArray(response.colors) || !Array.isArray(response.sizes)) {
    throw new CatalogueApiError('invalid-response');
  }
  const brands = response.brands.flatMap((raw): CatalogFacets['brands'] => {
    const brand = object(raw), id = string(brand?.id), name = string(brand?.name);
    return id && name ? [{ id, name }] : [];
  });
  const mapCodeLabel = (raw: unknown): { code: string; label: string }[] => {
    const facet = object(raw), code = string(facet?.code), label = string(facet?.label);
    return code && label ? [{ code, label }] : [];
  };
  const categories = response.categories.flatMap(mapCodeLabel);
  const colors = response.colors.flatMap(mapCodeLabel);
  const sizes = response.sizes.filter((value): value is string => typeof value === 'string');
  return { brands, categories, colors, sizes };
}

export async function discoverProduct(
  filters: Filters,
  brands: readonly CatalogFacets['brands'][number][],
  continuation: { cursor: string; intent: 'next' | 'similar' | 'different_brand'; anchorProductId?: string } | null,
  signal?: AbortSignal,
): Promise<DiscoveryResult> {
  const payload: JsonObject = continuation
    ? { cursor: continuation.cursor, intent: continuation.intent,
        ...(continuation.anchorProductId ? { anchor_product_id: continuation.anchorProductId } : {}) }
    : { limit: 1 };
  if (!continuation) {
    if (filters.query.trim()) payload.q = filters.query.trim();
    if (filters.category.trim()) payload.category = [filters.category.trim()];
    if (filters.size.trim()) payload.size = [filters.size.trim()];
    if (filters.color.trim()) payload.color = [filters.color.trim()];
    if (filters.brand.trim()) {
      const match = brands.find(item => item.name.toLocaleLowerCase() === filters.brand.trim().toLocaleLowerCase());
      if (!match) return { items: [], nextCursor: null, emptyReason: 'no_eligible_products' };
      payload.brand_id = [match.id];
    }
  }
  const response = object(await postJson('/discover', payload, signal));
  if (!Array.isArray(response?.items)) throw new CatalogueApiError('invalid-response');
  return {
    items: response.items.map(object).filter((item): item is JsonObject => item !== null),
    nextCursor: string(response.next_cursor),
    emptyReason: string(response.empty_reason),
  };
}

export async function getProductDetail(id: string, signal?: AbortSignal): Promise<ProductView | null> {
  const value = await getJson(`/catalog/products/${encodeURIComponent(id)}`, signal);
  const result = mapDetail(value);
  if (!result) throw new CatalogueApiError('invalid-response');
  return result;
}

export async function getOutfitPage(cursor?: string | null, signal?: AbortSignal): Promise<OutfitPage> {
  const path = cursor ? `/ootd?limit=5&cursor=${encodeURIComponent(cursor)}` : '/ootd?limit=5';
  const response = object(await getJson(path, signal));
  if (!Array.isArray(response?.items) ||
      !(response.next_cursor === null || typeof response.next_cursor === 'string')) {
    throw new CatalogueApiError('invalid-response');
  }
  const items = response.items.map(mapOutfit);
  if (items.some(item => item === null)) throw new CatalogueApiError('invalid-response');
  return { items: items as OutfitView[], nextCursor: response.next_cursor };
}

export async function getOutfitDetail(id: string, signal?: AbortSignal): Promise<OutfitView> {
  const response = mapOutfit(await getJson(`/ootd/${encodeURIComponent(id)}`, signal));
  if (!response) throw new CatalogueApiError('invalid-response');
  return response;
}

export function mapProductCard(value: JsonObject): ProductView | null {
  return mapCard(value);
}
