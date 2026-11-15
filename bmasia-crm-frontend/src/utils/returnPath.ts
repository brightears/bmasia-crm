/**
 * The page to open after sign-in, taken from the location the route guard remembered.
 * Only same-app paths are accepted: they must start with exactly one "/" (not "//" or "/\",
 * which browsers treat as another site), contain no control characters (browsers drop tab,
 * CR and LF, so "/\t/evil.example" would become "//evil.example"), and resolve to this app's
 * own origin. Anything else falls back to `fallback`.
 */
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001F\u007F]/;

export const safeReturnPath = (
  from: { pathname?: unknown; search?: unknown } | null | undefined,
  fallback: string
): string => {
  const pathname = typeof from?.pathname === 'string' ? from.pathname : '';
  if (!/^\/(?![/\\])/.test(pathname) || CONTROL_CHARS.test(pathname)) return fallback;
  const rawSearch = typeof from?.search === 'string' ? from.search : '';
  const search = rawSearch.startsWith('?') && !CONTROL_CHARS.test(rawSearch) ? rawSearch : '';
  const target = `${pathname}${search}`;
  try {
    const origin = window.location.origin;
    if (new URL(target, origin).origin !== origin) return fallback;
  } catch {
    return fallback;
  }
  return target;
};
