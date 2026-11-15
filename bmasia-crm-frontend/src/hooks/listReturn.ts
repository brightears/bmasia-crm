import { useLocation } from 'react-router-dom';

/**
 * A list page passes its current view (the address's search part) along when it opens a record,
 * so the record page's breadcrumb and Back button return to that same view:
 *
 *   navigate(`/opportunities/${id}`, withListView(list.searchParams));   // on the list
 *   const listPath = useListReturnPath('/opportunities');                 // on the record page
 */
export const withListView = (search: URLSearchParams | string) => ({
  state: { listSearch: String(search).replace(/^\?/, '') },
});

/** The list's address with the view the user came from, or the plain list when opened another way. */
export function useListReturnPath(listPath: string): string {
  const location = useLocation();
  const listSearch = (location.state as { listSearch?: unknown } | null)?.listSearch;
  return typeof listSearch === 'string' && listSearch && !/[#\s]/.test(listSearch) ? `${listPath}?${listSearch}` : listPath;
}
