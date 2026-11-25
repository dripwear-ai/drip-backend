import { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { CatalogueApiError, discoverProduct, getCatalogFacets, mapProductCard, type CatalogFacets } from './api';
import { disconnectedCatalogue, type CatalogueState, type Filters } from './presentation';

const initialFilters: Filters = { query: '', brand: '', category: '', size: '', color: '' };
const emptyFacets: CatalogFacets = { brands: [], categories: [], colors: [], sizes: [] };
const Context = createContext<{ catalogue: CatalogueState; facets: CatalogFacets; filters: Filters; setFilters: (filters: Filters) => void; requestNext: (action: 'similar' | 'different-brand') => void; continueSearch: () => void; canContinue: boolean; retry: () => void } | null>(null);
export function CatalogueProvider({ children }: PropsWithChildren) {
  const [filters, setFilters] = useState(initialFilters);
  const [catalogue, setCatalogue] = useState<CatalogueState>(disconnectedCatalogue);
  const [facets, setFacets] = useState<CatalogFacets>(emptyFacets);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const sequence = useRef(0);
  const continuation = useRef<{ cursor: string; intent: 'next' | 'similar' | 'different_brand'; anchorProductId?: string } | null>(null);
  const changeFilters = useCallback((next: Filters) => {
    continuation.current = null;
    setNextCursor(null);
    setFilters(next);
  }, []);

  useEffect(() => {
    const requestId = ++sequence.current;
    const controller = new AbortController();
    const currentContinuation = continuation.current;
    continuation.current = null;
    const timer = setTimeout(() => {
      void (async () => {
        setCatalogue({ status: 'loading', product: null });
        try {
          const catalogFacets = await getCatalogFacets(controller.signal);
          if (requestId !== sequence.current) return;
          setFacets(catalogFacets);
          const page = await discoverProduct(filters, catalogFacets.brands, currentContinuation, controller.signal);
          const selected = page.items.map(mapProductCard).find(item => item !== null) ?? null;
          if (requestId !== sequence.current) return;
          setNextCursor(page.nextCursor);
          setCatalogue(selected ? { status: 'ready', product: selected } : { status: 'empty', product: null });
        } catch (error) {
          if (requestId !== sequence.current || controller.signal.aborted) return;
          setCatalogue(error instanceof CatalogueApiError && error.kind === 'not-configured'
            ? { status: 'not-connected', product: null } : { status: 'error', product: null });
        }
      })();
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [filters, refresh]);

  const requestNext = useCallback((action: 'similar' | 'different-brand') => {
    const product = catalogue.status === 'ready' ? catalogue.product : null;
    if (!product) return;
    if (!nextCursor) return;
    continuation.current = {
      cursor: nextCursor,
      intent: action === 'similar' ? 'similar' : 'different_brand',
      anchorProductId: product.id,
    };
    setRefresh(value => value + 1);
  }, [catalogue, nextCursor]);
  const retry = useCallback(() => {
    continuation.current = null;
    setNextCursor(null);
    setRefresh(value => value + 1);
  }, []);
  const continueSearch = useCallback(() => {
    if (catalogue.status !== 'empty' || !nextCursor) return;
    continuation.current = { cursor: nextCursor, intent: 'next' };
    setRefresh(value => value + 1);
  }, [catalogue.status, nextCursor]);

  return <Context.Provider value={{ catalogue, facets, filters, setFilters: changeFilters, requestNext, continueSearch, canContinue: catalogue.status === 'empty' && nextCursor !== null, retry }}>{children}</Context.Provider>;
}
export function useCatalogue() {
  const context = useContext(Context);
  if (!context) throw new Error('Catalogue presentation context is missing.');
  return context;
}
