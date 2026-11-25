import { memo, useCallback, useMemo, useState, type ComponentProps, type ReactNode } from 'react';
import { Image, ImageBackground, Pressable, StyleSheet, Text, View, type ImageSourcePropType } from 'react-native';
import { router, usePathname } from 'expo-router';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { ReduceMotion, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring } from 'react-native-reanimated';
import { scheduleOnRN } from 'react-native-worklets';
import { useLovableStore } from './lovable-store';
import { palette as c } from './theme';

export const label = { fontSize: 10, lineHeight: 14, fontWeight: '800' as const, letterSpacing: 1.5 };
export const serif = { fontFamily: 'Georgia', fontWeight: '400' as const, letterSpacing: -0.6 };
export const glass = { backgroundColor: c.glass, borderColor: 'rgba(243,238,228,0.14)', borderWidth: 1 };

export function T({ children, style, ...props }: ComponentProps<typeof Text>) {
  return <Text {...props} style={[{ color: c.ink, fontFamily: 'System', fontSize: 14 }, style]}>{children}</Text>;
}

export function TopBar({ title, back = false, overlay = false }: { title?: string; back?: boolean; overlay?: boolean }) {
  const { wishlist, bag } = useLovableStore();
  return <View style={{ height: 64, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: overlay ? 'transparent' : c.background, zIndex: 20 }}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      {back ? <Pressable accessibilityRole="button" accessibilityLabel="Go back" onPress={() => router.back()} style={[glass, { width: 40, height: 40, borderRadius: 22, alignItems: 'center', justifyContent: 'center' }]}><T style={{ fontSize: 24 }}>‹</T></Pressable>
        : <Pressable accessibilityRole="link" accessibilityLabel="Drip home" onPress={() => router.replace('/')}><T style={[serif, { fontSize: 30, fontStyle: 'italic' }]}>Drip<T style={{ color: c.accent }}>.</T></T></Pressable>}
      {!!title && <T style={[label, { maxWidth: 190 }]} numberOfLines={1}>{title.toUpperCase()}</T>}
    </View>
    <View style={{ flexDirection: 'row', gap: 8 }}>
      <HeaderIcon label="Wishlist" symbol="♡" path="/wishlist" count={wishlist.length} />
      <HeaderIcon label="Bag" symbol="▱" path="/cart" count={bag.length} />
    </View>
  </View>;
}
function HeaderIcon({ label: title, symbol, path, count }: { label: string; symbol: string; path: '/wishlist' | '/cart'; count: number }) {
  return <Pressable accessibilityRole="link" accessibilityLabel={title} onPress={() => router.push(path)} style={[glass, { width: 40, height: 40, borderRadius: 24, justifyContent: 'center', alignItems: 'center' }]}>
    <T style={{ fontSize: 21 }}>{symbol}</T>{count > 0 && <View style={{ position: 'absolute', right: -3, top: -3, minWidth: 18, height: 18, paddingHorizontal: 4, backgroundColor: c.accent, borderRadius: 10, alignItems: 'center', justifyContent: 'center' }}><T style={{ fontSize: 9, color: c.onAccent, fontWeight: '800' }}>{count}</T></View>}
  </Pressable>;
}

export function BottomDock({ active = 'discover' }: { active?: 'discover' | 'ootd' }) {
  const path = usePathname();
  const selected = path.startsWith('/outfit') ? 'ootd' : active;
  return <View style={{ position: 'absolute', zIndex: 40, bottom: 12, left: 0, right: 0, alignItems: 'center', paddingHorizontal: 20 }}>
    <View style={[glass, { width: '100%', maxWidth: 440, flexDirection: 'row', borderRadius: 999, padding: 6, gap: 6,
      shadowColor: '#000', shadowOpacity: 0.55, shadowRadius: 20, shadowOffset: { width: 0, height: 12 }, elevation: 12 }]}>
      <DockItem title="Discover" symbol="⌕" active={selected === 'discover'} onPress={() => router.replace('/discover')} />
      <DockItem title="OOTD" symbol="✦" active={selected === 'ootd'} onPress={() => router.replace('/outfit')} />
    </View>
  </View>;
}
function DockItem({ title, symbol, active, onPress }: { title: string; symbol: string; active: boolean; onPress: () => void }) {
  return <Pressable accessibilityRole="tab" accessibilityState={{ selected: active }} onPress={onPress}
    style={({ pressed }) => ({ flex: 1, height: 48, borderRadius: 999, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
      backgroundColor: active ? c.accent : 'transparent', opacity: pressed ? 0.75 : 1 })}>
    <T style={{ color: active ? c.onAccent : c.ink, fontSize: 17 }}>{symbol}</T><T style={[label, { color: active ? c.onAccent : c.muted }]}>{title.toUpperCase()}</T>
  </Pressable>;
}

export function ActionButtons({ onAction, upLabel, rightLabel = 'Save to wishlist', rightKind = 'heart', rightSymbol }: { onAction: (direction: SwipeDir) => void; upLabel?: string; rightLabel?: string; rightKind?: 'heart' | 'bag'; rightSymbol?: string }) {
  return <View style={{ flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 16, paddingVertical: 12 }}>
    <RoundAction label="Skip" symbol="×" onPress={() => onAction('left')} />
    {!!upLabel && <Pressable accessibilityRole="button" accessibilityLabel={upLabel} onPress={() => onAction('up')}
      style={[glass, { height: 44, paddingHorizontal: 16, borderRadius: 25, flexDirection: 'row', alignItems: 'center', gap: 7 }]}><T style={{ fontSize: 16 }}>↑</T><T style={label}>{upLabel.toUpperCase()}</T></Pressable>}
    <RoundAction label={rightLabel} symbol={rightSymbol ?? (rightKind === 'heart' ? '♡' : '▱')} active onPress={() => onAction('right')} />
  </View>;
}
function RoundAction({ label: title, symbol, active, onPress }: { label: string; symbol: string; active?: boolean; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress}
    style={({ pressed }) => [{ width: 56, height: 56, borderRadius: 30, alignItems: 'center', justifyContent: 'center',
      backgroundColor: active ? c.accent : c.glass, borderColor: active ? c.accent : c.line, borderWidth: 1, opacity: pressed ? 0.72 : 1,
      shadowColor: active ? c.accent : '#000', shadowOpacity: active ? 0.36 : 0.15, shadowRadius: 14, elevation: 5 }]}>
    <T style={{ color: active ? c.onAccent : '#EA7A68', fontSize: 29, lineHeight: 34 }}>{symbol}</T>
  </Pressable>;
}

export type SwipeDir = 'left' | 'right' | 'up';
export type DeckHandle = { swipe: (direction: SwipeDir) => void; reset: () => void };
type DeckProps<T> = { items: readonly T[]; getKey: (item: T) => string; renderCard: (item: T, active: boolean) => ReactNode;
  onSwipe?: (direction: SwipeDir, item: T) => 'stay' | void; onTap?: (item: T) => void; allowUp?: boolean;
  labels?: { left: string; right: string; up?: string }; empty?: ReactNode; initialIndex?: number; showActions?: boolean; rightKind?: 'heart' | 'bag'; rightActionLabel?: string; rightSymbol?: string };

export function SwipeDeck<T>({ items, getKey, renderCard, onSwipe, onTap, allowUp = false,
  labels = { left: 'Nope', right: 'Save' }, empty, initialIndex = 0, showActions = false, rightKind = 'heart', rightActionLabel, rightSymbol }: DeckProps<T>) {
  const [index, setIndex] = useState(initialIndex);
  const [busy, setBusy] = useState(false);
  const x = useSharedValue(0), y = useSharedValue(0);
  const reduced = useReducedMotion();
  const item = items[index];
  const likeStamp = useAnimatedStyle(() => ({ opacity: Math.max(0, Math.min(1, x.get() / 90)) }));
  const nopeStamp = useAnimatedStyle(() => ({ opacity: Math.max(0, Math.min(1, -x.get() / 90)) }));
  const upStamp = useAnimatedStyle(() => ({ opacity: allowUp && y.get() < 0 ? Math.min(1, -y.get() / 90) : 0 }));
  const swipe = useCallback((direction: SwipeDir) => {
    if (!item || busy) return;
    setBusy(true);
    const outcome = onSwipe?.(direction, item);
    if (outcome !== 'stay') setIndex(current => Math.min(items.length, current + 1));
    x.set(withSpring(0, { reduceMotion: ReduceMotion.System }));
    y.set(withSpring(0, { reduceMotion: ReduceMotion.System }));
    setTimeout(() => setBusy(false), 240);
  }, [busy, item, items.length, onSwipe, x, y]);
  const tap = useCallback(() => { if (item) onTap?.(item); }, [item, onTap]);
  const gesture = useMemo(() => {
    const pan = Gesture.Pan().enabled(!!item && !busy).minDistance(8)
      .onUpdate(event => { x.set(event.translationX); y.set(event.translationY); })
      .onEnd(event => {
        if (allowUp && event.translationY < -100 && Math.abs(event.translationY) > Math.abs(event.translationX)) scheduleOnRN(swipe, 'up');
        else if (event.translationX > 105) scheduleOnRN(swipe, 'right');
        else if (event.translationX < -105) scheduleOnRN(swipe, 'left');
        else { x.set(withSpring(0)); y.set(withSpring(0)); }
      });
    const press = Gesture.Tap().enabled(!!item).maxDistance(10).onEnd((_event, success) => { if (success) scheduleOnRN(tap); });
    return Gesture.Exclusive(pan, press);
  }, [allowUp, busy, item, swipe, tap, x, y]);
  const motion = useAnimatedStyle(() => ({ transform: [{ translateX: reduced ? 0 : x.get() }, { translateY: reduced ? 0 : y.get() }, { rotate: reduced ? '0deg' : `${x.get() / 18}deg` }] }));
  if (!item) return <View style={{ flex: 1, minHeight: 280, justifyContent: 'center' }}>{empty}</View>;
  return <View style={{ flex: 1, minHeight: 320 }}>
    <View style={{ flex: 1, minHeight: 270 }}>
    {[items[index + 2], items[index + 1]].filter(Boolean).map((under, layer) => <View key={getKey(under!)} pointerEvents="none"
      style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, overflow: 'hidden', borderRadius: 28, transform: [{ translateY: 11 * (layer + 1) }, { scale: 1 - (layer + 1) * 0.045 }], opacity: 0.48, zIndex: layer }}>
      {renderCard(under!, false)}</View>)}
    <GestureDetector gesture={gesture}><Animated.View accessible accessibilityRole="button" accessibilityLabel="Swipe card" style={[{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, overflow: 'hidden', borderRadius: 28,
      backgroundColor: c.surface, zIndex: 5, shadowColor: '#000', shadowOpacity: 0.42, shadowRadius: 26, elevation: 8 }, motion]}>
      {renderCard(item, true)}
      <Animated.View pointerEvents="none" style={[{ position: 'absolute', top: 26, left: 24, transform: [{ rotate: '-12deg' }] }, likeStamp]}><T style={[label, { fontSize: 21, color: c.accent }]}>{labels.right.toUpperCase()}</T></Animated.View>
      <Animated.View pointerEvents="none" style={[{ position: 'absolute', top: 26, right: 24, transform: [{ rotate: '12deg' }] }, nopeStamp]}><T style={[label, { fontSize: 21, color: '#E87966' }]}>{labels.left.toUpperCase()}</T></Animated.View>
      {allowUp && !!labels.up && <Animated.View pointerEvents="none" style={[{ position: 'absolute', top: 90, alignSelf: 'center' }, upStamp]}><T style={[label, { color: c.accent }]}>{labels.up.toUpperCase()}</T></Animated.View>}
    </Animated.View></GestureDetector>
    </View>
    {showActions && <ActionButtons onAction={swipe} upLabel={allowUp ? labels.up : undefined}
      rightLabel={rightActionLabel ?? (rightKind === 'bag' ? 'Add to bag' : 'Save to wishlist')}
      rightKind={rightKind} rightSymbol={rightSymbol} />}
  </View>;
}

export const RefImage = memo(function RefImage({ source, alt, style }: { source: ImageSourcePropType; alt: string; style: object }) {
  return <Image source={source} accessibilityLabel={alt} resizeMode="cover" style={[{ backgroundColor: c.surface }, style]} />;
});

export function Chip({ children, active = false, onPress }: { children: string; active?: boolean; onPress?: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ selected: active }} onPress={onPress} style={[glass, { paddingHorizontal: 13, paddingVertical: 8, borderRadius: 24,
    backgroundColor: active ? 'rgba(215,244,92,0.12)' : c.glass, borderColor: active ? c.accent : c.line }]}><T style={{ fontSize: 11, fontWeight: '700', color: active ? c.accent : c.ink }}>{children}</T></Pressable>;
}

export function SectionHeading({ title, accent, action, onAction }: { title: string; accent?: string; action?: string; onAction?: () => void }) {
  return <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' }}>
    <T style={[serif, { fontSize: 34, lineHeight: 38 }]}>{title} {!!accent && <T style={[serif, { fontStyle: 'italic', color: c.accent }]}>{accent}</T>}</T>
    {!!action && <Pressable onPress={onAction}><T style={[label, { color: c.accent }]}>{action.toUpperCase()}</T></Pressable>}
  </View>;
}

export function FullBleedCard({ source, children }: { source: ImageSourcePropType; children: ReactNode }) {
  return <ImageBackground source={source} resizeMode="cover" style={{ flex: 1, justifyContent: 'flex-end', backgroundColor: c.surface }}>
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, { backgroundColor: 'transparent' }]} />
    <View style={{ backgroundColor: 'rgba(26,22,19,0.72)', padding: 20 }}>{children}</View>
  </ImageBackground>;
}

export function OverlayTitle({ children }: { children: ReactNode }) {
  return <T style={[serif, { fontSize: 38, lineHeight: 42 }]}>{children}</T>;
}
