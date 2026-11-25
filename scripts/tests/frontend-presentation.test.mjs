import assert from 'node:assert/strict';
import test from 'node:test';
import { approvedDestination, canPresentCard, disconnectedCatalogue, formatPaise, guestAction, priceState, swipeAction } from '../../apps/mobile/src/catalog/presentation.ts';
import { imageFileError, isHttpsInput, observationError, rupeesToPaise, validateProductDraft } from '../../apps/web/src/presentation/form-policy.ts';

// Synthetic values here are isolated test inputs, never bundled into application/catalogue data.
for (const [input, result] of [['0.01', '1'], ['1', '100'], ['1.2', '120'], ['1.23', '123'], ['90071992547409.93', '9007199254740993'], ['92233720368547758.07', '9223372036854775807']]) {
  test('exact rupee parsing ' + input, () => assert.equal(rupeesToPaise(input), result));
}
for (const [index, input] of ['', '0', '-1', '1.234', '1e2', 'NaN', '1,000', ' 1', '01', '1.', '.2', '92233720368547758.08'].entries()) {
  test('invalid rupee input ' + index, () => assert.equal(rupeesToPaise(input), null));
}
for (const [input, result] of [['1', '₹0.01'], ['100', '₹1.00'], ['123456789', '₹12,34,567.89'], ['9007199254740993', '₹9,00,71,99,25,47,409.93']]) {
  test('lossless paise display ' + input, () => assert.equal(formatPaise(input), result));
}
for (const [index, input] of ['0', '-1', '01', '1.1', '1e2', '9223372036854775808', '9'.repeat(100)].entries()) {
  test('invalid paise display ' + index, () => assert.equal(formatPaise(input), null));
}
const price = { amountMinor: '100', observedAt: '2026-10-01T00:00:00Z', validUntil: '2026-10-02T00:00:00Z' };
test('price validity uses exact interval boundaries', () => {
  assert.equal(priceState(price, Date.parse(price.observedAt) - 1), 'missing');
  assert.equal(priceState(price, Date.parse(price.observedAt)), 'current');
  assert.equal(priceState(price, Date.parse(price.validUntil) - 1), 'current');
  assert.equal(priceState(price, Date.parse(price.validUntil)), 'stale');
  assert.equal(priceState(null), 'missing');
  assert.equal(priceState({ ...price, validUntil: 'invalid' }), 'missing');
});
test('disconnected deck has no data and cannot authorize a save', () => {
  assert.deepEqual(disconnectedCatalogue, { status: 'not-connected', product: null });
  assert.equal(canPresentCard(null), false);
  for (const action of ['save', 'similar', 'different-brand', 'detail']) assert.equal(guestAction(action, false), 'catalogue-required');
});
test('guest save is sign-in intent, never a saved result', () => assert.equal(guestAction('save', true), 'sign-in-required'));
test('detail action requires a current card', () => assert.equal(guestAction('detail', true), 'detail'));
for (const [name, args, result] of [
  ['right', [100, 0, 0, 0], 'save'], ['left', [-100, 0, 0, 0], 'similar'], ['up', [0, -100, 0, 0], 'different-brand'],
  ['down', [0, 110, 0, 0], null], ['small', [20, 0, 0, 0], null], ['horizontal flick', [20, 0, 800, 0], 'save'],
  ['vertical flick', [0, -20, 0, -800], 'different-brand'], ['vertical dominance', [100, -180, 0, 0], 'different-brand'],
]) {
  test('gesture direction ' + name, () => assert.equal(swipeAction(...args, true), result));
  test('empty deck ignores ' + name, () => assert.equal(swipeAction(...args, false), null));
}
for (const [index, url] of ['http://retailer.example/item', 'javascript:alert(1)', 'https://retailer.example.evil.test/item', 'https://user:secret@retailer.example/item', 'https://retailer.example:444/item', 'https://retailer.example/item#secret', 'not-a-url'].entries()) {
  test('retailer URL fails closed ' + index, () => assert.equal(approvedDestination({ url, approvedHost: 'retailer.example' }), null));
}
test('retailer action needs an explicit approved destination', () => {
  assert.equal(approvedDestination(null), null);
  assert.equal(approvedDestination({ url: 'https://retailer.example/item', approvedHost: 'retailer.example' }), 'https://retailer.example/item');
});
test('input URL syntax is not a rights or host approval', () => {
  assert.equal(isHttpsInput('https://source.example/item'), true);
  for (const value of ['http://source.example', 'https://user:secret@source.example', 'https://127.0.0.1/item', 'https://host.local/item', 'data:text/html,content']) assert.equal(isHttpsInput(value), false);
});
test('observation order and future values rejected', () => {
  const now = Date.parse('2026-10-02T00:00:00Z');
  assert.equal(observationError(price.observedAt, price.validUntil, now), null);
  assert.ok(observationError(price.validUntil, price.observedAt, now));
  assert.ok(observationError('2026-10-03T00:00:00Z', '2026-10-04T00:00:00Z', now));
  assert.ok(observationError('', '', now));
});
test('local image previews reject active formats and large files', () => {
  assert.equal(imageFileError('image/png', 1024), null);
  assert.equal(imageFileError('image/webp', 10 * 1024 * 1024), null);
  assert.ok(imageFileError('image/svg+xml', 1024));
  assert.ok(imageFileError('image/jpeg', 10 * 1024 * 1024 + 1));
  assert.ok(imageFileError('image/jpeg', 0));
});
test('ineligible or unpriced products cannot become discovery cards', () => {
  const product = { id: 'isolated-test', eligible: false, image: { url: 'https://source.example/image', alt: 'test-only' }, variants: [{ price }] };
  assert.equal(canPresentCard(product, Date.parse(price.observedAt)), false);
  assert.equal(canPresentCard({ ...product, eligible: true }, Date.parse(price.observedAt)), true);
  assert.equal(canPresentCard({ ...product, eligible: true }, Date.parse(price.validUntil)), false);
  assert.equal(canPresentCard({ ...product, eligible: true, image: null }, Date.parse(price.observedAt)), false);
});

const draft = {
  title: 'test-only', brand: 'test-only', category: 'test-only', merchant: 'test-only',
  source: 'test-only', rights: 'test-only evidence reference', approver: 'test-only',
  destination: 'https://source.example/item', imageUrl: 'https://source.example/image',
  alt: 'test-only', rightsChecked: 'on', 'sku-0': 'test-only', 'price-0': '1.00',
  'observed-0': price.observedAt, 'until-0': price.validUntil,
};
const checkDraft = (fields, ids = [0], image = false, error = '') => validateProductDraft(fields, ids, image, error, Date.parse(price.observedAt));
test('local draft validation allows unknown size and color without fabricating them', () => {
  const before = JSON.stringify(draft);
  assert.deepEqual(checkDraft(draft), []);
  assert.equal(JSON.stringify(draft), before);
  assert.equal(draft['size-0'], undefined);
});
for (const field of ['title', 'brand', 'category', 'merchant', 'source', 'rights', 'approver', 'alt', 'rightsChecked']) {
  test('draft missing ' + field + ' fails local validation', () => assert.ok(checkDraft({ ...draft, [field]: '' }).length));
}
test('draft image evidence is required; local file does not imply approval', () => {
  assert.ok(checkDraft({ ...draft, imageUrl: '' }).length);
  assert.deepEqual(checkDraft({ ...draft, imageUrl: '' }, [0], true), []);
  assert.ok(checkDraft(draft, [0], false, 'Image rejected.').includes('Image rejected.'));
});
test('draft variants reject missing keys, duplicate identities and unsafe prices', () => {
  assert.ok(checkDraft(draft, []).length);
  assert.ok(checkDraft(draft, [0, 0]).includes('Each variant needs a distinct source key.'));
  assert.ok(checkDraft({ ...draft, 'sku-0': '' }).length);
  assert.ok(checkDraft({ ...draft, 'price-0': '1.234' }).length);
});
test('draft unsafe URL error never echoes supplied credentials', () => {
  const errors = checkDraft({ ...draft, destination: 'https://test-secret@example.test/item' });
  assert.ok(errors.length);
  assert.ok(!errors.join(' ').includes('test-secret'));
});
