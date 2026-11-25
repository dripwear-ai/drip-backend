'use client';

import { useState, type ChangeEvent } from 'react';
import { Heading } from './portal-shell';

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_ROWS = 5000;
const HEADERS = [
  'brand_slug', 'brand_name', 'merchant_slug', 'merchant_name', 'category_code', 'canonical_key',
  'title', 'description', 'source_listing_key', 'destination_url', 'source_variant_key', 'size_label',
  'color_label', 'image_url', 'image_alt', 'image_rights_ref', 'amount_minor', 'observed_at', 'valid_until',
];
const REQUIRED = ['brand_slug', 'brand_name', 'merchant_slug', 'merchant_name', 'category_code', 'canonical_key',
  'title', 'source_listing_key', 'destination_url', 'source_variant_key', 'image_url', 'image_alt',
  'image_rights_ref', 'amount_minor', 'observed_at', 'valid_until'];

type Preview = { fileName: string; count: number; headers: string[]; issues: string[]; sample: string[][] };

function parseCsv(input: string): { headers: string[]; rows: string[][] } {
  const rows: string[][] = [];
  let row: string[] = [], cell = '', quoted = false;
  const source = input.replace(/^\uFEFF/, '');
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') { cell += '"'; i += 1; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"' && cell.length === 0) quoted = true;
    else if (char === ',') { row.push(cell); cell = ''; }
    else if (char === '\n' || char === '\r') {
      row.push(cell); cell = '';
      if (row.some(value => value.trim())) rows.push(row);
      row = [];
      if (char === '\r' && source[i + 1] === '\n') i += 1;
    } else cell += char;
  }
  if (quoted) throw new Error('A quoted CSV field is not closed.');
  if (cell.length || row.length) { row.push(cell); if (row.some(value => value.trim())) rows.push(row); }
  const headers = rows.shift()?.map(value => value.trim()) ?? [];
  if (!headers.length || new Set(headers).size !== headers.length) throw new Error('The CSV needs one header row with unique column names.');
  if (headers.some(header => !HEADERS.includes(header))) throw new Error('The CSV contains an unsupported column. Use the documented import template columns.');
  return { headers, rows };
}

function safeHttps(value: string): boolean {
  try { const url = new URL(value); return url.protocol === 'https:' && !!url.hostname && !url.username && !url.password && !url.port && !url.hash; }
  catch { return false; }
}

function inspectFile(name: string, raw: string, bytes: number): Preview {
  if (bytes > MAX_FILE_BYTES) throw new Error('Choose a CSV file no larger than 5 MiB.');
  const { headers, rows } = parseCsv(raw);
  if (rows.length > MAX_ROWS) throw new Error('A feed preview is limited to 5,000 rows.');
  const missing = REQUIRED.filter(header => !headers.includes(header));
  if (missing.length) throw new Error(`Missing required columns: ${missing.join(', ')}.`);
  const issues: string[] = [];
  const positions = new Map(headers.map((header, index) => [header, index]));
  const seen = new Set<string>();
  const get = (cells: string[], key: string) => cells[positions.get(key) ?? -1]?.trim() ?? '';
  rows.forEach((cells, index) => {
    const line = index + 2;
    if (cells.length !== headers.length) issues.push(`Row ${line}: column count does not match the header.`);
    for (const header of REQUIRED) if (!get(cells, header)) issues.push(`Row ${line}: ${header} is required.`);
    if (get(cells, 'destination_url') && !safeHttps(get(cells, 'destination_url'))) issues.push(`Row ${line}: destination_url must be a credential-free HTTPS URL.`);
    if (get(cells, 'image_url') && !safeHttps(get(cells, 'image_url'))) issues.push(`Row ${line}: image_url must be a credential-free HTTPS URL.`);
    const amount = get(cells, 'amount_minor');
    const maxPaise = '9223372036854775807';
    if (!/^[1-9]\d{0,18}$/.test(amount) || amount.length > maxPaise.length || (amount.length === maxPaise.length && amount > maxPaise)) issues.push(`Row ${line}: amount_minor must be positive INR paise within signed BIGINT range.`);
    const observedText = get(cells, 'observed_at'), untilText = get(cells, 'valid_until');
    const hasOffset = (value: string) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
    const observed = Date.parse(observedText), until = Date.parse(untilText);
    if (!hasOffset(observedText) || !hasOffset(untilText) || !Number.isFinite(observed) || !Number.isFinite(until) || until <= observed) issues.push(`Row ${line}: observed_at and valid_until must be timezone-aware timestamps in order.`);
    const key = ['brand_slug', 'canonical_key', 'merchant_slug', 'source_listing_key', 'source_variant_key'].map(name => get(cells, name).toLowerCase()).join('|');
    if (seen.has(key)) issues.push(`Row ${line}: duplicate source variant identity.`);
    seen.add(key);
  });
  return { fileName: name, count: rows.length, headers, issues: issues.slice(0, 100), sample: rows.slice(0, 5) };
}

export function CatalogImport({ mode }: { mode: 'admin' | 'seller' }) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [endpointError, setEndpointError] = useState('');
  const heading = mode === 'admin' ? 'Bring a brand feed into review.' : 'Prepare a product feed for review.';

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    setPreview(null); setError('');
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) { setError('Choose a CSV file.'); return; }
    try { setPreview(inspectFile(file.name, await file.text(), file.size)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'The file could not be read.'); }
  }

  function validateEndpoint() {
    let valid = false;
    try { const url = new URL(endpoint); valid = url.protocol === 'https:' && !!url.hostname && !url.username && !url.password && !url.port && !url.hash; } catch { /* invalid URL */ }
    setEndpointError(valid ? 'URL format looks valid. It has not been contacted or saved.' : 'Enter a credential-free HTTPS feed URL. Do not put API keys or secrets in this field.');
  }

  return <>
    <Heading kicker={mode === 'admin' ? 'ADMIN / SOURCE INGESTION' : 'SELLER / BULK SUBMISSION'} title={heading}
      description="Use a brand-provided CSV export or feed URL. This workspace checks format locally; it does not fetch the feed, upload the file, save products or publish to Discover." />
    <div className="import-grid">
      <section className="form-section">
        <h2><span>01</span> CSV feed preview</h2>
        <p className="footnote">Select a brand-provided file to check its header and data shape in this browser. File limit 5 MiB / 5,000 rows. No file leaves this device.</p>
        <label className="upload"><span>Choose CSV file</span><small>UTF-8 CSV · one row per product variant</small><input type="file" accept="text/csv,.csv" onChange={event => void readFile(event)} /></label>
        {error && <p role="alert" className="error-text">{error}</p>}
        {preview && <div className="import-result" aria-live="polite">
          <p className="eyebrow">LOCAL CHECK / NOT IMPORTED</p><h3>{preview.fileName}</h3><p>{preview.count.toLocaleString()} rows read · {preview.issues.length ? `${preview.issues.length} issue(s) found` : 'shape checks passed'}</p>
          {preview.issues.length > 0 && <ul className="import-issues">{preview.issues.slice(0, 12).map((issue, index) => <li key={`${index}-${issue}`}>{issue}</li>)}</ul>}
          {preview.sample.length > 0 && <div className="table-wrap"><table><caption>First {preview.sample.length} rows (local preview only)</caption><thead><tr>{['brand_slug', 'title', 'category_code', 'amount_minor', 'destination_url'].map(header => <th key={header}>{header.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{preview.sample.map((row, index) => <tr key={index}>{['brand_slug', 'title', 'category_code', 'amount_minor', 'destination_url'].map(header => <td key={header}>{row[preview.headers.indexOf(header)] ?? ''}</td>)}</tr>)}</tbody></table></div>}
          <button className="button secondary" type="button" disabled>{mode === 'admin' ? 'Send valid rows to draft review · not connected' : 'Submit feed for admin review · not connected'}</button>
          <p className="footnote">A valid file is not a saved product. Authentication, import API, source approval and admin publication are not connected.</p>
        </div>}
      </section>
      <section className="form-section">
        <h2><span>02</span> Brand API feed</h2>
        <p className="footnote">Enter only the public, brand-provided endpoint URL. Never paste a bearer token, API key or private URL with credentials.</p>
        <label><span>HTTPS feed endpoint</span><input type="url" value={endpoint} maxLength={2048} placeholder="https://brand.example/feed" onChange={event => { setEndpoint(event.target.value); setEndpointError(''); }} /></label>
        <button className="button secondary" type="button" onClick={validateEndpoint}>Check URL format</button>
        {endpointError && <p role="status" className={endpointError.startsWith('URL format') ? 'footnote' : 'error-text'}>{endpointError}</p>}
        <p className="footnote">No request was sent. Server-side allowlisting, feed authentication, SSRF protections, scheduled sync, row mapping, audit and admin review must be configured before a feed can populate the catalogue.</p>
      </section>
    </div>
    <section className="import-template"><p className="eyebrow">FEED CONTRACT / REQUIRED COLUMNS</p><p>{HEADERS.join(', ')}</p><p className="footnote">Prices are integer INR paise. Image rights references and source timestamps are required. Rows enter draft review only after the authorized import API is connected.</p></section>
  </>;
}
