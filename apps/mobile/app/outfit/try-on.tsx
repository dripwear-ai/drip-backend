import { router } from 'expo-router';
import { Button, Copy, Empty, Page } from '../../src/components/ui';
import { palette as c } from '../../src/theme';

export default function TryOn() {
  return <Page>
    <Copy variant="eyebrow" style={{ color: c.accent }}>VIRTUAL FIT · NOT CONNECTED</Copy>
    <Copy variant="title">A more personal fit preview.</Copy>
    <Empty label="3D try-on unavailable" title="No digital body model has been created."
      message="This app does not estimate or guarantee garment fit. Photo capture, measurement storage, size recommendations and 3D rendering are not connected." />
    <Button title="Create fit profile unavailable" disabled />
    <Button title="Try on a product unavailable" secondary disabled />
    <Copy variant="small" style={{ color: c.muted }}>
      Enabling this requires a verified fit model, clear consent for body measurements and photos, secure private storage, deletion/retention controls, garment sizing data, device testing and fit-accuracy validation. Do not use this preview as sizing advice.
    </Copy>
    <Button title="Back to OOTD" secondary onPress={() => router.navigate('/outfit')} />
  </Page>;
}
