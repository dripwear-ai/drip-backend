import { router } from 'expo-router';
import { Button, Copy, Empty, Page } from '../src/components/ui';
import { palette as c } from '../src/theme';

export default function Wishlist() {
  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>YOUR OWN COLLECTION</Copy>
    <Copy variant="title">Wishlist</Copy>
    <Empty label="Sign-in required" title="Your saved pieces belong to your account."
      message="Permanent wishlist storage and authenticated sign-in are not connected yet. Guest browsing stays available, and no local preview item is presented as a saved product." />
    <Button title="Sign in unavailable" disabled />
    <Button title="Continue discovering" secondary onPress={() => router.navigate('/discover')} />
  </Page>;
}
