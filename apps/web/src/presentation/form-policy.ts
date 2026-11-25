// Local input feedback only; not server validation, source approval or a wire contract.
export function rupeesToPaise(value: string): string | null {
  if (value.length > 21 || !/^(0|[1-9]\d*)(\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  const paise = (whole + fraction.padEnd(2, '0')).replace(/^0+(?=\d)/, '');
  if (BigInt(paise) <= BigInt(0) || BigInt(paise) > BigInt('9223372036854775807')) return null;
  return paise;
}
export function isHttpsInput(value: string): boolean {
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && !url.hash && !url.port && url.hostname.includes('.') && !/^[\d.]+$/.test(url.hostname) && !url.hostname.endsWith('.local'); }
  catch { return false; }
}
export function observationError(observed: string, until: string, now = Date.now()): string | null {
  const a = Date.parse(observed), b = Date.parse(until);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return 'Enter both observation and valid-until times.';
  if (a > now) return 'Observation cannot be in the future.';
  if (b <= a) return 'Valid-until must be after observation.';
  return null;
}
export function imageFileError(type: string, size: number): string | null {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(type)) return 'Choose a JPEG, PNG or WebP image.';
  if (size <= 0 || size > 10 * 1024 * 1024) return 'Choose an image between 1 byte and 10 MiB.';
  return null;
}

export function validateProductDraft(fields: Record<string, string>, variantIds: readonly number[], hasLocalImage: boolean, localImageError: string, now = Date.now()): string[] {
  const read = (key: string) => (fields[key] ?? '').trim();
  const issues: string[] = [];
  for (const [name, label] of [['title', 'Product title'], ['brand', 'Brand'], ['category', 'Category'], ['merchant', 'Merchant/source'], ['source', 'Source record reference'], ['rights', 'Image rights evidence'], ['approver', 'Rights/source approver reference']]) {
    if (!read(name)) issues.push(label + ' is required.');
  }
  if (!isHttpsInput(read('destination'))) issues.push('Retailer destination must be a credential-free HTTPS URL. Host approval is a separate review.');
  if (read('imageUrl') && !isHttpsInput(read('imageUrl'))) issues.push('Image source URL must use HTTPS without embedded credentials.');
  if (!hasLocalImage && !read('imageUrl')) issues.push('Select a local image or provide its real approved-source URL.');
  if (!read('alt')) issues.push('Describe the image for accessibility.');
  if (localImageError) issues.push(localImageError);
  if (!variantIds.length || variantIds.length > 100) issues.push('Provide between 1 and 100 variants.');
  const seen = new Set<string>();
  variantIds.forEach((id, i) => {
    const key = read('sku-' + id);
    if (!key) issues.push('Variant ' + (i + 1) + ': source variant key is required.');
    if (seen.has(key)) issues.push('Each variant needs a distinct source key.');
    seen.add(key);
    if (!rupeesToPaise(read('price-' + id))) issues.push('Variant ' + (i + 1) + ': enter a positive INR amount, at most two decimal places, within BIGINT paise.');
    const timing = observationError(read('observed-' + id), read('until-' + id), now);
    if (timing) issues.push('Variant ' + (i + 1) + ': ' + timing);
  });
  if (read('rightsChecked') !== 'on') issues.push('Confirm you have evidence of permission to use the supplied content.');
  return issues;
}
