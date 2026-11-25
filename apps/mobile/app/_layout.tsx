import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useReducedMotion } from 'react-native-reanimated';
import { CatalogueProvider } from '../src/catalog/context';
import { palette as c } from '../src/theme';

export default function RootLayout() {
  const reduced = useReducedMotion();
  return <GestureHandlerRootView style={{ flex: 1 }}>
    <CatalogueProvider>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerStyle: { backgroundColor: c.background }, headerTintColor: c.ink,
        headerShadowVisible: false, contentStyle: { backgroundColor: c.background }, ...(reduced ? { animation: 'none' as const } : {}) }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="(browse)" options={{ headerShown: false }} />
        <Stack.Screen name="category" options={{ headerShown: false, presentation: 'card' }} />
        <Stack.Screen name="sign-in" options={{ title: 'Sign in', presentation: 'modal' }} />
        <Stack.Screen name="product" options={{ title: 'The details' }} />
        <Stack.Screen name="outfit/[id]" options={{ title: 'The complete look' }} />
        <Stack.Screen name="outfit/wardrobe" options={{ headerShown: false }} />
        <Stack.Screen name="outfit/try-on" options={{ headerShown: false }} />
        <Stack.Screen name="wishlist" options={{ title: 'Wishlist' }} />
        <Stack.Screen name="cart" options={{ title: 'Cart' }} />
      </Stack>
    </CatalogueProvider>
  </GestureHandlerRootView>;
}
