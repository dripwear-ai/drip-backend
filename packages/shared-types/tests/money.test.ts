import type { MoneyAmount, MoneyINR } from '../src/index.js';

// Compile-time checks, run with tsc --noEmit; no application fixtures are shipped.
const zero = { currency: 'INR', amount_minor: '0' } satisfies MoneyINR;
const one = { currency: 'INR', amount_minor: '1' } satisfies MoneyINR;
const aboveSafeInteger = {
  currency: 'INR', amount_minor: '9007199254740993',
} satisfies MoneyINR;
const maximum = {
  currency: 'INR', amount_minor: '9223372036854775807',
} satisfies MoneyINR;

const numericAmount: MoneyINR = {
  currency: 'INR',
  // @ts-expect-error The wire amount must be a string, never a JS number.
  amount_minor: 1,
};
const otherCurrency: MoneyINR = {
  // @ts-expect-error This contract permits INR only.
  currency: 'USD',
  amount_minor: '1',
};

// Preserve the legacy export's shape; this is not permission for catalogue use.
const legacy = { currency: 'USD', amount_minor: 1 } satisfies MoneyAmount;
void [zero, one, aboveSafeInteger, maximum, numericAmount, otherCurrency, legacy];
