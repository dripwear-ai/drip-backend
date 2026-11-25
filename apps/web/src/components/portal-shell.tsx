'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSyncExternalStore, type ReactNode } from 'react';

const subscribe = () => () => {};
// Keep native form submission disabled until client-side prevention is installed.
export function useUiReady() {
  return useSyncExternalStore(subscribe, () => true, () => false);
}

const adminLinks = [['/admin', 'Overview'], ['/admin/catalog', 'Catalogue'], ['/admin/catalog/new', 'New product'], ['/admin/catalog/import', 'Feed import'], ['/admin/review', 'Review & withdrawal'], ['/admin/activity', 'Activity']];
const sellerLinks = [['/seller', 'Overview'], ['/seller/profile', 'Business profile'], ['/seller/submissions', 'Submissions'], ['/seller/submissions/new', 'New submission'], ['/seller/submissions/import', 'Bulk file']];
export function PortalShell({ mode, children }: { mode: 'admin' | 'seller'; children: ReactNode }) {
  const path = usePathname(), links = mode === 'admin' ? adminLinks : sellerLinks;
  return <div className="portal">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <aside className="sidebar">
      <Link href="/" className="wordmark" aria-label="DRIP workspace home">DRIP<span>THE WORKSPACE</span></Link>
      <div className="realm">{mode === 'admin' ? 'Admin portal' : 'Seller portal'}<span>{mode === 'admin' ? 'Catalog management' : 'Product submissions'}</span></div>
      <nav aria-label={mode + ' navigation'}>{links.map(([href, label], index) =>
        <Link key={href} href={href} aria-current={path === href ? 'page' : undefined}><span className="nav-index">0{index + 1}</span>{label}<span aria-hidden="true">↗</span></Link>)}</nav>
      <div className="sidebar-foot"><span className="eyebrow">LOCAL PREVIEW</span><p>This workspace is not connected to accounts or product storage.</p>
        <span className="portal-address">{mode === 'admin' ? 'ADMIN / 3001' : 'SELLER / 3002'}</span></div>
    </aside>
    <div className="workspace">
      <header className="workspace-header"><span>DRIP / {mode === 'admin' ? 'CATALOGUE OPERATIONS' : 'SELLER WORKSPACE'}</span><span className="status-label"><i />Not connected</span></header>
      <div className="preview-banner" role="note">UI preview · No signed-in account. Changes stay on this page and are not saved or submitted.</div>
      <main id="workspace" tabIndex={-1}>{children}</main>
      <footer className="workspace-footer">DRIP 2.0<span>Local workspace preview</span></footer>
    </div>
  </div>;
}
export function Heading({ kicker, title, description, action }: { kicker: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{kicker}</p><h1>{title}</h1><p className="lede">{description}</p></div>{action}</div>;
}
export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-mark" aria-hidden="true">↗</div><p className="eyebrow">A CLEAR START</p><h2>{title}</h2><p>{children}</p>{action}</div>;
}
