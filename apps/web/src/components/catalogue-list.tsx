'use client';
import { useState } from 'react';
import Link from 'next/link';
import { EmptyState, Heading } from './portal-shell';
export function CatalogueList({ seller = false }: { seller?: boolean }) {
  const [query, setQuery] = useState(''), [status, setStatus] = useState('');
  return <>
    <Heading kicker={seller ? 'SELLER / SUBMISSIONS' : 'ADMIN / CATALOGUE'} title={seller ? 'Your product submissions.' : 'The collection, carefully kept.'}
      description="Search and review real records when the catalogue is connected. This preview contains no sample products."
      action={<div className="button-row"><Link className="button secondary" href={seller ? '/seller/submissions/import' : '/admin/catalog/import'}>{seller ? 'Prepare bulk file' : 'Import brand feed'} ↗</Link><Link className="button primary" href={seller ? '/seller/submissions/new' : '/admin/catalog/new'}>{seller ? 'Prepare submission' : 'New product'} ↗</Link></div>} />
    <div className="toolbar">
      <label className="search-field"><span>Search catalogue</span><input type="search" maxLength={80} value={query} onChange={e => setQuery(e.target.value)} placeholder="Product, brand or keyword" /></label>
      <label><span>State</span><select value={status} onChange={e => setStatus(e.target.value)}><option value="">All states</option><option value="draft">Draft</option><option value="pending_review">Pending review</option><option value="published">Published</option><option value="withdrawn">Withdrawn</option></select></label>
      <button className="button secondary" onClick={() => { setQuery(''); setStatus(''); }}>Clear filters</button>
    </div>
    <p className="inline-note" role="status">{query || status ? 'Filters selected. No search was sent because the catalogue is not connected.' : 'Catalogue connection unavailable. No records have been loaded.'}</p>
    <div className="table-wrap"><table><caption>{seller ? 'Submission records' : 'Catalogue records'} — not connected</caption><thead><tr><th>Product / brand</th><th>Variants</th><th>Price freshness</th><th>State</th><th>Review</th></tr></thead><tbody><tr><td colSpan={5}><EmptyState title="A blank page, for real products.">No records are available to view, edit or withdraw. Add real information in the preparation form; persistence remains unavailable.</EmptyState></td></tr></tbody></table></div>
    <p className="footnote">{seller ? 'Only authorized admins can publish approved submissions.' : 'Existing product editing requires a selected real record. No placeholder product is created for editing.'}</p>
  </>;
}
