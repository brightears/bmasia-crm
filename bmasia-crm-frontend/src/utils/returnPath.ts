/**
 * The page to open after sign-in, taken from the location the route guard remembered.
 * Only same-app paths are accepted: they must start with exactly one "/" (not "//" or "/\",
 * which browsers treat as another site). Anything else falls back to `fallback`.
 */
export const safeReturnPath = (
  from: { pathname?: unknown; search?: unknown } | null | undefined,
  fallback: string
): string => {
  const pathname = typeof from?.pathname === 'string' ? from.pathname : '';
  if (!/^\/(?![/\\])/.test(pathname)) return fallback;
  const search = typeof from?.search === 'string' && from.search.startsWith('?') ? from.search : '';
  return `${pathname}${search}`;
};
