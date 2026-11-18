import { useEffect, useState } from 'react';
import reviewApi, { ReviewSettings } from '../../services/reviewApi';

/**
 * Whether suggestions are switched on, read once per minute and shared by the menu, the company
 * page link and the Review page. A failed read counts as "off": nothing about suggestions is shown.
 */
const TTL_MS = 60_000;
let cached: { at: number; promise: Promise<ReviewSettings | null> } | null = null;

export const loadReviewSettings = (force = false): Promise<ReviewSettings | null> => {
  const now = Date.now();
  if (!force && cached && now - cached.at < TTL_MS) return cached.promise;
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

/** The menu entry's state: shown only when switched on, with the number of open suggestions. */
export const useReviewNavStatus = (pollMs = 60_000): { enabled: boolean; openCount: number } => {
  const [state, setState] = useState({ enabled: false, openCount: 0 });

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      const settings = await loadReviewSettings();
      if (!proposalsOn(settings)) {
        if (alive) setState({ enabled: false, openCount: 0 });
        return;
      }
      try {
        const openCount = await reviewApi.openCount();
        if (alive) setState({ enabled: true, openCount });
      } catch {
        if (alive) setState({ enabled: true, openCount: 0 });
      }
    };
    refresh();
    const timer = setInterval(refresh, pollMs);
    const onChange = () => refresh();
    window.addEventListener(REVIEW_CHANGED_EVENT, onChange);
    return () => {
      alive = false;
      clearInterval(timer);
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
    // Older browsers without the Event constructor: the badge catches up on the next poll.
  }
};
