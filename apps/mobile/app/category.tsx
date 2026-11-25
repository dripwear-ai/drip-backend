import { useEffect } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { palette as c } from '../src/theme';

/** Route compatibility for old category links; all inventory now comes from the API-backed discovery screen. */
export default function CategoryRedirect() {
  const { category } = useLocalSearchParams<{ category?: string }>();
  useEffect(() => {
    router.replace({ pathname: '/discover', params: typeof category === 'string' ? { category } : {} });
  }, [category]);
  return <View accessibilityLabel="Opening catalogue discovery" style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: c.background }}>
    <ActivityIndicator color={c.accent} />
  </View>;
}
