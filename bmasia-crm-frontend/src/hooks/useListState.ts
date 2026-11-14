import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

type Value = string | number;

/**
 * Keeps a list page's view (search, filters, sort, page, rows per page) in the address, so Back
 * from a record page returns to the same view and a filtered list can be shared as a link.
 *
 * Use it like several useState calls:
 *   const list = useListState({ q: '', status: '', sort: '-created_at', page: 0, size: 25 });
 *   const [search, setSearch] = list.bind('q');
 *
 * - Values equal to their default are left out of the address.
 * - `page` is 0-based in code and 1-based in the address (?page=2 is the second page).
 * - Several setters called in the same event are combined into one address update
 *   (React Router's setSearchParams would otherwise keep only the last one).
 * - Updates replace the current history entry, so typing does not fill the Back history.
 */
export function useListState<T extends Record<string, Value>>(defaults: T) {
  const [searchParams, setSearchParams] = useSearchParams();
  const pending = useRef<URLSearchParams | null>(null);
  const defaultsRef = useRef(defaults);
  // Always the current address and setter, so setters kept from an earlier render (for example
  // inside a useCallback with no dependencies) still start from the current address.
  const latestParams = useRef(searchParams);
  latestParams.current = searchParams;
  const latestSetter = useRef(setSearchParams);
  latestSetter.current = setSearchParams;

  // Once the address has caught up, start from it again.
  useEffect(() => {
    pending.current = null;
  }, [searchParams]);

  const values = useMemo(() => {
    const out: Record<string, Value> = {};
    Object.entries(defaultsRef.current).forEach(([key, def]) => {
      const raw = searchParams.get(key);
      if (raw === null || raw === '') {
        out[key] = def;
      } else if (typeof def === 'number') {
        const n = parseInt(raw, 10);
        out[key] = Number.isNaN(n) ? def : key === 'page' ? Math.max(0, n - 1) : n;
      } else {
        out[key] = raw;
      }
    });
    return out as T;
  }, [searchParams]);

  const set = useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      const next = new URLSearchParams(pending.current ?? latestParams.current);
      const def = defaultsRef.current[key];
      const k = String(key);
      if (value === def || value === '' || value === null || value === undefined) {
        next.delete(k);
      } else {
        next.set(k, k === 'page' ? String(Number(value) + 1) : String(value));
      }
      pending.current = next;
      latestSetter.current(next, { replace: true });
    },
    []
  );

  const bind = useCallback(
    <K extends keyof T>(key: K): [T[K], (value: T[K]) => void] => [values[key], (value: T[K]) => set(key, value)],
    [values, set]
  );

  return { values, set, bind, searchParams };
}

export default useListState;
