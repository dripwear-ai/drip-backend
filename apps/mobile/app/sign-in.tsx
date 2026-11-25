import { router, useLocalSearchParams } from 'expo-router';
import { Button, Copy, Empty, Page } from '../src/components/ui';
import { palette as c } from '../src/theme';
export default function SignIn() {
  const { method, intent } = useLocalSearchParams<{ method?: string; intent?: string }>();
  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>YOUR OWN COLLECTION</Copy>
    <Empty label="Sign-in not connected" title={intent === 'save' ? 'Keep this find in mind.' : 'Your style, across devices.'}
      message={(method === 'google' ? 'Google sign-in' : method === 'email' ? 'Email/password sign-in' : 'Sign-in') + ' will be available once the secure connection is ready. No account has been created and nothing has been saved.'} />
    {intent === 'save' && <Copy>Your current card is preserved. After signing in, you’ll be asked to confirm the save. It is saved only when DRIP confirms it.</Copy>}
    <Button title="Continue with Google · unavailable" disabled />
    <Button title="Continue with email/password · unavailable" disabled />
    <Button title="Continue browsing" secondary onPress={() => router.canGoBack() ? router.back() : router.replace('/discover')} />
  </Page>;
}
