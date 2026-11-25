import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { ImageBackground, Pressable, ScrollView, View } from 'react-native';
import { BottomDock, SectionHeading, T, TopBar, serif } from '../src/lovable-ui';
import { CatalogueApiError, getCatalogFacets, getOutfitPage, type CatalogFacets, type OutfitView } from '../src/catalog/api';
import { Button, Copy, Empty } from '../src/components/ui';
import { palette as c } from '../src/theme';

type LoadState = 'loading' | 'ready' | 'not-connected' | 'error' | 'empty';

export default function Home() {
  const [featured, setFeatured] = useState<OutfitView | null>(null);
  const [outfitState, setOutfitState] = useState<LoadState>('loading');
  const [categories, setCategories] = useState<CatalogFacets['categories']>([]);
  const [catalogueState, setCatalogueState] = useState<LoadState>('loading');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void Promise.allSettled([getOutfitPage(null, controller.signal), getCatalogFacets(controller.signal)]).then(([outfitResult, facetResult]) => {
      if (!active) return;
      if (outfitResult.status === 'fulfilled') {
        setFeatured(outfitResult.value.items[0] ?? null);
        setOutfitState(outfitResult.value.items.length ? 'ready' : 'empty');
      } else {
        setOutfitState(stateForError(outfitResult.reason));
      }
      if (facetResult.status === 'fulfilled') {
        setCategories(facetResult.value.categories);
        setCatalogueState(facetResult.value.categories.length ? 'ready' : 'empty');
      } else {
        setCatalogueState(stateForError(facetResult.reason));
      }
    });
    return () => { active = false; controller.abort(); };
  }, [retry]);
  const reload = () => {
    setOutfitState('loading');
    setCatalogueState('loading');
    setFeatured(null);
    setCategories([]);
    setRetry(value => value + 1);
  };

  return <View style={{ flex: 1, backgroundColor: '#1C1815' }}>
    <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 112, width: '100%', maxWidth: 440, alignSelf: 'center' }}>
      <TopBar />
      <View style={{ paddingHorizontal: 20, paddingTop: 6 }}>
        <Copy variant="eyebrow" style={{ color: c.muted }}>A MORE PERSONAL WAY TO DISCOVER</Copy>
        <T style={[serif, { fontSize: 52, lineHeight: 51, marginTop: 12 }]}>Find your next <T style={[serif, { color: c.accent, fontStyle: 'italic' }]}>favourite.</T></T>
        <Copy style={{ color: c.muted, fontSize: 14, lineHeight: 21, marginTop: 14, maxWidth: 340 }}>Browse verified pieces and considered looks, one at a time.</Copy>
      </View>

      <View style={{ marginTop: 26, paddingHorizontal: 20, gap: 12 }}>
        <SectionHeading title="Today’s" accent="edit" action="All looks" onAction={() => router.push('/outfit')} />
        {featured ? <Pressable accessibilityRole="link" accessibilityLabel={`Open ${featured.title} outfit`} onPress={() => router.push({ pathname: '/outfit/[id]', params: { id: featured.id } })}
          style={{ height: 350, borderRadius: 24, overflow: 'hidden', backgroundColor: c.surface }}>
          <ImageBackground source={{ uri: featured.image.url }} accessibilityLabel={featured.image.alt} resizeMode="cover" style={{ flex: 1, justifyContent: 'flex-end' }}>
            <View style={{ padding: 17, backgroundColor: 'rgba(22,18,15,0.75)' }}>
              <Copy variant="eyebrow" style={{ color: c.accent }}>{featured.brand.name.toUpperCase()} · APPROVED LOOK</Copy>
              <T style={[serif, { fontSize: 32, lineHeight: 37, marginTop: 5 }]}>{featured.title}</T>
              {!!featured.caption && <Copy numberOfLines={2} style={{ color: '#D8D0C6', marginTop: 6 }}>{featured.caption}</Copy>}
              <Copy style={{ color: c.muted, marginTop: 9 }}>{featured.products.length} eligible pieces · View look ↗</Copy>
            </View>
          </ImageBackground>
        </Pressable> : outfitState === 'loading' ? <Empty loading label="Editorial / live" title="Looking for published outfits." message="Only approved looks returned by the API appear here." />
          : outfitState === 'error' ? <View><Empty label="Editorial / unavailable" title="The outfit feed is unavailable." message="No demo look was substituted." /><Button title="Retry" secondary onPress={reload} /></View>
            : <Pressable accessibilityRole="link" onPress={() => router.push('/outfit')} style={{ padding: 18, borderWidth: 1, borderStyle: 'dashed', borderColor: c.line, borderRadius: 20 }}>
              <Copy variant="title">No looks published yet.</Copy><Copy style={{ color: c.muted }}>Approved editorial outfits will appear here when connected.</Copy>
            </Pressable>}
      </View>

      <View style={{ marginTop: 32, paddingHorizontal: 20, gap: 14 }}>
        <SectionHeading title="Shop by" accent="category" action="Discover" onAction={() => router.replace('/discover')} />
        {catalogueState === 'ready' ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 9 }}>
          {categories.map((category, index) => <Pressable key={category.code} accessibilityRole="link" onPress={() => router.push({ pathname: '/discover', params: { category: category.code } })}
            style={{ width: index === 0 ? '100%' : '48%', minHeight: index === 0 ? 126 : 104, justifyContent: 'flex-end', padding: 15, borderRadius: 20, borderWidth: 1, borderColor: c.line, backgroundColor: index % 2 ? c.surface : '#29241F' }}>
            <Copy variant="eyebrow" style={{ color: c.accent }}>VERIFIED CATALOGUE</Copy><T style={[serif, { fontSize: 26, marginTop: 4 }]}>{category.label}</T>
          </Pressable>)}
        </View> : <Empty loading={catalogueState === 'loading'} label="Catalogue / live" title={catalogueState === 'not-connected' ? 'Connect to discover categories.' : catalogueState === 'error' ? 'Catalogue is unavailable.' : 'No approved categories yet.'}
          message="Category options are read from the configured backend; no sample inventory is bundled." />}
      </View>

      <View style={{ marginTop: 28, paddingHorizontal: 20, flexDirection: 'row', gap: 10 }}>
        <FeatureCard title="AI Wardrobe" detail="Private wardrobe styling is not connected yet." symbol="♧" onPress={() => router.push('/outfit/wardrobe')} />
        <FeatureCard title="Virtual Fit" detail="3D try-on is not connected yet." symbol="◉" onPress={() => router.push('/outfit/try-on')} />
      </View>
    </ScrollView>
    <BottomDock active="discover" />
  </View>;
}

function stateForError(error: unknown): LoadState {
  return error instanceof CatalogueApiError && error.kind === 'not-configured' ? 'not-connected' : 'error';
}

function FeatureCard({ title, detail, symbol, onPress }: { title: string; detail: string; symbol: string; onPress: () => void }) {
  return <Pressable accessibilityRole="link" onPress={onPress} style={{ flex: 1, minHeight: 140, justifyContent: 'space-between', padding: 14, borderRadius: 20, borderWidth: 1, borderColor: c.line, backgroundColor: c.surface }}>
    <Copy style={{ color: c.accent, fontSize: 22 }}>{symbol}</Copy><View><Copy variant="heading">{title}</Copy><Copy style={{ color: c.muted, fontSize: 11, lineHeight: 16, marginTop: 4 }}>{detail}</Copy></View>
  </Pressable>;
}
