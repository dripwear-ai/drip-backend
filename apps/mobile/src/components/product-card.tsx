import { memo, useMemo } from 'react';
import { Image, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { ReduceMotion, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';
import { canPresentCard, formatPaise, priceState, swipeAction, type CardAction, type ProductView } from '../catalog/presentation';
import { palette as c, space as s, motion } from '../theme';
import { Button, Copy, Empty } from './ui';

export const ProductCard = memo(function ProductCard({ product, onAction }: { product: ProductView | null; onAction: (action: CardAction) => void }) {
  const x = useSharedValue(0), y = useSharedValue(0);
  const reduced = useReducedMotion();
  const enabled = canPresentCard(product);
  const gestures = useMemo(() => {
    const pan = Gesture.Pan().enabled(enabled).minDistance(12)
      .onUpdate(event => { x.set(event.translationX); y.set(event.translationY); })
      .onEnd(event => {
        const action = swipeAction(event.translationX, event.translationY, event.velocityX, event.velocityY, enabled);
        if (action) scheduleOnRN(onAction, action);
      })
      .onFinalize(() => {
        x.set(withSpring(0, { ...motion, reduceMotion: ReduceMotion.System }));
        y.set(withSpring(0, { ...motion, reduceMotion: ReduceMotion.System }));
      });
    const tap = Gesture.Tap().enabled(enabled).maxDistance(10).onEnd((_event, success) => { if (success) scheduleOnRN(onAction, 'detail'); });
    return Gesture.Exclusive(pan, tap);
  }, [enabled, onAction, x, y]);
  const animated = useAnimatedStyle(() => ({
    transform: [{ translateX: reduced ? 0 : x.get() }, { translateY: reduced ? 0 : y.get() },
      { rotate: reduced ? '0deg' : x.get() / 28 + 'deg' }],
  }));
  if (!product || !enabled) return <Empty label="Discover / not connected" title="Your next find starts here."
    message="The catalogue isn’t connected yet. When approved products arrive, explore one thoughtful find at a time." />;
  const variant = product.variants.find(item => priceState(item.price, Date.now(), item.priceStatus) === 'current');
  return <View style={{ gap: s.md }}>
    <GestureDetector gesture={gestures}><Animated.View style={[{ backgroundColor: c.paper, borderRadius: 4, overflow: 'hidden', shadowColor: '#17251C', shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 4 }, animated]}
      accessible accessibilityRole="button" accessibilityLabel={product.brand + ', ' + product.title}
      accessibilityHint="Open product details. Equivalent discovery actions are below."
      accessibilityActions={[{ name: 'activate', label: 'Product details' }, { name: 'save', label: 'Save to wishlist' }, { name: 'similar', label: 'Similar product' }, { name: 'different-brand', label: 'Different brand' }]}
      onAccessibilityAction={event => onAction(event.nativeEvent.actionName === 'activate' ? 'detail' : event.nativeEvent.actionName as CardAction)}>
      {product.image ? <Image source={{ uri: product.image.url }} accessibilityLabel={product.image.alt} style={{ width: '100%', aspectRatio: 0.78, backgroundColor: c.raised }} resizeMode="cover" /> :
        <View style={{ width: '100%', aspectRatio: 0.78, justifyContent: 'center', alignItems: 'center', backgroundColor: c.raised }}><Copy variant="eyebrow" style={{ color: c.muted }}>APPROVED IMAGERY UNAVAILABLE</Copy></View>}
      <View style={{ padding: s.lg, gap: s.sm }}>
        <Copy variant="eyebrow" style={{ color: c.onPaper }}>{product.brand}</Copy>
        <Copy variant="title" style={{ color: c.onPaper }}>{product.title}</Copy>
        <Copy style={{ color: c.onPaper }}>{variant?.price ? formatPaise(variant.price.amountMinor) : 'Price unavailable'}</Copy>
      </View>
    </Animated.View></GestureDetector>
    <Copy variant="small" style={{ color: c.muted, textAlign: 'center' }}>← Similar · ↑ Another brand · → Save · Tap for details</Copy>
    <View style={{ gap: s.sm }}>
      <View style={{ flexDirection: 'row', gap: s.sm }}><View style={{ flex: 1 }}><Button title="Find similar" secondary onPress={() => onAction('similar')} /></View><View style={{ flex: 1 }}><Button title="Another brand" secondary onPress={() => onAction('different-brand')} /></View></View>
      <View style={{ flexDirection: 'row', gap: s.sm }}><View style={{ flex: 1 }}><Button title="Save to wishlist" onPress={() => onAction('save')} /></View><View style={{ flex: 1 }}><Button title="View details" secondary onPress={() => onAction('detail')} /></View></View>
    </View>
  </View>;
});
