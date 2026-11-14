import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * The text of a list's search box, kept in the page's own state so every keystroke shows at once,
 * and written to the address about `delay` ms after typing stops.
 *
 * Why: the router applies address changes as a deferred (transition) update. A text box whose value
 * comes straight from the address is put back to the last committed text after each keystroke, so
 * fast typing on a slow device loses characters ("lumen" becomes "ln").
 *
 *   const [search, setSearch] = list.bind('q');
 *   const searchBox = useListSearchBox(search, (text) => { setSearch(text); setPage(0); });
 *   <TextField value={searchBox.value} onChange={(e) => searchBox.onChange(e.target.value)} />
 *
 * - `committed` is the search text in the address. When it changes for another reason (Back,
 *   Forward, a link, a "clear filters" button), the box shows the new text and any pending write
 *   is dropped.
 * - The page's own writes coming back from the address never overwrite newer typing.
 * - `flush()` writes the pending text at once (for example on Enter).
 * - Nothing is written after the page is left.
 */
export function useListSearchBox(committed: string, commit: (text: string) => void, delay = 250) {
  const [text, setText] = useState(committed);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingText = useRef<string | null>(null);
  // Texts this box has written to the address that the address has not shown yet, oldest first.
  const inFlight = useRef<string[]>([]);
  const committedRef = useRef(committed);
  committedRef.current = committed;
  const commitRef = useRef(commit);
  commitRef.current = commit;

  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pendingText.current = null;
  };

  useEffect(() => {
    const own = inFlight.current.indexOf(committed);
    if (own !== -1) {
      // One of our own writes arriving: keep whatever has been typed since.
      inFlight.current = inFlight.current.slice(own + 1);
      return;
    }
    // Changed from outside the box.
    inFlight.current = [];
    cancel();
    setText(committed);
  }, [committed]);

  useEffect(() => cancel, []);

  const write = useCallback((value: string) => {
    timer.current = null;
    pendingText.current = null;
    if (value === committedRef.current && inFlight.current.length === 0) return;
    inFlight.current.push(value);
    commitRef.current(value);
  }, []);

  const onChange = useCallback(
    (value: string) => {
      setText(value);
      if (timer.current) clearTimeout(timer.current);
      pendingText.current = value;
      timer.current = setTimeout(() => write(value), delay);
    },
    [delay, write]
  );

  const flush = useCallback(() => {
    if (pendingText.current === null) return;
    const value = pendingText.current;
    if (timer.current) clearTimeout(timer.current);
    write(value);
  }, [write]);

  return { value: text, onChange, flush };
}

export default useListSearchBox;
