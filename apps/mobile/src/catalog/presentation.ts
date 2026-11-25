// Local composition shapes only. No approved API contract or connected data source.
export type PriceView = { amountMinor: string; observedAt: string; validUntil: string };
export type VariantView = {
  id: string; size: string | null; color: string | null; inventory: null | 'in_stock' | 'out_of_stock' | 'stale';
  price: PriceView | null; priceStatus?: 'current' | 'stale' | 'missing'; image: { url: string; alt: string } | null;
  destination: { url: string; approvedHost: string } | null;
};
export type ProductView = {
  id: string; brand: string; brandId?: string; categoryCode?: string; title: string; description: string;
  eligible: boolean; image: { url: string; alt: string } | null; variants: readonly VariantView[];
};
export type CatalogueState =
  | { status: 'not-connected' | 'loading' | 'error' | 'empty'; product: null }
  | { status: 'ready'; product: ProductView };
export type Filters = { query: string; brand: string; category: string; size: string; color: string };
export const disconnectedCatalogue: CatalogueState = { status: 'not-connected', product: null };

export function formatPaise(value: string): string | null {
  if (value.length > 19 || !/^[1-9]\d*$/.test(value) || BigInt(value) > BigInt('9223372036854775807')) return null;
  const digits = value.padStart(3, '0');
  const rupees = digits.slice(0, -2);
  const head = rupees.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',');
  return '₹' + (head ? head + ',' : '') + rupees.slice(-3) + '.' + digits.slice(-2);
}
export function priceState(price: PriceView | null, now = Date.now(), status?: VariantView['priceStatus']): 'current' | 'stale' | 'missing' {
  if (!price) return status === 'stale' ? 'stale' : 'missing';
  if (status && status !== 'current') return status;
  if (!formatPaise(price.amountMinor)) return 'missing';
  const from = Date.parse(price.observedAt), until = Date.parse(price.validUntil);
  if (!Number.isFinite(from) || !Number.isFinite(until) || until <= from || now < from) return 'missing';
  return now >= until ? 'stale' : 'current';
}
export function approvedDestination(destination: VariantView['destination']): string | null {
  if (!destination) return null;
  try {
    const url = new URL(destination.url);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash || url.port ||
        url.hostname !== destination.approvedHost || !url.hostname.includes('.') ||
        /^[\d.]+$/.test(url.hostname) || url.hostname.endsWith('.local')) return null;
    return url.href;
  } catch { return null; }
}
// The future adapter must independently verify source/rights/host approval and public eligibility.
export function canPresentCard(product: ProductView | null, now = Date.now()): boolean {
  return !!product?.eligible && !!product.image &&
    product.variants.some(variant => priceState(variant.price, now, variant.priceStatus) === 'current');
}
export type CardAction = 'save' | 'similar' | 'different-brand' | 'detail';
export function swipeAction(x: number, y: number, vx: number, vy: number, enabled: boolean): CardAction | null {
  'worklet';
  if (!enabled) return null;
  const px = x + vx * 0.12, py = y + vy * 0.12;
  if (Math.abs(py) > Math.abs(px) && py < -90) return 'different-brand';
  if (Math.abs(px) >= Math.abs(py) && px > 90) return 'save';
  if (Math.abs(px) >= Math.abs(py) && px < -90) return 'similar';
  return null;
}
export function guestAction(action: CardAction, hasProduct: boolean): 'sign-in-required' | 'catalogue-required' | 'detail' {
  if (!hasProduct) return 'catalogue-required';
  return action === 'save' ? 'sign-in-required' : action === 'detail' ? 'detail' : 'catalogue-required';
}
