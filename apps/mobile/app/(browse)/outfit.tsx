import { useCallback, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { ImageBackground, Pressable, View } from 'react-native';
import { BottomDock, SwipeDeck, T, TopBar, label, serif } from '../../src/lovable-ui';
import { CatalogueApiError, getOutfitPage, type OutfitView } from '../../src/catalog/api';
import { Button, Copy, Empty } from '../../src/components/ui';
import { palette as c } from '../../src/theme';

type FeedState = 'loading' | 'ready' | 'not-connected' | 'error' | 'empty';

function OutfitCard({ item }: { item: OutfitView }) {
  return <ImageBackground source={{ uri: item.image.url }} accessibilityLabel={item.image.alt}
    resizeMode="cover" style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: c.surface }}>
    <View pointerEvents="none" style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 120, backgroundColor: 'rgba(20,16,14,0.35)' }} />
    <View style={{ padding: 20, paddingTop: 48, backgroundColor: 'rgba(20,16,14,0.76)' }}>
      <T style={[label, { color: c.accent }]}>{item.brand.name.toUpperCase()} · EDITORIAL LOOK</T>
      <T style={[serif, { fontSize: 42, lineHeight: 46, marginTop: 6 }]}>{item.title}</T>
      {!!item.caption && <T numberOfLines={3} style={{ color: '#E8E0D7', lineHeight: 19, marginTop: 8 }}>{item.caption}</T>}
      <View style={{ flexDirection: 'row', gap: 7, alignItems: 'center', marginTop: 12 }}>
        {item.products.slice(0, 4).map(product => <ImageBackground key={product.id} source={{ uri: product.image.url }}
          accessibilityLabel={product.image.alt} resizeMode="cover" style={{ width: 42, height: 52, borderRadius: 6, overflow: 'hidden', backgroundColor: c.surface }} />)}
        <T style={{ color: '#E8E0D7', fontSize: 11 }}>{item.products.length} eligible pieces</T>
      </View>
    </View>
  </ImageBackground>;
}

export default function Ootd() {
  const [outfits, setOutfits] = useState<OutfitView[]>([]);
  const [status, setStatus] = useState<FeedState>('loading');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [deckKey, setDeckKey] = useState(0);
  const [deckStart, setDeckStart] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const busy = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    busy.current = false;
    void getOutfitPage(null, controller.signal).then(page => {
      if (!active) return;
      setOutfits(page.items);
      setNextCursor(page.nextCursor);
      setStatus(page.items.length ? 'ready' : 'empty');
      setDeckStart(0);
      setDeckKey(value => value + 1);
    }).catch(error => {
      if (!active || controller.signal.aborted) return;
      setStatus(error instanceof CatalogueApiError && error.kind === 'not-configured' ? 'not-connected' : 'error');
    });
    return () => { active = false; controller.abort(); };
  }, [retry]);

  const loadNextPage = useCallback(async () => {
    if (!nextCursor || busy.current) return;
    busy.current = true;
    setLoadingMore(true);
    try {
      const page = await getOutfitPage(nextCursor);
      const oldLength = outfits.length;
      setOutfits(current => [...current, ...page.items]);
      setNextCursor(page.nextCursor);
      setDeckStart(oldLength);
      setDeckKey(value => value + 1);
      setStatus('ready');
    } catch {
      setStatus('error');
    } finally {
      busy.current = false;
      setLoadingMore(false);
    }
  }, [nextCursor, outfits.length]);

  const openOutfit = useCallback((item: OutfitView) => {
    router.push({ pathname: '/outfit/[id]', params: { id: item.id } });
  }, []);
  const reload = () => {
    setStatus('loading');
    setOutfits([]);
    setNextCursor(null);
    setRetry(value => value + 1);
  };

  return <View style={{ flex: 1, backgroundColor: c.background }}>
    <TopBar title="Outfit of the day" />
    <View style={{ paddingHorizontal: 18, paddingBottom: 8, flexDirection: 'row', gap: 9 }}>
      <Pressable accessibilityRole="link" onPress={() => router.push('/outfit/wardrobe')} style={{ flex: 1, height: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9, borderRadius: 17, backgroundColor: c.glass, borderWidth: 1, borderColor: c.line }}>
        <T style={{ color: c.accent }}>♧</T><T style={[serif, { fontSize: 19, fontStyle: 'italic' }]}>AI Wardrobe</T>
      </Pressable>
      <Pressable accessibilityRole="link" onPress={() => router.push('/outfit/try-on')} style={{ flex: 1, height: 46, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9, borderRadius: 17, backgroundColor: '#985238' }}>
        <T>◉</T><T style={[serif, { fontSize: 19, fontStyle: 'italic' }]}>3D Try-On</T>
      </Pressable>
    </View>
    <View style={{ flex: 1, marginHorizontal: 11, marginBottom: 75 }}>
      {status === 'loading' ? <Empty loading label="OOTD / approved editorial" title="Finding today's looks." message="Checking published outfits and their current eligible pieces." />
        : status === 'not-connected' ? <Empty label="OOTD / not connected" title="Published looks will appear here." message="Connect the public API. No demo outfits or prices are included." />
          : status === 'error' && outfits.length === 0 ? <View><Empty label="OOTD / unavailable" title="The outfit feed could not load." message="No substitute content was shown. Check the API and retry." /><Button title="Retry" onPress={reload} /></View>
            : status === 'empty' ? <Empty label="OOTD / empty" title="No outfits are published yet." message="Approved editorial looks will appear after an admin publishes them." />
              : <SwipeDeck key={deckKey} initialIndex={deckStart} items={outfits} getKey={item => item.id} allowUp={false} showActions
                labels={{ left: 'Skip', right: 'Open details' }} rightActionLabel="Open details" rightSymbol="↗"
                renderCard={item => <OutfitCard item={item} />} onTap={openOutfit}
                onSwipe={(direction, item) => { if (direction === 'right') openOutfit(item); }}
                empty={<View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', borderRadius: 26, borderWidth: 1, borderColor: c.line, borderStyle: 'dashed', padding: 24 }}>
                  {status === 'error' ? <><Copy variant="heading">Couldn’t load the next looks.</Copy><Button title="Retry feed" onPress={reload} /></>
                    : nextCursor ? <><Copy variant="heading">More published looks await.</Copy><Button title={loadingMore ? 'Loading…' : 'Load next looks'} disabled={loadingMore} onPress={() => void loadNextPage()} /></>
                      : <Copy style={{ color: c.muted, textAlign: 'center' }}>You’ve reached the end of the published outfit feed.</Copy>}
                </View>} />}
    </View>
    <BottomDock active="ootd" />
  </View>;
}
