import { Tabs } from 'expo-router';
import { Copy } from '../../src/components/ui';
import { palette as c } from '../../src/theme';
export default function BrowseLayout() {
  return <Tabs screenOptions={{ headerShown: false, animation: 'none', tabBarStyle: { display: 'none' },
    tabBarActiveTintColor: c.accent, tabBarInactiveTintColor: c.muted, tabBarLabelStyle: { fontSize: 10, fontWeight: '700', letterSpacing: 1 } }}>
    <Tabs.Screen name="discover" options={{ title: 'Discover', tabBarIcon: ({ color }) => <Copy style={{ color }}>◇</Copy> }} />
    <Tabs.Screen name="outfit" options={{ title: 'OOTD', tabBarIcon: ({ color }) => <Copy style={{ color }}>▤</Copy> }} />
  </Tabs>;
}
