import type { PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type TextInputProps, type TextProps } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { palette as c, space as s, typography as t } from '../theme';

export function Copy({ variant = 'body', style, ...props }: TextProps & { variant?: keyof typeof t }) {
  return <Text {...props} style={[{ color: c.ink }, t[variant], style]} />;
}
export function Button({ title, onPress, disabled = false, secondary = false }: { title: string; onPress?: () => void; disabled?: boolean; secondary?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={({ pressed }) => [ui.button, secondary && ui.secondary, { opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}>
    <Copy style={{ color: secondary ? c.ink : c.onAccent, fontWeight: '600', textAlign: 'center' }}>{title}</Copy>
  </Pressable>;
}
export function Page({ children }: PropsWithChildren) {
  const insets = useSafeAreaInsets();
  return <ScrollView contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled"
    contentContainerStyle={[ui.page, { paddingBottom: Math.max(insets.bottom, s.lg) }]}>{children}</ScrollView>;
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return <View style={{ gap: s.sm }}><Copy variant="small">{label}</Copy><TextInput {...props} accessibilityLabel={label}
    placeholderTextColor={c.muted} style={[ui.input, props.style]} /></View>;
}
export function Empty({ title, message, label = 'A little space for what’s next', loading = false }: { title: string; message: string; label?: string; loading?: boolean }) {
  return <View style={ui.empty} accessibilityLiveRegion="polite">
    {loading && <ActivityIndicator color={c.accent} />}
    <Copy variant="eyebrow" style={{ color: c.accent }}>{label.toUpperCase()}</Copy>
    <Copy variant="title">{title}</Copy><Copy style={{ color: c.muted }}>{message}</Copy>
  </View>;
}
export const ui = StyleSheet.create({
  page: { flexGrow: 1, padding: s.lg, gap: s.lg, width: '100%', maxWidth: 620, alignSelf: 'center' },
  button: { minHeight: 52, padding: s.md, backgroundColor: c.accent, borderRadius: 8, justifyContent: 'center' },
  secondary: { backgroundColor: c.surface, borderWidth: 1, borderColor: c.line },
  input: { minHeight: 52, borderWidth: 1, borderColor: c.line, borderRadius: 8, color: c.ink, backgroundColor: c.surface, padding: s.md, fontSize: 16 },
  empty: { gap: s.md, paddingVertical: s.xxl, borderTopWidth: 1, borderBottomWidth: 1, borderColor: c.line },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: s.sm },
});
