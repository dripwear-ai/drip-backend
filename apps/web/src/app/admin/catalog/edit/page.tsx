import Link from 'next/link';
import { EmptyState, Heading } from '../../../../components/portal-shell';
export default function Page() { return <><Heading kicker="ADMIN / EDIT PRODUCT" title="Start with a real record." description="The same product editor will load source-backed fields from a selected record once the authorized catalogue is connected." /><EmptyState title="No product selected" action={<Link className="button secondary" href="/admin/catalog">Back to catalogue</Link>}>No catalogue records are loaded. Editing, saving and withdrawal remain unavailable.</EmptyState></>; }
