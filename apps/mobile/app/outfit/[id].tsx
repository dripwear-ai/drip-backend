import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Image, Pressable, View } from 'react-native';
import { CatalogueApiError, getOutfitDetail, type OutfitView } from '../../src/catalog/api';
import { Button, Copy, Empty, Page, ui } from '../../src/components/ui';
import { palette as c, space as s } from '../../src/theme';

type DetailState = 'loading' | 'ready' | 'unavailable' | 'error' | 'missing';

export default function OutfitDetail() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [result, setResult] = useState<{ id: string; retry: number; state: DetailState; outfit: OutfitView | null } | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    if (typeof id !== 'string' || !id) return () => controller.abort();
    void getOutfitDetail(id, controller.signal).then(value => {
      if (active) {
        setResult({ id, retry, outfit: value, state: 'ready' });
      }
    }).catch(error => {
      if (!active || controller.signal.aborted) return;
      setResult({ id, retry, outfit: null, state: error instanceof CatalogueApiError && error.kind === 'not-configured'
        ? 'unavailable' : 'error' });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [id, retry]);

  const current = result && result.id === id && result.retry === retry ? result : null;
  const state: DetailState = typeof id !== 'string' || !id ? 'missing' : current?.state ?? 'loading';
  const outfit = current?.outfit ?? null;

  if (state !== 'ready' || !outfit) {
    const title = state === 'loading' ? 'Loading the complete look'
      : state === 'unavailable' ? 'The outfit service is not connected.'
        : state === 'missing' ? 'No outfit was selected.'
          : state === 'error' ? 'Couldn’t load this outfit.' : 'No outfit was selected.';
    const message = state === 'loading' ? 'Checking that every piece is still eligible.'
      : state === 'unavailable' ? 'No sample editorial content is shown.'
        : state === 'missing' ? 'Return to the public outfit feed.'
          : state === 'error' ? 'No alternate content was substituted.' : 'Return to the public outfit feed.';
    return <Page>
      <Empty loading={state === 'loading'} label="Outfit details" title={title} message={message} />
      {state === 'error' && <Button title="Retry" onPress={() => setRetry(value => value + 1)} />}
      <Button title="Back to outfits" secondary onPress={() => router.navigate('/outfit')} />
    </Page>;
  }

  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>THE DAILY OUTFIT</Copy>
    <Copy variant="title">{outfit.title}</Copy>
    <Copy variant="eyebrow" style={{ color: c.muted }}>{outfit.brand.name}</Copy>
    <Image source={{ uri: outfit.image.url }} accessibilityLabel={outfit.image.alt}
      resizeMode="cover" style={{ width: '100%', aspectRatio: 0.76, backgroundColor: c.surface, borderRadius: 12 }} />
    {!!outfit.caption && <Copy style={{ color: c.muted }}>{outfit.caption}</Copy>}
    <Copy variant="heading">Eligible pieces</Copy>
    <View style={{ gap: s.sm }}>
      {outfit.products.map(product => <Pressable key={product.id} accessibilityRole="link"
        accessibilityLabel={`View ${product.title}`} onPress={() => router.push({ pathname: '/product', params: { id: product.id } })}
        style={({ pressed }) => [ui.row, { alignItems: 'center', gap: s.md, padding: s.sm, backgroundColor: c.surface, borderRadius: 8, opacity: pressed ? 0.7 : 1 }]}>
        <Image source={{ uri: product.image.url }} accessibilityLabel={product.image.alt}
          resizeMode="cover" style={{ width: 72, height: 88, backgroundColor: c.raised, borderRadius: 6 }} />
        <Copy style={{ flex: 1 }}>{product.title}</Copy>
        <Copy accessibilityElementsHidden>›</Copy>
      </Pressable>)}
    </View>
  </Page>;
}
