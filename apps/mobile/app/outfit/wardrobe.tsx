import { router } from 'expo-router';
import { Button, Copy, Empty, Page } from '../../src/components/ui';
import { palette as c } from '../../src/theme';

export default function Wardrobe() {
  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>PERSONAL WARDROBE · NOT CONNECTED</Copy>
    <Copy variant="title">Your closet, when you’re ready.</Copy>
    <Empty label="Private feature unavailable" title="No clothing has been uploaded or analyzed."
      message="Wardrobe storage, photo consent, deletion controls and a reviewed styling service are not configured. This screen does not contain sample clothing or generated outfit advice." />
    <Button title="Clothing upload unavailable" disabled />
    <Button title="Outfit suggestions unavailable" secondary disabled />
    <Copy variant="small" style={{ color: c.muted }}>
      Before enabling uploads, DRIP needs private user-owned media storage, explicit consent, retention and deletion rules, authenticated APIs, and a reviewed recommendation approach. Your photos and wardrobe data are not being collected here.
    </Copy>
    <Button title="Back to OOTD" secondary onPress={() => router.navigate('/outfit')} />
  </Page>;
}
