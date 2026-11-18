import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert,
  Badge,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  IconButton,
  Link,
  MenuItem,
  Paper,
  Popover,
  Snackbar,
  Switch,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  FactCheckOutlined,
  HelpOutline,
  InboxOutlined,
  OpenInNew,
  Refresh,
  ToggleOffOutlined,
  TaskAltOutlined,
  ManageSearchOutlined,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';
import reviewApi, {
  ChangeProposal,
  OPEN_PAGE_SIZE,
  PatchValue,
  ProposalConflict,
  ReviewApiError,
  ReviewSettings,
} from '../../services/reviewApi';
import { EmptyState, PageHeader } from '../../components/ui';
import ProposalCard, { CardHandlers, CardNotice, ConflictChoice, ContactInfo, DecisionResult } from './ProposalCard';
import ReasonDialog from './ReasonDialog';
import PlainText from './PlainText';
import {
  BULK_REJECT_MAX,
  CONFLICT_REJECT_REASON,
  CardState,
  DECIDED_STATUSES,
  EVIDENCE_LABEL,
  KIND_LABEL,
  REJECT_REASONS,
  ReviewQuery,
  ReviewTab,
  STATUS_LABEL,
  cardActions,
  displayValue,
  fieldLabel,
  groupProposals,
  needsAnotherLook,
  readOnlyReason,
  readQuery,
  sortProposals,
  writeQuery,
} from './reviewModel';
import { acceptedText, closedResult, fieldErrorsOf, outcomeOf, rejectedText } from './decisionText';
import { announceReviewChange } from './useReviewStatus';

type Load = 'loading' | 'ready' | 'error';
type DialogState =
  | { type: 'reject'; proposal: ChangeProposal; initial?: string; then?: () => void }
  | { type: 'bulk'; rows: ChangeProposal[] }
  | { type: 'reopen'; proposal: ChangeProposal }
  | null;

const DECIDED_PAGE = 25;
/** Cards rendered at once; more appear on request, so the page stays quick with a long queue. */
const RENDER_STEP = 50;
/** Contact and conflict look-ups: at most this many at a time, and this many per page visit. */
const LOOKUP_CONCURRENCY = 4;
const LOOKUP_CAP = 300;
const BULK_LIST_MAX = 8;
const SHORTCUTS_KEY = 'bmasia.review.shortcuts';

const asError = (e: unknown): ReviewApiError =>
  e instanceof ReviewApiError ? e : new ReviewApiError(undefined, 'no_answer', 'No answer from the server.');

const sameValues = (a: Record<string, PatchValue>, b: Record<string, PatchValue> | undefined) =>
  Object.keys(a).every((k) => displayValue(a[k]) === displayValue(b?.[k]));

const readShortcuts = (): boolean => {
  try {
    return localStorage.getItem(SHORTCUTS_KEY) !== 'off';
  } catch {
    return true;
  }
};

const isTypingTarget = (el: Element | null) =>
  Boolean(
    el &&
    el instanceof HTMLElement &&
    (el.tagName === 'INPUT' ||
      el.tagName === 'TEXTAREA' ||
      el.tagName === 'SELECT' ||
      el.isContentEditable ||
      el.closest('[role="dialog"],[role="listbox"],[role="menu"],[role="combobox"]')),
  );

const summary = (p: ChangeProposal) =>
  `${p.company_name}: ${KIND_LABEL[p.kind] || p.kind}${
    p.kind === 'field_update'
      ? ` (${Object.keys(p.patch || {})
          .map(fieldLabel)
          .join(', ')})`
      : ''
  }`;

/** A small queue for look-ups, so a long list never fires hundreds of requests at once. */
const useLookupQueue = () => {
  const queue = useRef<(() => Promise<void>)[]>([]);
  const running = useRef(0);
  const started = useRef(0);
  const pump = useCallback(() => {
    while (running.current < LOOKUP_CONCURRENCY && queue.current.length) {
      const job = queue.current.shift()!;
      running.current += 1;
      job().finally(() => {
        running.current -= 1;
        pump();
      });
    }
  }, []);
  return useCallback(
    (job: () => Promise<void>) => {
      if (started.current >= LOOKUP_CAP) return false;
      started.current += 1;
      queue.current.push(job);
      pump();
      return true;
    },
    [pump],
  );
};

/**
 * The Review page: a person works through what agents and jobs suggest, one decision at a time.
 * Every decision is bound to the version that was shown; a refused one is explained and the card
 * is read again, and the reviewer decides again with a fresh click.
 */
const ReviewQueue: React.FC = () => {
  const { user } = useAuth();
  const me = user?.username;
  const [search, setSearch] = useSearchParams();
  const query = readQuery(search);

  const [settings, setSettings] = useState<ReviewSettings | null>(null);
  const [settingsLoad, setSettingsLoad] = useState<Load>('loading');
  const [openRows, setOpenRows] = useState<ChangeProposal[]>([]);
  const [openLoad, setOpenLoad] = useState<Load>('loading');
  const [openTotal, setOpenTotal] = useState(0);
  const [openPage, setOpenPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [extraRows, setExtraRows] = useState<Record<string, ChangeProposal>>({});
  const [decided, setDecided] = useState<{ rows: ChangeProposal[]; count: number; page: number; load: Load }>({
    rows: [],
    count: 0,
    page: 1,
    load: 'loading',
  });
  const [notices, setNotices] = useState<Record<string, CardNotice | undefined>>({});
  const [results, setResults] = useState<Record<string, DecisionResult | undefined>>({});
  const [sticky, setSticky] = useState<Record<string, ReviewTab>>({});
  const [busy, setBusy] = useState<Set<string>>(new Set());
  const busyRef = useRef<Set<string>>(new Set());
  const [pageReadOnly, setPageReadOnly] = useState<string | null>(null);
  const [cardReadOnly, setCardReadOnly] = useState<Record<string, string>>({});
  const [contacts, setContacts] = useState<Record<string, ContactInfo>>({});
  const requested = useRef<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [focusReq, setFocusReq] = useState<{ id: string; n: number }>({ id: '', n: 0 });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, Record<string, string>>>({});
  const [acks, setAcks] = useState<Record<string, string>>({});
  const [choices, setChoices] = useState<Record<string, { choice: ConflictChoice; seen: string }>>({});
  const [sourceChecks, setSourceChecks] = useState<Record<string, string>>({});
  const armed = useRef<Record<string, boolean>>({});
  const [dialog, setDialog] = useState<DialogState>(null);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);
  const [helpAnchor, setHelpAnchor] = useState<HTMLElement | null>(null);
  const [renderLimit, setRenderLimit] = useState(RENDER_STEP);
  const [proposer, setProposer] = useState('');
  const [shortcutsOn, setShortcutsOn] = useState(readShortcuts);
  const lookup = useLookupQueue();

  /** Any change of list, filter or order clears the selection and starts the rendering window again. */
  const resetView = () => {
    setSelected(new Set());
    setRenderLimit(RENDER_STEP);
  };
  const setQuery = (patch: Partial<ReviewQuery>) => {
    resetView();
    setSearch(writeQuery({ ...query, ...patch }), { replace: false });
  };

  // ------------------------------------------------------------------ loading

  const loadSettings = useCallback(async () => {
    setSettingsLoad('loading');
    try {
      const data = await reviewApi.getSettings();
      setSettings(data);
      setSettingsLoad('ready');
      if (data.you_can_review === false) {
        setPageReadOnly(
          data.review_refusal || 'Your account is not on the list of people who may decide on suggestions.',
        );
      }
    } catch {
      setSettingsLoad('error');
    }
  }, []);

  const enabled = settingsLoad === 'ready' && settings?.proposals_enabled === true;
  const valuesFollowTarget = Boolean(settings && 'you_can_review' in settings);

  const loadOpen = useCallback(async (sort: 'newest' | 'expiring') => {
    setOpenLoad('loading');
    try {
      const data = await reviewApi.listOpen(1, sort);
      setOpenRows(data.results);
      setOpenTotal(data.count);
      setOpenPage(1);
      setOpenLoad('ready');
    } catch {
      setOpenLoad('error');
    }
  }, []);

  const loadMoreOpen = async () => {
    setLoadingMore(true);
    try {
      const data = await reviewApi.listOpen(openPage + 1, query.sort);
      setOpenRows((rows) => {
        const have = new Set(rows.map((r) => r.id));
        return [...rows, ...data.results.filter((r) => !have.has(r.id))];
      });
      setOpenTotal(data.count);
      setOpenPage((n) => n + 1);
    } catch {
      setSnack('More suggestions could not be loaded. Try again.');
    } finally {
      setLoadingMore(false);
    }
  };

  const loadDecided = useCallback(
    async (page: number) => {
      setDecided((d) => ({ ...d, load: 'loading', ...(page === 1 ? { rows: [] } : {}) }));
      try {
        const data = await reviewApi.list({
          status:
            query.decided && (DECIDED_STATUSES as string[]).includes(query.decided)
              ? [query.decided as any]
              : DECIDED_STATUSES,
          company: query.company || undefined,
          kind: query.kind ? [query.kind] : undefined,
          proposer: proposer || undefined,
          page,
          page_size: DECIDED_PAGE,
          ordering: '-created_at',
        });
        setDecided((d) => ({
          rows: page === 1 ? data.results : [...d.rows, ...data.results],
          count: data.count,
          page,
          load: 'ready',
        }));
      } catch {
        setDecided((d) => ({ ...d, load: 'error' }));
      }
    },
    [query.decided, query.company, query.kind, proposer],
  );

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (enabled) loadOpen(query.sort);
  }, [enabled, loadOpen, query.sort]);

  useEffect(() => {
    if (enabled && query.tab === 'decided') loadDecided(1);
  }, [enabled, query.tab, loadDecided]);

  // ------------------------------------------------------------------ row bookkeeping

  const updateRow = useCallback((fresh: ChangeProposal) => {
    const merge = (rows: ChangeProposal[]) => rows.map((r) => (r.id === fresh.id ? fresh : r));
    setOpenRows((rows) =>
      rows.some((r) => r.id === fresh.id) ? merge(rows) : fresh.status === 'proposed' ? [fresh, ...rows] : rows,
    );
    setDecided((d) => ({ ...d, rows: merge(d.rows) }));
    setExtraRows((x) => (x[fresh.id] ? { ...x, [fresh.id]: fresh } : x));
  }, []);

  const mergeSnapshot = useCallback((id: string, snap: Partial<ChangeProposal>) => {
    const merge = (rows: ChangeProposal[]) => rows.map((r) => (r.id === id ? { ...r, ...snap } : r));
    setOpenRows(merge);
    setDecided((d) => ({ ...d, rows: merge(d.rows) }));
  }, []);

  const findRow = (id: string) =>
    openRows.find((r) => r.id === id) || decided.rows.find((r) => r.id === id) || extraRows[id];

  /** The full rows of each card's conflicting suggestions, once loaded. */
  const partnersById = useMemo(() => {
    const byId = new Map<string, ChangeProposal>();
    [...Object.values(extraRows), ...decided.rows, ...openRows].forEach((r) => byId.set(r.id, r));
    const out: Record<string, ChangeProposal[]> = {};
    openRows.forEach((p) => {
      const list = (p.conflicts_with || []).map((c) => byId.get(c.id)).filter(Boolean) as ChangeProposal[];
      if ((p.conflicts_with || []).length) out[p.id] = list;
    });
    return out;
  }, [openRows, decided.rows, extraRows]);

  const setNotice = (id: string, notice?: CardNotice) => setNotices((n) => ({ ...n, [id]: notice }));
  const setResult = (id: string, result?: DecisionResult) => setResults((r) => ({ ...r, [id]: result }));
  const stick = (id: string) => setSticky((s) => (s[id] ? s : { ...s, [id]: query.tab }));
  const focusCard = (id: string) => {
    setFocusedId(id);
    setFocusReq((f) => ({ id, n: f.n + 1 }));
  };

  const startBusy = (ids: string[]) => {
    if (ids.some((id) => busyRef.current.has(id))) return false;
    ids.forEach((id) => busyRef.current.add(id));
    setBusy(new Set(busyRef.current));
    return true;
  };
  const endBusy = (ids: string[]) => {
    ids.forEach((id) => busyRef.current.delete(id));
    setBusy(new Set(busyRef.current));
  };

  // ------------------------------------------------------------------ the shared rule

  const readOnlyFor = (p: ChangeProposal) => cardReadOnly[p.id] || readOnlyReason(p, me, pageReadOnly);

  /** Everything `cardActions` needs, from page state. The card computes the same from its props. */
  const stateFor = (p: ChangeProposal): CardState => {
    const choice = choices[p.id];
    const partners = partnersById[p.id] || [];
    return {
      readOnly: readOnlyFor(p),
      expired: p.status === 'proposed' && Date.parse(p.expires_at) <= Date.now(),
      busy: busyRef.current.has(p.id),
      decided: Boolean(results[p.id]),
      editing: editingId === p.id,
      acknowledged: acks[p.id] === p.seen_version,
      conflictChoice: choice && choice.seen === p.seen_version ? choice.choice : null,
      partnersShown: (p.conflicts_with || []).every((c) => partners.some((r) => r.id === c.id)),
      sourceChecked: sourceChecks[p.id] === p.seen_version,
    };
  };
  const actionsFor = (p: ChangeProposal) => cardActions(p, stateFor(p));

  /** After a decision, move on to the next card in the list. */
  const focusNextAfter = (id: string) => {
    const ids = navigableRef.current;
    const at = ids.indexOf(id);
    const next =
      ids.slice(at + 1).find((x) => x !== id) ||
      ids
        .slice(0, Math.max(at, 0))
        .reverse()
        .find((x) => x !== id);
    if (next) focusCard(next);
  };

  /** Read one proposal again (never a decision). */
  const reread = async (id: string): Promise<ChangeProposal | null> => {
    try {
      const fresh = await reviewApi.get(id);
      updateRow(fresh);
      return fresh;
    } catch {
      return null;
    }
  };

  const handleError = async (p: ChangeProposal, raw: unknown) => {
    const error = asError(raw);
    const outcome = outcomeOf(p, error);
    if (outcome.kind === 'switched_off') {
      await loadSettings();
      return;
    }
    if (outcome.kind === 'page_read_only') {
      setPageReadOnly(outcome.reason);
      setEditingId(null);
      return;
    }
    if (outcome.kind === 'card_read_only') {
      setCardReadOnly((c) => ({ ...c, [p.id]: outcome.reason }));
      setEditingId((id) => (id === p.id ? null : id));
      return;
    }
    if (outcome.snapshot) mergeSnapshot(p.id, outcome.snapshot);
    if (error.code === 'invalid_value') setServerErrors((s) => ({ ...s, [p.id]: fieldErrorsOf(error) }));
    else if (outcome.refresh || outcome.snapshot) {
      // What was being edited is no longer what is on the card: close the form until it is looked at again.
      setEditingId((id) => (id === p.id ? null : id));
    }
    setNotice(p.id, outcome.notice);
    if (outcome.refresh) {
      const fresh = await reread(p.id);
      if (fresh && fresh.status !== 'proposed' && !(p.status === 'rejected' && fresh.status === 'rejected')) {
        const closed = closedResult(fresh, me);
        if (closed && error.code !== 'not_rejected') setResult(p.id, closed);
      }
    }
    focusCard(p.id);
  };

  // ------------------------------------------------------------------ decisions

  const rejectConflicting = async (winner: ChangeProposal): Promise<string> => {
    const lines: string[] = [];
    for (const c of winner.conflicts_with || []) {
      let other: ChangeProposal | undefined = findRow(c.id);
      if (!other || other.status !== 'proposed' || !sameValues(c.patch, other.patch)) {
        other = (await reread(c.id)) || undefined;
      }
      // Reject only what the reviewer saw: the other suggestion's values must be the ones shown.
      if (!other || other.status !== 'proposed' || !sameValues(c.patch, other.patch)) {
        lines.push(
          `The other suggestion by ${c.proposer_username} could not be matched to what was shown and is still open.`,
        );
        if (other)
          setNotice(other.id, {
            tone: 'warning',
            text: 'A suggestion for the same field was accepted. Look at this one again.',
          });
        continue;
      }
      try {
        const rejected = await reviewApi.reject(other.id, other.seen_version, CONFLICT_REJECT_REASON);
        updateRow(rejected);
        stick(other.id);
        setResult(other.id, {
          tone: 'info',
          text: `Rejected: you kept the suggestion by ${winner.proposer_username} for the same field.`,
        });
        lines.push(`The other suggestion by ${c.proposer_username} was rejected.`);
      } catch (e) {
        lines.push(`The other suggestion by ${c.proposer_username} could not be rejected and is still open.`);
        stick(other.id);
        await handleError(other, e);
      }
    }
    return lines.join(' ');
  };

  const accept = async (p: ChangeProposal, edits?: { edits: Record<string, PatchValue>; drop: string[] }) => {
    const allowed = edits ? actionsFor(p).acceptEdits : actionsFor(p).accept;
    if (!allowed.ok) return;
    const keepThis = (p.conflicts_with || []).length > 0 && stateFor(p).conflictChoice === 'this';
    if (!startBusy([p.id])) return;
    stick(p.id);
    setNotice(p.id, undefined);
    try {
      const updated = edits
        ? await reviewApi.acceptWithEdits(p.id, p.seen_version, edits.edits, edits.drop)
        : await reviewApi.accept(p.id, p.seen_version);
      updateRow(updated);
      setEditingId((id) => (id === p.id ? null : id));
      setServerErrors((s) => ({ ...s, [p.id]: {} }));
      let text = acceptedText(updated);
      if (keepThis) text += ` ${await rejectConflicting(p)}`;
      setResult(p.id, { tone: 'success', text });
      setSelected((s) => {
        const next = new Set(s);
        next.delete(p.id);
        return next;
      });
      announceReviewChange();
      focusNextAfter(p.id);
    } catch (e) {
      await handleError(p, e);
    } finally {
      endBusy([p.id]);
    }
  };

  const reject = async (p: ChangeProposal, reason: string, then?: () => void) => {
    if (!actionsFor(p).reject.ok || !startBusy([p.id])) return;
    stick(p.id);
    setNotice(p.id, undefined);
    setDialogBusy(true);
    try {
      const updated = await reviewApi.reject(p.id, p.seen_version, reason);
      updateRow(updated);
      setEditingId((id) => (id === p.id ? null : id));
      setResult(p.id, { tone: 'info', text: rejectedText(reason) });
      setSelected((s) => {
        const next = new Set(s);
        next.delete(p.id);
        return next;
      });
      announceReviewChange();
      setDialog(null);
      if (then) then();
      else focusNextAfter(p.id);
    } catch (e) {
      setDialog(null);
      await handleError(p, e);
    } finally {
      setDialogBusy(false);
      endBusy([p.id]);
    }
  };

  const reopen = async (p: ChangeProposal, note: string) => {
    if (!actionsFor(p).reopen.ok || !startBusy([p.id])) return;
    stick(p.id);
    setNotice(p.id, undefined);
    setDialogBusy(true);
    try {
      const updated = await reviewApi.reopen(p.id, p.seen_version, note);
      updateRow(updated);
      setResult(p.id, { tone: 'success', text: 'Reopened. It is waiting in the Open tab again.' });
      announceReviewChange();
      setDialog(null);
      focusCard(p.id);
    } catch (e) {
      setDialog(null);
      await handleError(p, e);
    } finally {
      setDialogBusy(false);
      endBusy([p.id]);
    }
  };

  /** Rejects exactly the rows the dialog listed. */
  const bulkReject = async (rows: ChangeProposal[], reason: string) => {
    const ids = rows.map((r) => r.id);
    if (!ids.length || ids.length > BULK_REJECT_MAX || !startBusy(ids)) return;
    setDialogBusy(true);
    ids.forEach((id) => {
      stick(id);
      setNotice(id, undefined);
    });
    try {
      const answer = await reviewApi.bulkReject(
        rows.map((r) => ({ id: r.id, seen_version: r.seen_version })),
        reason,
      );
      const rejected = new Set(answer.rejected || []);
      setOpenRows((all) =>
        all.map((r) =>
          rejected.has(r.id)
            ? { ...r, status: 'rejected', decision_note: reason, reviewer_username: me || r.reviewer_username }
            : r,
        ),
      );
      rejected.forEach((id) => setResult(id, { tone: 'info', text: rejectedText(reason) }));
      for (const skip of answer.skipped || []) {
        if (skip.code === 'reviewer_is_party') {
          setCardReadOnly((c) => ({
            ...c,
            [skip.id]: 'You took part in this suggestion, so another person has to decide on it.',
          }));
        } else if (skip.code === 'stale_view') {
          setNotice(skip.id, {
            tone: 'warning',
            text: 'Not rejected: this suggestion changed since it was loaded. Look at it again.',
          });
          await reread(skip.id);
        } else {
          const fresh = await reread(skip.id);
          const closed = fresh ? closedResult(fresh, me) : null;
          if (closed) setResult(skip.id, closed);
          else setNotice(skip.id, { tone: 'info', text: `Not rejected (${skip.code}).` });
        }
      }
      (answer.not_found || []).forEach((id) =>
        setNotice(id, { tone: 'error', text: 'Not rejected: this suggestion no longer exists.' }),
      );
      setSelected(new Set());
      setSnack(
        `${rejected.size} rejected${(answer.skipped || []).length ? `, ${answer.skipped.length} not rejected (see the cards)` : ''}.`,
      );
      announceReviewChange();
      setDialog(null);
    } catch (e) {
      setDialog(null);
      const error = asError(e);
      const outcome = outcomeOf(rows[0], error);
      if (outcome.kind === 'switched_off') await loadSettings();
      else if (outcome.kind === 'page_read_only') setPageReadOnly(outcome.reason);
      else {
        setSnack(
          error.noAnswer
            ? 'No answer from the server. The list was read again; check it before deciding.'
            : `Nothing was rejected: ${error.detail}`,
        );
        if (error.noAnswer) await loadOpen(query.sort);
      }
    } finally {
      setDialogBusy(false);
      endBusy(ids);
    }
  };

  /** Keep the other of two conflicting suggestions: reject this one (with a reason), then go to the other. */
  const pickOther = (p: ChangeProposal, other: ProposalConflict) => {
    setDialog({
      type: 'reject',
      proposal: p,
      initial: CONFLICT_REJECT_REASON,
      then: async () => {
        const fresh = await reread(other.id);
        if (fresh && fresh.status === 'proposed') {
          stick(other.id);
          setNotice(other.id, {
            tone: 'info',
            text: 'You chose this suggestion over the other one. Accept it to apply it.',
          });
          focusCard(other.id);
        }
      },
    });
  };

  const toggleSelect = (id: string, checked: boolean) =>
    setSelected((s) => {
      const next = new Set(s);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });

  // One stable set of callbacks for every card; they call the latest page functions.
  const live = useRef({ accept, reject, pickOther, toggleSelect, findRow });
  live.current = { accept, reject, pickOther, toggleSelect, findRow };
  const onArm = useCallback((id: string, value: boolean) => {
    armed.current[id] = value;
  }, []);
  const handlers = useMemo<CardHandlers>(
    () => ({
      onSelect: (id, checked) => live.current.toggleSelect(id, checked),
      onFocusCard: (id) => setFocusedId(id),
      onArm,
      onEdit: (id, value) => setEditingId(value ? id : null),
      onAccept: (p) => live.current.accept(p),
      onAcceptEdits: (p, edits, drop) => live.current.accept(p, { edits, drop }),
      onRequestReject: (p) => setDialog({ type: 'reject', proposal: p }),
      onRequestReopen: (p) => setDialog({ type: 'reopen', proposal: p }),
      onPickOther: (p, other) => live.current.pickOther(p, other),
      onChoose: (p, choice) =>
        setChoices((c) => {
          const next = { ...c };
          if (choice) next[p.id] = { choice, seen: p.seen_version };
          else delete next[p.id];
          return next;
        }),
      onAcknowledge: (p, value) => setAcks((a) => ({ ...a, [p.id]: value ? p.seen_version : '' })),
      onSourceCheck: (p, value) => setSourceChecks((s) => ({ ...s, [p.id]: value ? p.seen_version : '' })),
    }),
    [onArm],
  );

  // ------------------------------------------------------------------ what is shown

  const matchesFilters = (p: ChangeProposal) =>
    (!query.company || p.company_id === query.company) &&
    (!query.kind || p.kind === query.kind) &&
    (!proposer || p.proposer_username.toLowerCase() === proposer.toLowerCase()) &&
    (!query.evidence || p.evidence === query.evidence);

  const inTab = (p: ChangeProposal, tab: ReviewTab) => {
    if (sticky[p.id]) return sticky[p.id] === tab;
    if (p.status !== 'proposed') return false;
    const look = needsAnotherLook(p).length > 0;
    return tab === 'look' ? look : !look;
  };

  const filteredOpen = useMemo(
    () => openRows.filter(matchesFilters),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [openRows, query.company, query.kind, query.evidence, proposer],
  );
  const openCount = filteredOpen.filter((p) => p.status === 'proposed' && !needsAnotherLook(p).length).length;
  const lookCount = filteredOpen.filter((p) => p.status === 'proposed' && needsAnotherLook(p).length > 0).length;

  const shown = useMemo(
    () =>
      query.tab === 'decided'
        ? decided.rows.filter((p) => !query.evidence || p.evidence === query.evidence)
        : sortProposals(
            filteredOpen.filter((p) => inTab(p, query.tab)),
            query.sort,
          ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [query.tab, query.sort, query.evidence, decided.rows, filteredOpen, sticky],
  );
  // Group in display order, then render only the first `renderLimit` cards.
  const order = useMemo(
    () =>
      query.tab === 'decided'
        ? shown
        : groupProposals(shown, query.sort, true).flatMap((g) => g.batches.flatMap((b) => b.proposals)),
    [shown, query.tab, query.sort],
  );
  const windowed = order.slice(0, renderLimit);
  const groups = query.tab === 'decided' ? null : groupProposals(windowed, query.sort, true);
  const navigable = windowed.filter((p) => !results[p.id]).map((p) => p.id);
  const navigableRef = useRef<string[]>(navigable);
  navigableRef.current = navigable;

  // Names and role flags of contacts on the rendered cards only, a few at a time.
  useEffect(() => {
    windowed.forEach((p) => {
      const ids = [p.target_collection === 'contact' ? p.target_id : '', displayValue(p.patch?.related_contact)].filter(
        Boolean,
      );
      ids.forEach((id) => {
        if (requested.current.has(id)) return;
        const queued = lookup(async () => {
          try {
            const c = await reviewApi.getContact(id);
            setContacts((all) => ({
              ...all,
              [id]: {
                name: typeof c?.name === 'string' ? c.name : undefined,
                is_primary: c?.is_primary === true,
                contact_type: typeof c?.contact_type === 'string' ? c.contact_type : undefined,
                receives_invoice_emails: c?.receives_invoice_emails === true,
                receives_payment_emails: c?.receives_payment_emails === true,
              },
            }));
          } catch {
            setContacts((all) => ({ ...all, [id]: {} }));
          }
        });
        if (queued) requested.current.add(id);
      });
      // The other side of a conflict, when it is not among the loaded rows: read it to show its evidence.
      (p.conflicts_with || []).forEach((c) => {
        const key = `p:${c.id}`;
        if (requested.current.has(key) || openRows.some((r) => r.id === c.id) || extraRows[c.id]) return;
        const queued = lookup(async () => {
          try {
            const row = await reviewApi.get(c.id);
            setExtraRows((x) => ({ ...x, [row.id]: row }));
          } catch {
            // The card keeps saying the evidence is loading, and accepting stays blocked.
          }
        });
        if (queued) requested.current.add(key);
      });
    });
  }, [windowed, openRows, extraRows, lookup]);

  const companyOptions = useMemo(() => {
    const map = new Map<string, string>();
    [...openRows, ...decided.rows].forEach((p) => map.set(p.company_id, p.company_name));
    if (query.company && !map.has(query.company)) map.set(query.company, 'Selected company');
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [openRows, decided.rows, query.company]);

  const proposerOptions = useMemo(() => {
    const set = new Set<string>();
    [...openRows, ...decided.rows].forEach((p) => p.proposer_username && set.add(p.proposer_username));
    if (proposer) set.add(proposer);
    return Array.from(set).sort();
  }, [openRows, decided.rows, proposer]);

  const filtersActive = Boolean(query.company || query.kind || proposer || query.evidence || query.decided);
  const clearFilters = () => {
    setProposer('');
    setQuery({ company: '', kind: '', evidence: '', decided: '' });
  };

  /** Exactly what a bulk reject would send: selected, shown with the current tab and filters, and decidable. */
  const bulkRows = shown.filter((p) => selected.has(p.id) && actionsFor(p).select.ok);
  const tooMany = bulkRows.length > BULK_REJECT_MAX;

  // ------------------------------------------------------------------ keyboard

  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const keyState = useRef<any>(null);
  keyState.current = { navigable, focusedId, dialog, editingId, order, shortcutsOn, helpAnchor, renderLimit };
  const keyFns = useRef<any>(null);
  keyFns.current = { actionsFor, stateFor, accept, toggleSelect };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const s = keyState.current;
      const f = keyFns.current;
      if (!s.shortcutsOn || s.dialog || s.helpAnchor || event.metaKey || event.ctrlKey || event.altKey) return;
      // While a card is being edited, every shortcut waits until the form is saved or closed.
      if (s.editingId) return;
      if (isTypingTarget(event.target as Element) || isTypingTarget(document.activeElement)) return;
      const ids: string[] = s.navigable;
      const index = s.focusedId ? ids.indexOf(s.focusedId) : -1;
      const current: ChangeProposal | undefined = s.order.find((p: ChangeProposal) => p.id === s.focusedId);
      // Card shortcuts act only on the card that really has focus.
      const focusInCard =
        current && document.activeElement instanceof HTMLElement
          ? document.activeElement.closest('[data-proposal-id]')?.getAttribute('data-proposal-id') === current.id
          : false;
      switch (event.key) {
        case 'j': {
          if (index + 1 >= ids.length && s.order.length > s.renderLimit) setRenderLimit((n: number) => n + RENDER_STEP);
          const next = ids[Math.min(ids.length - 1, index + 1)];
          if (next) focusCard(next);
          break;
        }
        case 'k':
          if (ids.length) focusCard(ids[Math.max(0, index - 1)]);
          break;
        case 'e':
          if (current && focusInCard && f.actionsFor(current).edit.ok) setEditingId(current.id);
          else if (current && focusInCard) setSnack(f.actionsFor(current).edit.reason || 'Not possible now.');
          break;
        case 'r':
          if (current && focusInCard && f.actionsFor(current).reject.ok)
            setDialog({ type: 'reject', proposal: current });
          break;
        case 'x':
          if (current && focusInCard && f.actionsFor(current).select.ok)
            f.toggleSelect(current.id, !selectedRef.current.has(current.id));
          break;
        case 'a': {
          if (!current || !focusInCard) break;
          const allowed = f.actionsFor(current).accept;
          if (!allowed.ok) setSnack(allowed.reason || 'Not possible now.');
          else if (!armed.current[current.id])
            setSnack('Read the card first: the A key accepts once the card has been in focus for a moment.');
          else f.accept(current);
          break;
        }
        case '?':
          setHelpAnchor(document.getElementById('review-help-button'));
          break;
        default:
          return;
      }
      event.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const toggleShortcuts = (on: boolean) => {
    setShortcutsOn(on);
    try {
      localStorage.setItem(SHORTCUTS_KEY, on ? 'on' : 'off');
    } catch {
      // Storage unavailable: the choice lasts until the page is left.
    }
  };

  // ------------------------------------------------------------------ states

  if (settingsLoad === 'loading') {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }} aria-busy="true">
        <CircularProgress aria-label="Loading" />
      </Box>
    );
  }

  const header = (actions?: React.ReactNode) => (
    <PageHeader
      breadcrumbs={[{ label: 'Today', to: '/today' }, { label: 'Review' }]}
      title="Review"
      subtitle="Changes suggested from email, chat, calls and agent conversations. Nothing changes in the CRM until a person accepts it."
      actions={actions}
    />
  );

  if (settingsLoad === 'error') {
    return (
      <Box>
        {header()}
        <Alert severity="error" action={<Button onClick={loadSettings}>Try again</Button>}>
          The review settings could not be read. Check your connection and try again.
        </Alert>
      </Box>
    );
  }

  if (!enabled) {
    return (
      <Box data-testid="review-off">
        {header()}
        <Paper variant="outlined">
          <EmptyState
            icon={<ToggleOffOutlined />}
            title="Suggestions are not switched on yet"
            description="Once they are, changes that agents and jobs suggest from email, chat and calls will wait here for a person to accept or reject them."
          />
        </Paper>
      </Box>
    );
  }

  const help = (
    <Popover
      open={Boolean(helpAnchor)}
      anchorEl={helpAnchor}
      onClose={() => setHelpAnchor(null)}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <Box sx={{ p: 2, maxWidth: 380 }} data-testid="review-help">
        <Typography variant="subtitle2" gutterBottom>
          How review works
        </Typography>
        <Typography variant="body2" component="div" sx={{ '& li': { mb: 0.5 } }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>
              Each change is accepted on its own card, after you have looked at it. There is deliberately no “accept
              all”.
            </li>
            <li>
              You can reject several at once: tick them (or a whole batch) and give one reason. The dialog lists what
              will be rejected.
            </li>
            <li>
              If a suggestion changed since you loaded it, nothing happens and the card shows what changed. Decide again
              with a fresh click.
            </li>
            <li>Accepting applies the change as you, and it is recorded in the record’s history.</li>
          </ul>
        </Typography>
        <Typography variant="subtitle2" sx={{ mt: 1.5 }} gutterBottom>
          Keys (when switched on, and never while typing or editing)
        </Typography>
        <Box
          component="dl"
          sx={{
            m: 0,
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            columnGap: 1.5,
            rowGap: 0.5,
            fontSize: '0.875rem',
          }}
        >
          {[
            ['j / k', 'next / previous card'],
            ['a', 'accept the card in focus, once it has been in focus for a moment'],
            ['e', 'edit, then accept'],
            ['r', 'reject with a reason'],
            ['x', 'select for rejecting together'],
            ['?', 'this help'],
          ].map(([k, v]) => (
            <React.Fragment key={k}>
              <Box component="dt" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {k}
              </Box>
              <Box component="dd" sx={{ m: 0 }}>
                {v}
              </Box>
            </React.Fragment>
          ))}
        </Box>
      </Box>
    </Popover>
  );

  const actions = (
    <>
      <FormControlLabel
        control={<Switch size="small" checked={shortcutsOn} onChange={(e) => toggleShortcuts(e.target.checked)} />}
        label={<Typography variant="body2">Keyboard shortcuts</Typography>}
        sx={{ mr: 0.5 }}
      />
      <Button
        variant="outlined"
        startIcon={<Refresh />}
        onClick={() => {
          setResults({});
          setNotices({});
          setSticky({});
          setServerErrors({});
          setEditingId(null);
          resetView();
          loadOpen(query.sort);
          if (query.tab === 'decided') loadDecided(1);
        }}
        disabled={busy.size > 0}
      >
        Refresh
      </Button>
      <Tooltip title="How review works, and keys">
        <IconButton
          id="review-help-button"
          aria-label="How review works"
          onClick={(e) => setHelpAnchor(e.currentTarget)}
          sx={{ border: 1, borderColor: 'divider' }}
        >
          <HelpOutline fontSize="small" />
        </IconButton>
      </Tooltip>
    </>
  );

  const renderCard = (p: ChangeProposal) => {
    const s = stateFor(p);
    return (
      <ProposalCard
        key={p.id}
        proposal={p}
        settings={settings}
        valuesFollowTarget={valuesFollowTarget}
        busy={busy.has(p.id)}
        notice={notices[p.id]}
        result={results[p.id]}
        readOnly={s.readOnly}
        contact={p.target_collection === 'contact' ? contacts[p.target_id] : undefined}
        relatedName={contacts[displayValue(p.patch?.related_contact)]?.name}
        partners={partnersById[p.id]}
        selected={selected.has(p.id)}
        focused={focusedId === p.id}
        focusNonce={focusReq.id === p.id ? focusReq.n : 0}
        editing={s.editing}
        serverErrors={serverErrors[p.id]}
        acknowledged={s.acknowledged}
        conflictChoice={s.conflictChoice}
        sourceChecked={s.sourceChecked}
        handlers={handlers}
      />
    );
  };

  const emptyFor = (tab: ReviewTab) => {
    if (filtersActive) {
      return (
        <EmptyState
          icon={<ManageSearchOutlined />}
          title="Nothing matches these filters"
          action={<Button onClick={clearFilters}>Clear filters</Button>}
        />
      );
    }
    if (tab === 'open') {
      return (
        <EmptyState
          icon={<TaskAltOutlined />}
          title="Nothing waiting for review"
          description={
            lookCount
              ? 'Some suggestions need another look; see the next tab.'
              : 'New suggestions appear here as agents and jobs make them.'
          }
        />
      );
    }
    if (tab === 'look') {
      return (
        <EmptyState
          icon={<FactCheckOutlined />}
          title="Nothing needs another look"
          description="Suggestions land here when their record changed, another suggestion conflicts with them, or applying them failed."
        />
      );
    }
    return (
      <EmptyState
        icon={<InboxOutlined />}
        title="No decided suggestions yet"
        description="Accepted, rejected and expired suggestions are listed here with who decided and when."
      />
    );
  };

  const listLoad = query.tab === 'decided' ? decided.load : openLoad;
  const notLoaded = openTotal - openRows.length;

  return (
    <Box>
      {header(actions)}
      {help}

      {pageReadOnly && (
        <Alert severity="info" sx={{ mb: 2 }} data-testid="page-read-only">
          You can look at suggestions but not decide on them: <PlainText value={pageReadOnly} />
        </Alert>
      )}

      {query.tab !== 'decided' && openLoad === 'ready' && notLoaded > 0 && (
        <Alert
          severity="warning"
          sx={{ mb: 2 }}
          data-testid="more-not-loaded"
          action={
            <Button color="inherit" onClick={loadMoreOpen} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : `Load ${Math.min(OPEN_PAGE_SIZE, notLoaded)} more`}
            </Button>
          }
        >
          Showing the {query.sort === 'expiring' ? 'soonest-expiring' : 'newest'}{' '}
          {openRows.length.toLocaleString('en-US')} of {openTotal.toLocaleString('en-US')} open suggestions. The counts
          below are for the loaded ones.
        </Alert>
      )}

      <Paper variant="outlined" sx={{ mb: 2 }}>
        <Tabs
          value={query.tab}
          onChange={(_, tab: ReviewTab) => {
            // Decided cards stay where they were decided only until the list changes.
            setSticky({});
            setResults({});
            setEditingId(null);
            setQuery({ tab, decided: tab === 'decided' ? query.decided : '' });
          }}
          variant="scrollable"
          allowScrollButtonsMobile
          aria-label="Review lists"
          sx={{ px: 1, borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab value="open" label={<TabLabel text="Open" count={openLoad === 'ready' ? openCount : undefined} />} />
          <Tab
            value="look"
            label={
              <TabLabel text="Needs another look" count={openLoad === 'ready' ? lookCount : undefined} tone="warning" />
            }
          />
          <Tab value="decided" label="Decided" />
        </Tabs>
        <Box
          sx={{
            p: 1.5,
            display: 'grid',
            gap: 1.5,
            gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(6, minmax(0, 1fr))' },
          }}
        >
          <FilterSelect
            label="Company"
            value={query.company}
            onChange={(company) => setQuery({ company })}
            options={companyOptions}
          />
          <FilterSelect
            label="Type"
            value={query.kind}
            onChange={(kind) => setQuery({ kind })}
            options={['field_update', 'note', 'new_contact', 'task'].map((k) => [k, KIND_LABEL[k]])}
          />
          <FilterSelect
            label="Suggested by"
            value={proposer}
            onChange={(value) => {
              resetView();
              setProposer(value);
            }}
            options={proposerOptions.map((p) => [p, p])}
          />
          <FilterSelect
            label="Evidence"
            value={query.evidence}
            onChange={(evidence) => setQuery({ evidence })}
            options={Object.entries(EVIDENCE_LABEL)}
          />
          {query.tab === 'decided' ? (
            <FilterSelect
              label="Outcome"
              value={query.decided}
              onChange={(value) => setQuery({ decided: value })}
              options={DECIDED_STATUSES.map((s) => [s, STATUS_LABEL[s]])}
            />
          ) : (
            <FilterSelect
              label="Order"
              value={query.sort}
              allowEmpty={false}
              onChange={(value) => setQuery({ sort: value === 'expiring' ? 'expiring' : 'newest' })}
              options={[
                ['newest', 'Newest evidence first'],
                ['expiring', 'Expiring soonest first'],
              ]}
            />
          )}
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {filtersActive && (
              <Button size="small" onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </Box>
        </Box>
      </Paper>

      {query.tab !== 'decided' && bulkRows.length > 0 && (
        <Paper
          variant="outlined"
          sx={{
            mb: 2,
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            flexWrap: 'wrap',
            position: 'sticky',
            top: 64,
            zIndex: 2,
          }}
          data-testid="bulk-bar"
        >
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {bulkRows.length} selected
          </Typography>
          <Button
            color="error"
            variant="contained"
            onClick={() => setDialog({ type: 'bulk', rows: bulkRows })}
            disabled={busy.size > 0 || tooMany}
          >
            Reject selected…
          </Button>
          <Button onClick={() => setSelected(new Set())}>Clear selection</Button>
          <Typography variant="caption" color={tooMany ? 'error' : 'text.secondary'} data-testid="bulk-note">
            {tooMany
              ? `At most ${BULK_REJECT_MAX} can be rejected at once; the server refuses more. Clear some first.`
              : 'Accepting is always one card at a time.'}
          </Typography>
        </Paper>
      )}

      {listLoad === 'error' && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button onClick={() => (query.tab === 'decided' ? loadDecided(1) : loadOpen(query.sort))}>Try again</Button>
          }
        >
          The suggestions could not be loaded. Check your connection and try again.
        </Alert>
      )}

      {listLoad === 'loading' && shown.length === 0 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }} aria-busy="true">
          <CircularProgress aria-label="Loading suggestions" />
        </Box>
      )}

      {listLoad !== 'error' && !(listLoad === 'loading' && shown.length === 0) && shown.length === 0 && (
        <Paper variant="outlined">{emptyFor(query.tab)}</Paper>
      )}

      {groups &&
        groups.map((group) => (
          <Box component="section" key={group.companyId} sx={{ mb: 3 }} aria-label={group.companyName}>
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, mb: 1, flexWrap: 'wrap' }}>
              <Typography variant="h6" component="h2" sx={{ minWidth: 0 }}>
                <PlainText value={group.companyName} />
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {group.count} {group.count === 1 ? 'suggestion' : 'suggestions'}
              </Typography>
              <Link
                href={`/companies/${group.companyId}`}
                target="_blank"
                rel="noopener noreferrer"
                underline="hover"
                variant="body2"
                sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.25 }}
              >
                Open company <OpenInNew sx={{ fontSize: 14 }} />
              </Link>
            </Box>
            <Box sx={{ display: 'grid', gap: 1.5 }}>
              {group.batches.map((batch) => {
                const batchDecidable = batch.proposals.filter((p) => actionsFor(p).select.ok);
                const allSelected = batchDecidable.length > 0 && batchDecidable.every((p) => selected.has(p.id));
                if (!batch.batchKey || batch.proposals.length === 1) {
                  return <React.Fragment key={batch.key}>{batch.proposals.map(renderCard)}</React.Fragment>;
                }
                return (
                  <Box
                    key={batch.key}
                    sx={{ borderLeft: 3, borderColor: 'divider', pl: { xs: 1, sm: 1.5 }, display: 'grid', gap: 1.5 }}
                    data-testid="batch-group"
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Typography variant="caption" color="text.secondary">
                        {batch.proposals.length} suggestions from one source · batch{' '}
                        <PlainText value={batch.batchKey} sx={{ fontFamily: 'monospace' }} />
                      </Typography>
                      {batchDecidable.length > 1 && (
                        <FormControlLabel
                          sx={{ ml: 0 }}
                          control={
                            <Checkbox
                              size="small"
                              checked={allSelected}
                              indeterminate={!allSelected && batchDecidable.some((p) => selected.has(p.id))}
                              onChange={(e) =>
                                setSelected((s) => {
                                  const next = new Set(s);
                                  batchDecidable.forEach((p) =>
                                    e.target.checked ? next.add(p.id) : next.delete(p.id),
                                  );
                                  return next;
                                })
                              }
                            />
                          }
                          label={<Typography variant="caption">Select the batch to reject it</Typography>}
                        />
                      )}
                    </Box>
                    {batch.proposals.map(renderCard)}
                  </Box>
                );
              })}
            </Box>
          </Box>
        ))}

      {groups && order.length > windowed.length && (
        <Box sx={{ textAlign: 'center', mb: 2 }}>
          <Button
            variant="outlined"
            onClick={() => setRenderLimit((n) => n + RENDER_STEP)}
            data-testid="show-more-cards"
          >
            Show {Math.min(RENDER_STEP, order.length - windowed.length)} more of {order.length.toLocaleString('en-US')}{' '}
            here
          </Button>
        </Box>
      )}

      {query.tab === 'decided' && (shown.length > 0 || decided.rows.length > 0) && (
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          {query.evidence && (
            <Typography variant="body2" color="text.secondary" data-testid="decided-count">
              {shown.length} of the {decided.rows.length} loaded match the evidence filter (
              {decided.count.toLocaleString('en-US')} decided in all; the evidence filter applies to loaded rows only).
            </Typography>
          )}
          {windowed.map(renderCard)}
          {(decided.rows.length < decided.count || order.length > windowed.length) && (
            <Box sx={{ textAlign: 'center', mt: 1 }}>
              <Button
                onClick={() => {
                  if (order.length > windowed.length) setRenderLimit((n) => n + RENDER_STEP);
                  else loadDecided(decided.page + 1);
                }}
                disabled={decided.load === 'loading'}
              >
                {decided.load === 'loading'
                  ? 'Loading…'
                  : order.length > windowed.length
                    ? `Show ${Math.min(RENDER_STEP, order.length - windowed.length)} more`
                    : `Load ${Math.min(DECIDED_PAGE, decided.count - decided.rows.length)} more (${(decided.count - decided.rows.length).toLocaleString('en-US')} not loaded)`}
              </Button>
            </Box>
          )}
        </Box>
      )}

      <ReasonDialog
        open={dialog?.type === 'reject'}
        title="Reject this suggestion"
        intro={
          dialog?.type === 'reject' ? (
            <>
              Nothing changes in the CRM. An agent will not raise the same change again. (
              <PlainText value={summary(dialog.proposal)} />)
            </>
          ) : undefined
        }
        label="Reason"
        confirmLabel="Reject"
        confirmColor="error"
        quickPicks={REJECT_REASONS}
        initialText={dialog?.type === 'reject' ? dialog.initial : undefined}
        busy={dialogBusy}
        onClose={() => setDialog(null)}
        onConfirm={(reason) => dialog?.type === 'reject' && reject(dialog.proposal, reason, dialog.then)}
      />
      <ReasonDialog
        open={dialog?.type === 'bulk'}
        title={`Reject ${dialog?.type === 'bulk' ? dialog.rows.length : 0} suggestions`}
        intro={
          dialog?.type === 'bulk' ? (
            <Box data-testid="bulk-list">
              These get the same reason. Any that changed since you loaded them are left open and marked.
              <Box component="ul" sx={{ m: 0, mt: 1, pl: 2.5 }}>
                {dialog.rows.slice(0, BULK_LIST_MAX).map((r) => (
                  <li key={r.id}>
                    <PlainText value={summary(r)} />
                  </li>
                ))}
              </Box>
              {dialog.rows.length > BULK_LIST_MAX && (
                <Box sx={{ mt: 0.5 }}>and {dialog.rows.length - BULK_LIST_MAX} more</Box>
              )}
            </Box>
          ) : undefined
        }
        label="Reason"
        confirmLabel={`Reject ${dialog?.type === 'bulk' ? dialog.rows.length : 0}`}
        confirmColor="error"
        quickPicks={REJECT_REASONS}
        busy={dialogBusy}
        onClose={() => setDialog(null)}
        onConfirm={(reason) => dialog?.type === 'bulk' && bulkReject(dialog.rows, reason)}
      />
      <ReasonDialog
        open={dialog?.type === 'reopen'}
        title="Reopen this suggestion"
        intro="It goes back to the Open tab for a new decision. Say why, for the history."
        label="Note"
        confirmLabel="Reopen"
        busy={dialogBusy}
        onClose={() => setDialog(null)}
        onConfirm={(note) => dialog?.type === 'reopen' && reopen(dialog.proposal, note)}
      />
      <Snackbar open={Boolean(snack)} autoHideDuration={5000} onClose={() => setSnack(null)} message={snack || ''} />
    </Box>
  );
};

const TabLabel: React.FC<{ text: string; count?: number; tone?: 'warning' }> = ({ text, count, tone }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
    {text}
    {typeof count === 'number' && (
      <Badge
        badgeContent={count}
        showZero
        max={999}
        color={tone === 'warning' && count > 0 ? 'warning' : 'default'}
        sx={{ '& .MuiBadge-badge': { position: 'static', transform: 'none' } }}
      />
    )}
  </Box>
);

const FilterSelect: React.FC<{
  label: string;
  value: string;
  options: [string, string][] | string[][];
  allowEmpty?: boolean;
  onChange: (value: string) => void;
}> = ({ label, value, options, allowEmpty = true, onChange }) => (
  <TextField select size="small" label={label} value={value} onChange={(e) => onChange(e.target.value)} fullWidth>
    {allowEmpty && (
      <MenuItem value="">
        <em>All</em>
      </MenuItem>
    )}
    {options.map(([v, text]) => (
      <MenuItem key={v} value={v}>
        {text}
      </MenuItem>
    ))}
  </TextField>
);

export default ReviewQueue;
