import { useSyncExternalStore } from 'react';
import type { ImageSourcePropType } from 'react-native';

// The Lovable store is an in-memory UI prototype only. It is intentionally not a
// source of truth and is never persisted or sent to the API.
export type LocalSavedItem = { key: string; name: string; brand: string; price: number; image: ImageSourcePropType; kind: 'piece' | 'look' };
type State = { wishlist: LocalSavedItem[]; bag: LocalSavedItem[] };
let state: State = { wishlist: [], bag: [] };
const EMPTY: State = { wishlist: [], bag: [] };
const listeners = new Set<() => void>();
function emit() { listeners.forEach(listener => listener()); }
export function useLovableStore() {
  return useSyncExternalStore(callback => { listeners.add(callback); return () => listeners.delete(callback); }, () => state, () => EMPTY);
}
export const lovableActions = {
  save(item: LocalSavedItem) { if (state.wishlist.some(existing => existing.key === item.key)) return; state = { ...state, wishlist: [item, ...state.wishlist] }; emit(); },
  unsave(key: string) { state = { ...state, wishlist: state.wishlist.filter(item => item.key !== key) }; emit(); },
  addToBag(item: LocalSavedItem) { if (state.bag.some(existing => existing.key === item.key)) return; state = { ...state, bag: [item, ...state.bag] }; emit(); },
  removeFromBag(key: string) { state = { ...state, bag: state.bag.filter(item => item.key !== key) }; emit(); },
};
