import { useEffect, useState } from 'react';
import reviewApi, { ReviewSettings } from '../../services/reviewApi';

/**
 * Whether suggestions are switched on. The switch is a server setting that changes only with a
 * restart, so it is read once per page load and again when the browser tab becomes visible, at
 * most once a minute. Nothing polls while suggestions are off. A failed read counts as "off".
 */
const MIN_INTERVAL_MS = 60_000;
let cached: { at: number; promise: Promise<ReviewSettings | null> } | null = null;

export const loadReviewSettings = (force = false): Promise<ReviewSettings | null> => {
  const now = Date.now();
  if (!force && cached && now - cached.at < MIN_INTERVAL_MS) return cached.promise;
  const promise = reviewApi.getSettings().catch(() => null);
  cached = { at: now, promise };
  return promise;
};

/** For tests. */
export const resetReviewSettingsCache = () => {
  cached = null;
};

export const proposalsOn = (settings: ReviewSettings | null | undefined): boolean =>
  Boolean(settings && settings.proposals_enabled === true);

const tabVisible = () => typeof document === 'undefined' || document.visibilityState !== 'hidden';

/**
 * The menu entry's state: shown only when switched on, with the number of open suggestions.
 * While on, the count is read once a minute, and only while the tab is visible.
 */
export const useReviewNavStatus = (pollMs = 60_000): { enabled: boolean; openCount: number } => {
  const [state, setState] = useState({ enabled: false, openCount: 0 });

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setInterval> | null = null;
    let on = false;

    const count = async () => {
      try {
        const openCount = await reviewApi.openCount();
        if (alive) setState({ enabled: true, openCount });
      } catch {
        if (alive) setState((s) => ({ ...s, enabled: true }));
      }
    };
    const stopPolling = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    const check = async () => {
      on = proposalsOn(await loadReviewSettings());
      if (!alive) return;
      if (!on) {
        stopPolling();
        setState({ enabled: false, openCount: 0 });
        return;
      }
      await count();
      if (alive && !timer && tabVisible()) {
        timer = setInterval(() => (tabVisible() ? count() : stopPolling()), pollMs);
      }
    };
    const onVisibility = () => {
      if (tabVisible()) check();
      else stopPolling();
    };
    const onChange = () => {
      if (on) count();
    };

    check();
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener(REVIEW_CHANGED_EVENT, onChange);
    return () => {
      alive = false;
      stopPolling();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener(REVIEW_CHANGED_EVENT, onChange);
    };
  }, [pollMs]);

  return state;
};

/** Fired by the Review page after a decision, so the menu badge updates at once. */
export const REVIEW_CHANGED_EVENT = 'bmasia:review-changed';
export const announceReviewChange = () => {
  try {
    window.dispatchEvent(new Event(REVIEW_CHANGED_EVENT));
  } catch {
    // Older browsers without the Event constructor: the badge catches up on the next read.
  }
};
