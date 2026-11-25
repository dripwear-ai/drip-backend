import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Image, Linking, View } from 'react-native';
import { CatalogueApiError, getProductDetail } from '../src/catalog/api';
import { approvedDestination, formatPaise, priceState } from '../src/catalog/presentation';
import { Button, Copy, Empty, Page, ui } from '../src/components/ui';
import { palette as c, space as s } from '../src/theme';
export default function ProductDetail() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [selected, setSelected] = useState<string | null>(null), [error, setError] = useState('');
  const [detail, setDetail] = useState<{ id: string; request: number; product: Awaited<ReturnType<typeof getProductDetail>>; status: 'ready' | 'not-connected' | 'error' } | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    if (typeof id !== 'string') return () => controller.abort();
    void getProductDetail(id, controller.signal).then(value => {
      if (active) setDetail({ id, request: retryCount, product: value, status: 'ready' });
    }).catch(cause => {
      if (active && !controller.signal.aborted) setDetail({ id, request: retryCount, product: null,
        status: cause instanceof CatalogueApiError && cause.kind === 'not-configured' ? 'not-connected' : 'error' });
    });
    return () => { active = false; controller.abort(); };
  }, [id, retryCount]);
  const current = detail && detail.id === id && detail.request === retryCount ? detail : null;
  const loading = typeof id === 'string' && !current;
  const product = current?.product ?? null;
  const variant = product?.variants.find(item => item.id === selected) ?? product?.variants[0];
  if (loading) return <Page><Empty loading label="Product details" title="Loading product details" message="Checking the current approved catalogue." /></Page>;
  if (!product) return <Page><Empty label="Product details" title={current?.status === 'not-connected' ? 'Catalogue connection is unavailable.' : current?.status === 'error' ? 'Couldn’t load product details.' : 'This piece isn’t available.'} message={current?.status === 'not-connected' ? 'Configure the public API connection to load this product.' : current?.status === 'error' ? 'No fallback product was substituted. Retry when the catalogue is reachable.' : 'No eligible product details were returned.'} />{current?.status === 'error' && <Button title="Retry" onPress={() => setRetryCount(value => value + 1)} />}<Button title="Back to Discover" onPress={() => router.navigate('/discover')} /></Page>;
  const state = priceState(variant?.price ?? null, undefined, variant?.priceStatus);
  const destination = approvedDestination(variant?.destination ?? null);
  const image = variant?.image ?? product.image;
  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>{product.brand}</Copy><Copy variant="title">{product.title}</Copy>
    {image ? <Image source={{ uri: image.url }} accessibilityLabel={image.alt} style={{ width: '100%', aspectRatio: 0.8, borderRadius: 12 }} /> : <Copy>Approved image unavailable.</Copy>}
    <Copy>{product.description}</Copy><Copy variant="heading">Choose your variation</Copy>
    <View style={ui.row}>{product.variants.map(item => <Button key={item.id} secondary={variant?.id !== item.id} title={(item.size ?? 'Size unspecified') + ' / ' + (item.color ?? 'Color unspecified')} onPress={() => setSelected(item.id)} />)}</View>
    <View style={{ gap: s.sm }}>
      <Copy variant="heading">{state === 'current' && variant?.price ? formatPaise(variant.price.amountMinor) : state === 'stale' ? 'Price needs an update' : 'Price unavailable'}</Copy>
      {state === 'current' && variant?.price && <Copy variant="small">Source observed: {variant.price.observedAt} · Valid until: {variant.price.validUntil}</Copy>}
      <Copy variant="small">Availability: {variant?.inventory === 'in_stock' ? 'Reported available by source' : variant?.inventory === 'out_of_stock' ? 'Reported unavailable by source' : 'Unknown — check with retailer'}</Copy>
    </View>
    <Button title="Save to wishlist" secondary onPress={() => router.push({ pathname: '/sign-in', params: { intent: 'save' } })} />
    <Button title={destination ? 'Buy Now · visit retailer ↗' : 'Retailer link unavailable'} disabled={!destination} onPress={() => {
      if (destination) void Linking.openURL(destination).catch(() => setError('Could not open the retailer. Please try again.'));
    }} />
    <Copy variant="small" style={{ color: c.muted }}>You’ll leave DRIP. Price, availability and purchase terms are confirmed by the retailer.</Copy>
    {!!error && <Copy accessibilityLiveRegion="polite">{error}</Copy>}
  </Page>;
}
