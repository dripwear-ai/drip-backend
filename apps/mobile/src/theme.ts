import { Platform } from 'react-native';

export const palette = {
  background: '#211E1B', surface: '#302A25', raised: '#40372F', ink: '#F3EEE4',
  muted: '#B2A89A', line: '#51463C', accent: '#D7F45C', onAccent: '#20251A',
  paper: '#F2E7D8', onPaper: '#211E1B', warning: '#D18A68', clay: '#C77858',
  glass: 'rgba(48, 42, 37, 0.92)',
};
export const space = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 };
export const typography = {
  display: { fontSize: 48, lineHeight: 52, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif', default: 'Georgia' }) },
  title: { fontSize: 28, lineHeight: 34, fontFamily: Platform.select({ ios: 'Georgia', android: 'serif', default: 'Georgia' }) },
  heading: { fontSize: 22, lineHeight: 30, fontWeight: '600' as const },
  body: { fontSize: 16, lineHeight: 25 },
  small: { fontSize: 13, lineHeight: 20 },
  eyebrow: { fontSize: 11, lineHeight: 18, letterSpacing: 2, fontWeight: '700' as const },
};
export const motion = { duration: 400, dampingRatio: 0.8 };
