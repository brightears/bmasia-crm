import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

type Value = string | number;

/** Rows-per-page choices used by the list pages; `size` from the address must be one of these. */
export const ROWS_PER_PAGE_OPTIONS: readonly number[] = [10, 25, 50, 100];

/** Which values a key may take: a list of choices, or a test. Anything else falls back to the default. */
export type AllowedValues = readonly Value[] | ((value: Value) => boolean);

/**
 * Keeps a list page's view (search, filters, sort, page, rows per page) in the address, so Back
 * from a record page returns to the same view and a filtered list can be shared as a link.
 *
 * Use it like several useState calls:
 *   const list = useListState({ q: '', status: '', sort: '-created_at', page: 0, size: 25 },
 *                             { status: ['', 'Draft', 'Sent'] });
 *   const [status, setStatus] = list.bind('status');
 *
 * - Values equal to their default are left out of the address.
 * - `page` is 0-based in code and 1-based in the address (?page=2 is the second page).
 * - Values from the address are checked: `size` must be one of ROWS_PER_PAGE_OPTIONS (or the
 *   default) unless `allowed.size` says otherwise, and keys listed in `allowed` only take the
 *   listed values. A value that fails the check is replaced by the default, so a hand-edited or
 *   outdated link never sends an unknown filter to the server.
 * - Several setters called in the same event are combined into one address update
 *   (React Router's setSearchParams would otherwise keep only the last one).
 * - Updates replace the current history entry, so typing does not fill the Back history.
 * - Do not bind a text box's value to the address directly: the router applies address changes as
 *   a deferred (transition) update, and a text box driven by those loses keystrokes. Use
 *   useListSearchBox for search boxes.
 */
export function useListState<T extends Record<string, Value>>(
  defaults: T,
  allowed: Partial<Record<keyof T, AllowedValues>> = {},
  /** Change this when a check depends on loaded data (e.g. the number of loaded users), to re-check. */
  recheck?: unknown
) {
  const [searchParams, setSearchParams] = useSearchParams();
  const pending = useRef<URLSearchParams | null>(null);
  const defaultsRef = useRef(defaults);
  const allowedRef = useRef(allowed);
  allowedRef.current = allowed;
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
      let value: Value = def;
      if (raw !== null && raw !== '') {
        if (typeof def === 'number') {
          const n = /^\d+$/.test(raw) ? parseInt(raw, 10) : NaN;
          if (!Number.isNaN(n)) value = key === 'page' ? Math.max(0, n - 1) : n;
        } else {
          value = raw;
        }
      }
      const rule: AllowedValues | undefined =
        allowedRef.current[key as keyof T] ?? (key === 'size' ? ROWS_PER_PAGE_OPTIONS : undefined);
      if (value !== def && rule) {
        const ok = typeof rule === 'function' ? rule(value) : rule.includes(value);
        if (!ok) value = def;
      }
      out[key] = value;
    });
    return out as T;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, recheck]);

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

/** A record id as the API uses them: a UUID (with or without dashes) or a whole number. */
export const isRecordId = (value: Value) =>
  /^\d+$/.test(String(value)) ||
  /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(String(value));

/**
 * A check for a filter that holds a record id from a loaded list (owner, company): the value must
 * look like an id, and once the list has loaded it must be in it. Pass the list's length as
 * useListState's `recheck` so the check runs again when the list arrives.
 */
export const idFromList =
  (items: readonly { id: unknown }[] | null | undefined, ...extra: Value[]) =>
  (value: Value) =>
    extra.includes(value) ||
    (isRecordId(value) && (!items || items.length === 0 || items.some((i) => String(i.id) === String(value))));

/** Choices for a filter, from an options list such as [{ value: 'Draft', label: 'Draft' }]. */
export const optionValues = (options: readonly { value: Value }[]): Value[] => options.map((o) => o.value);

export default useListState;
