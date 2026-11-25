import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Modal, Pressable, ScrollView, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ProductCard } from '../../src/components/product-card';
import { Button, Copy, Empty, ui } from '../../src/components/ui';
import { useCatalogue } from '../../src/catalog/context';
import { palette as c, space as s } from '../../src/theme';
import { BottomDock, Chip, TopBar, serif } from '../../src/lovable-ui';

export default function Discover() {
  const { category } = useLocalSearchParams<{ category?: string }>();
  const { catalogue, facets, filters, setFilters, requestNext, continueSearch, canContinue, retry } = useCatalogue();
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof category === 'string' && category !== filters.category) {
      setFilters({ ...filters, category });
    }
  }, [category, filters, setFilters]);

  const activeFilters = Number(!!filters.brand) + Number(!!filters.category) + Number(!!filters.size) + Number(!!filters.color);
  const change = (key: keyof typeof filters, value: string) => setFilters({ ...filters, [key]: value });
  const action = (kind: 'save' | 'similar' | 'different-brand' | 'detail') => {
    if (kind === 'detail' && catalogue.status === 'ready') {
      router.push({ pathname: '/product', params: { id: catalogue.product.id } });
    } else if (kind === 'save') {
      router.push({ pathname: '/sign-in', params: { intent: 'save' } });
    } else if (kind === 'similar' || kind === 'different-brand') {
      requestNext(kind);
    }
  };

  return <View style={{ flex: 1, backgroundColor: c.background }}>
    <TopBar title="Discover" />
    <View style={{ flex: 1, paddingHorizontal: 18, paddingBottom: 96, gap: 12 }}>
      <View style={{ flexDirection: 'row', gap: 9 }}>
        <View style={[ui.input, { flex: 1, minHeight: 48, height: 48, paddingVertical: 0, borderRadius: 28, flexDirection: 'row', alignItems: 'center', gap: 8 }]}>
          <Copy style={{ color: c.muted, fontSize: 18 }}>⌕</Copy>
          <TextInput accessibilityLabel="Search products and brands" value={filters.query}
            onChangeText={value => change('query', value)} placeholder="Search products or brands"
            placeholderTextColor={c.muted} style={{ flex: 1, height: 46, color: c.ink, fontSize: 13 }} />
          {!!filters.query && <Pressable accessibilityRole="button" accessibilityLabel="Clear search" onPress={() => change('query', '')}><Copy>×</Copy></Pressable>}
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={`Filters, ${activeFilters} active`} onPress={() => setOpen(true)}
          style={{ width: 48, height: 48, borderRadius: 25, justifyContent: 'center', alignItems: 'center', backgroundColor: c.ink }}>
          <Copy style={{ color: c.background, fontSize: 18 }}>☷</Copy>
          {activeFilters > 0 && <View style={{ position: 'absolute', right: -2, top: -3, minWidth: 19, height: 19, borderRadius: 10, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center' }}><Copy style={{ color: c.onAccent, fontSize: 10, fontWeight: '800' }}>{activeFilters}</Copy></View>}
        </Pressable>
      </View>

      {!!facets.categories.length && <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        <Chip active={!filters.category} onPress={() => change('category', '')}>All</Chip>
        {facets.categories.map(item => <Chip key={item.code} active={filters.category === item.code} onPress={() => change('category', filters.category === item.code ? '' : item.code)}>{item.label}</Chip>)}
      </ScrollView>}

      <View style={{ flex: 1, minHeight: 0, justifyContent: 'center' }}>
        {catalogue.status === 'ready' ? <ProductCard product={catalogue.product} onAction={action} /> :
          <Empty loading={catalogue.status === 'loading'} label="Discover / verified catalogue"
            title={catalogue.status === 'not-connected' ? 'Connect the catalogue to begin.' : catalogue.status === 'error' ? 'The catalogue could not load.' : 'No eligible pieces found.'}
            message={catalogue.status === 'not-connected' ? 'Set the local API URL and approved catalogue policies. No sample products are shown.' : catalogue.status === 'error' ? 'Nothing has been substituted. Check the API and retry.' : 'Try clearing a filter or continue through eligible results.'} />}
        {catalogue.status === 'error' && <Button title="Retry" onPress={retry} />}
        {catalogue.status === 'empty' && (canContinue ? <Button title="Continue this search" onPress={continueSearch} /> : <Button title="Try again" secondary onPress={retry} />)}
      </View>
    </View>
    <BottomDock active="discover" />

    <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
      <Pressable accessibilityRole="button" accessibilityLabel="Close filters" onPress={() => setOpen(false)}
        style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.55)' }}>
        <Pressable onPress={() => undefined} style={{ maxHeight: '78%', backgroundColor: c.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, paddingTop: 20, paddingHorizontal: 20, paddingBottom: Math.max(insets.bottom, s.lg), borderWidth: 1, borderColor: c.line }}>
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <View style={{ width: 42, height: 4, borderRadius: 4, backgroundColor: c.muted, alignSelf: 'center', marginBottom: 16 }} />
            <Copy style={[serif, { fontSize: 38, fontStyle: 'italic' }]}>Filters</Copy>
            {([['brand', 'BRAND', facets.brands.map(item => ({ value: item.name, label: item.name }))],
              ['category', 'CATEGORY', facets.categories.map(item => ({ value: item.code, label: item.label }))],
              ['size', 'SIZE', facets.sizes.map(value => ({ value, label: value }))],
              ['color', 'COLOUR', facets.colors.map(item => ({ value: item.code, label: item.label }))]] as const).map(([key, title, options]) =>
              <View key={key} style={{ marginTop: 22 }}>
                <Copy variant="eyebrow" style={{ color: c.muted }}>{title}</Copy>
                {options.length ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>{options.map(option => <Chip key={option.value} active={filters[key] === option.value} onPress={() => change(key, filters[key] === option.value ? '' : option.value)}>{option.label}</Chip>)}</View> : <Copy style={{ color: c.muted, marginTop: 8 }}>No approved options loaded.</Copy>}
              </View>)}
            <Pressable accessibilityRole="button" onPress={() => setOpen(false)} style={{ height: 50, marginTop: 24, marginBottom: 6, borderRadius: 28, backgroundColor: c.accent, alignItems: 'center', justifyContent: 'center' }}><Copy variant="eyebrow" style={{ color: c.onAccent }}>SHOW VERIFIED RESULTS</Copy></Pressable>
            <Copy style={{ color: c.muted, textAlign: 'center', marginBottom: 4 }}>Filters only use options returned by the connected catalogue.</Copy>
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  </View>;
}
