import Link from 'next/link';
import { EmptyState, Heading } from './portal-shell';
export function Overview({ seller = false }: { seller?: boolean }) {
  const href = seller ? '/seller/submissions/new' : '/admin/catalog/new';
  return <>
    <Heading kicker={seller ? 'SELLER STUDIO / OVERVIEW' : 'ADMINISTRATION / OVERVIEW'} title={seller ? 'Good things begin here.' : 'A considered catalogue.'}
      description={seller ? 'Prepare your product story. Every submission will need an admin review before it can reach Discover.' : 'A workspace for the pieces, people and provenance behind every DRIP discovery.'}
      action={<Link className="button primary" href={href}>{seller ? 'Prepare a submission' : 'Open product form'} <span>↗</span></Link>} />
    <section className="editorial-panel"><div><span className="eyebrow">THE STANDARD</span><h2>{seller ? 'Your products.\nA clear path to review.' : 'Every piece has\na real source.'}</h2></div>
      <p>{seller ? 'Add accurate variants, source-backed prices and image rights. Submission and publishing are not connected in this preview.' : 'Build around approved imagery, exact prices and traceable sources. A beautiful catalogue starts with information you can stand behind.'}</p></section>
    <div className="section-title"><h2>{seller ? 'Your submissions' : 'Catalogue at a glance'}</h2><span>LIVE DATA NOT CONNECTED</span></div>
    <EmptyState title={seller ? 'No submissions loaded' : 'No published products loaded'} action={<Link className="text-link" href={seller ? '/seller/submissions' : '/admin/catalog'}>Explore the workspace →</Link>}>
      {seller ? 'There is no seller account or submission connection yet. No review status has been created.' : 'The catalogue is not connected. Published products and their status will appear here when the authorized service is available.'}
    </EmptyState>
    <div className="process-strip">{['Describe accurately', 'Verify sources & rights', 'Review before publication'].map((label, i) => <div key={label}><span>0{i + 1}</span><p>{label}</p></div>)}</div>
  </>;
}
