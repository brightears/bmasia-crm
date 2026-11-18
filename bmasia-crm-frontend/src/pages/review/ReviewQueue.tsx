import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
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
  PatchValue,
  ProposalConflict,
  ReviewApiError,
  ReviewSettings,
} from '../../services/reviewApi';
import { EmptyState, PageHeader } from '../../components/ui';
import ProposalCard, { CardNotice, ConflictChoice, ContactInfo, DecisionResult } from './ProposalCard';
import ReasonDialog from './ReasonDialog';
import PlainText from './PlainText';
import {
  CONFLICT_REJECT_REASON,
  DECIDED_STATUSES,
  EVIDENCE_LABEL,
  KIND_LABEL,
  REJECT_REASONS,
  ReviewQuery,
  ReviewTab,
  STATUS_LABEL,
  displayValue,
  groupProposals,
  needsAnotherLook,
  readOnlyReason,
  readQuery,
  writeQuery,
} from './reviewModel';
import { acceptedText, closedResult, fieldErrorsOf, outcomeOf, rejectedText } from './decisionText';
import { announceReviewChange } from './useReviewStatus';

type Load = 'loading' | 'ready' | 'error';
type DialogState =
  | { type: 'reject'; proposal: ChangeProposal; initial?: string; then?: () => void }
  | { type: 'bulk' }
  | { type: 'reopen'; proposal: ChangeProposal }
  | null;

const DECIDED_PAGE = 25;
const asError = (e: unknown): ReviewApiError =>
  e instanceof ReviewApiError ? e : new ReviewApiError(undefined, 'no_answer', 'No answer from the server.');

const sameValues = (a: Record<string, PatchValue>, b: Record<string, PatchValue> | undefined) =>
  Object.keys(a).every((k) => displayValue(a[k]) === displayValue(b?.[k]));

/**
 * The Review page: a person works through what agents and jobs suggest, one decision at a time.
 * Every decision is bound to the version that was shown; a refused one is explained and never retried.
 */
const ReviewQueue: React.FC = () => {
  const { user } = useAuth();
  const [search, setSearch] = useSearchParams();
  const query = readQuery(search);

  const [settings, setSettings] = useState<ReviewSettings | null>(null);
  const [settingsLoad, setSettingsLoad] = useState<Load>('loading');
  const [openRows, setOpenRows] = useState<ChangeProposal[]>([]);
  const [openLoad, setOpenLoad] = useState<Load>('loading');
  const [truncated, setTruncated] = useState(false);
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
  const requestedContacts = useRef<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, Record<string, string>>>({});
  const [acks, setAcks] = useState<Record<string, string>>({});
  const armed = useRef<Record<string, boolean>>({});
  const [dialog, setDialog] = useState<DialogState>(null);
  const [dialogBusy, setDialogBusy] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);
  const [helpAnchor, setHelpAnchor] = useState<HTMLElement | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const setQuery = (patch: Partial<ReviewQuery>) => setSearch(writeQuery({ ...query, ...patch }), { replace: false });

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

  const loadOpen = useCallback(async () => {
    setOpenLoad('loading');
    try {
      const { rows, truncated: more } = await reviewApi.listAllOpen({});
      setOpenRows(rows);
      setTruncated(more);
      setOpenLoad('ready');
    } catch {
      setOpenLoad('error');
    }
  }, []);

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
          proposer: query.proposer || undefined,
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
    [query.decided, query.company, query.kind, query.proposer],
  );

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (enabled) loadOpen();
  }, [enabled, loadOpen]);

  useEffect(() => {
    if (enabled && query.tab === 'decided') loadDecided(1);
  }, [enabled, query.tab, loadDecided]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  // Names and role flags of target contacts and linked contacts.
  useEffect(() => {
    const ids = new Set<string>();
    [...openRows, ...decided.rows].forEach((p) => {
      if (p.target_collection === 'contact' && p.target_id) ids.add(p.target_id);
      const related = displayValue(p.patch?.related_contact);
      if (related) ids.add(related);
    });
    ids.forEach((id) => {
      if (requestedContacts.current.has(id)) return;
      requestedContacts.current.add(id);
      reviewApi
        .getContact(id)
        .then((c) =>
          setContacts((all) => ({
            ...all,
            [id]: {
              name: typeof c?.name === 'string' ? c.name : undefined,
              is_primary: c?.is_primary === true,
              contact_type: typeof c?.contact_type === 'string' ? c.contact_type : undefined,
              receives_invoice_emails: c?.receives_invoice_emails === true,
              receives_payment_emails: c?.receives_payment_emails === true,
            },
          })),
        )
        .catch(() => setContacts((all) => ({ ...all, [id]: {} })));
    });
  }, [openRows, decided.rows]);

  const contactNames = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(contacts)
          .filter(([, c]) => c.name)
          .map(([id, c]) => [id, c.name as string]),
      ),
    [contacts],
  );

  // ------------------------------------------------------------------ row bookkeeping

  const updateRow = useCallback((fresh: ChangeProposal) => {
    const merge = (rows: ChangeProposal[]) => rows.map((r) => (r.id === fresh.id ? fresh : r));
    setOpenRows((rows) =>
      rows.some((r) => r.id === fresh.id) ? merge(rows) : fresh.status === 'proposed' ? [fresh, ...rows] : rows,
    );
    setDecided((d) => ({ ...d, rows: merge(d.rows) }));
  }, []);

  const mergeSnapshot = useCallback((id: string, snap: Partial<ChangeProposal>) => {
    const merge = (rows: ChangeProposal[]) => rows.map((r) => (r.id === id ? { ...r, ...snap } : r));
    setOpenRows(merge);
    setDecided((d) => ({ ...d, rows: merge(d.rows) }));
  }, []);

  const findRow = (id: string) => openRows.find((r) => r.id === id) || decided.rows.find((r) => r.id === id);

  const setNotice = (id: string, notice?: CardNotice) => setNotices((n) => ({ ...n, [id]: notice }));
  const setResult = (id: string, result?: DecisionResult) => setResults((r) => ({ ...r, [id]: result }));
  const stick = (id: string) => setSticky((s) => (s[id] ? s : { ...s, [id]: query.tab }));

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

  /** Read one proposal again (never a decision). Shows its closed state when it was decided elsewhere. */
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
      return;
    }
    if (outcome.kind === 'card_read_only') {
      setCardReadOnly((c) => ({ ...c, [p.id]: outcome.reason }));
      return;
    }
    if (outcome.snapshot) mergeSnapshot(p.id, outcome.snapshot);
    if (error.code === 'invalid_value') setServerErrors((s) => ({ ...s, [p.id]: fieldErrorsOf(error) }));
    setNotice(p.id, outcome.notice);
    if (outcome.refresh) {
      const fresh = await reread(p.id);
      if (fresh && fresh.status !== 'proposed' && !(p.status === 'rejected' && fresh.status === 'rejected')) {
        const closed = closedResult(fresh);
        if (closed && error.code !== 'not_rejected') setResult(p.id, closed);
      }
    }
  };

  // ------------------------------------------------------------------ decisions

  const rejectConflicting = async (winner: ChangeProposal): Promise<string> => {
    const lines: string[] = [];
    for (const c of winner.conflicts_with || []) {
      let other = findRow(c.id);
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

  const accept = async (
    p: ChangeProposal,
    choice?: ConflictChoice,
    edits?: { edits: Record<string, PatchValue>; drop: string[] },
  ) => {
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
      if (choice === 'this' && (p.conflicts_with || []).length) text += ` ${await rejectConflicting(p)}`;
      setResult(p.id, { tone: 'success', text });
      setSelected((s) => {
        const next = new Set(s);
        next.delete(p.id);
        return next;
      });
      announceReviewChange();
    } catch (e) {
      await handleError(p, e);
    } finally {
      endBusy([p.id]);
    }
  };

  const reject = async (p: ChangeProposal, reason: string, then?: () => void) => {
    if (!startBusy([p.id])) return;
    stick(p.id);
    setNotice(p.id, undefined);
    setDialogBusy(true);
    try {
      const updated = await reviewApi.reject(p.id, p.seen_version, reason);
      updateRow(updated);
      setResult(p.id, { tone: 'info', text: rejectedText(reason) });
      setSelected((s) => {
        const next = new Set(s);
        next.delete(p.id);
        return next;
      });
      announceReviewChange();
      setDialog(null);
      if (then) then();
    } catch (e) {
      setDialog(null);
      await handleError(p, e);
    } finally {
      setDialogBusy(false);
      endBusy([p.id]);
    }
  };

  const reopen = async (p: ChangeProposal, note: string) => {
    if (!startBusy([p.id])) return;
    stick(p.id);
    setNotice(p.id, undefined);
    setDialogBusy(true);
    try {
      const updated = await reviewApi.reopen(p.id, p.seen_version, note);
      updateRow(updated);
      setResult(p.id, { tone: 'success', text: 'Reopened. It is waiting in the Open tab again.' });
      announceReviewChange();
      setDialog(null);
    } catch (e) {
      setDialog(null);
      await handleError(p, e);
    } finally {
      setDialogBusy(false);
      endBusy([p.id]);
    }
  };

  const bulkReject = async (reason: string) => {
    const rows = openRows.filter((r) => selected.has(r.id) && r.status === 'proposed');
    const ids = rows.map((r) => r.id);
    if (!ids.length || !startBusy(ids)) return;
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
            ? {
                ...r,
                status: 'rejected',
                decision_note: reason,
                reviewer_username: user?.username || r.reviewer_username,
              }
            : r,
        ),
      );
      rejected.forEach((id) => setResult(id, { tone: 'info', text: rejectedText(reason) }));
      for (const skip of answer.skipped || []) {
        const row = rows.find((r) => r.id === skip.id);
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
          const closed = fresh ? closedResult(fresh) : null;
          if (closed) setResult(skip.id, closed);
          else if (row) setNotice(row.id, { tone: 'info', text: `Not rejected (${skip.code}).` });
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
        if (error.noAnswer) await loadOpen();
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
          setFocusedId(other.id);
        }
      },
    });
  };

  // ------------------------------------------------------------------ what is shown

  const readOnlyFor = (p: ChangeProposal) => cardReadOnly[p.id] || readOnlyReason(p, user?.username, pageReadOnly);

  const matchesFilters = (p: ChangeProposal) =>
    (!query.company || p.company_id === query.company) &&
    (!query.kind || p.kind === query.kind) &&
    (!query.proposer || p.proposer_username.toLowerCase() === query.proposer.toLowerCase()) &&
    (!query.evidence || p.evidence === query.evidence);

  const inTab = (p: ChangeProposal, tab: ReviewTab) => {
    if (sticky[p.id]) return sticky[p.id] === tab;
    if (p.status !== 'proposed') return false;
    const look = needsAnotherLook(p).length > 0;
    return tab === 'look' ? look : !look;
  };

  const filteredOpen = openRows.filter(matchesFilters);
  const openCount = filteredOpen.filter((p) => p.status === 'proposed' && !needsAnotherLook(p).length).length;
  const lookCount = filteredOpen.filter((p) => p.status === 'proposed' && needsAnotherLook(p).length > 0).length;

  const shown =
    query.tab === 'decided'
      ? decided.rows.filter((p) => !query.evidence || p.evidence === query.evidence)
      : filteredOpen.filter((p) => inTab(p, query.tab));
  const groups = query.tab === 'decided' ? null : groupProposals(shown);
  const order = groups ? groups.flatMap((g) => g.batches.flatMap((b) => b.proposals)) : shown;
  const navigable = order.filter((p) => !results[p.id]).map((p) => p.id);

  const companyOptions = useMemo(() => {
    const map = new Map<string, string>();
    [...openRows, ...decided.rows].forEach((p) => map.set(p.company_id, p.company_name));
    if (query.company && !map.has(query.company)) map.set(query.company, 'Selected company');
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [openRows, decided.rows, query.company]);

  const proposerOptions = useMemo(() => {
    const set = new Set<string>();
    [...openRows, ...decided.rows].forEach((p) => p.proposer_username && set.add(p.proposer_username));
    if (query.proposer) set.add(query.proposer);
    return Array.from(set).sort();
  }, [openRows, decided.rows, query.proposer]);

  const filtersActive = Boolean(query.company || query.kind || query.proposer || query.evidence || query.decided);

  const decidable = (p: ChangeProposal) =>
    p.status === 'proposed' && !readOnlyFor(p) && new Date(p.expires_at).getTime() > now && !results[p.id];

  const toggleSelect = (id: string, checked: boolean) =>
    setSelected((s) => {
      const next = new Set(s);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });

  const onArm = useCallback((id: string, value: boolean) => {
    armed.current[id] = value;
  }, []);

  // ------------------------------------------------------------------ keyboard

  const keyState = useRef({ navigable, focusedId, dialog, order });
  keyState.current = { navigable, focusedId, dialog, order };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const state = keyState.current;
      if (state.dialog || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable ||
          target.closest('[role="dialog"],[role="listbox"],[role="menu"]'))
      ) {
        return;
      }
      const ids = state.navigable;
      const index = state.focusedId ? ids.indexOf(state.focusedId) : -1;
      const current = state.order.find((p) => p.id === state.focusedId);
      switch (event.key) {
        case 'j':
          if (ids.length) setFocusedId(ids[Math.min(ids.length - 1, index + 1)]);
          break;
        case 'k':
          if (ids.length) setFocusedId(ids[Math.max(0, index - 1)]);
          break;
        case 'e':
          if (current && decidable(current) && !(current.conflicts_with || []).length) setEditingId(current.id);
          break;
        case 'r':
          if (current && decidable(current)) setDialog({ type: 'reject', proposal: current });
          break;
        case 'x':
          if (current && decidable(current)) toggleSelect(current.id, !selected.has(current.id));
          break;
        case 'a': {
          if (!current || !decidable(current)) break;
          if ((current.conflicts_with || []).length) {
            setSnack('This one conflicts with another suggestion: pick one on the card.');
          } else if (current.target_changed_at && acks[current.id] !== current.seen_version) {
            setSnack('The record changed: compare the current values and tick the box on the card first.');
          } else if (!armed.current[current.id]) {
            setSnack('Read the card first: the A key accepts once the card has been in focus for a moment.');
          } else {
            accept(current);
          }
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
  });

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
      <Box sx={{ p: 2, maxWidth: 360 }} data-testid="review-help">
        <Typography variant="subtitle2" gutterBottom>
          How review works
        </Typography>
        <Typography variant="body2" component="div" sx={{ '& li': { mb: 0.5 } }}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>
              Each change is accepted on its own card, after you have looked at it. There is deliberately no “accept
              all”.
            </li>
            <li>You can reject several at once: tick them (or a whole batch) and give one reason.</li>
            <li>
              If a suggestion changed since you loaded it, nothing happens and the card shows what changed. Decide again
              with a fresh click.
            </li>
            <li>Accepting applies the change as you, and it is recorded in the record’s history.</li>
          </ul>
        </Typography>
        <Typography variant="subtitle2" sx={{ mt: 1.5 }} gutterBottom>
          Keys
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
      <Tooltip title="Read the list again">
        <span>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => {
              setResults({});
              setNotices({});
              setSticky({});
              setSelected(new Set());
              setServerErrors({});
              loadOpen();
              if (query.tab === 'decided') loadDecided(1);
            }}
            disabled={busy.size > 0}
          >
            Refresh
          </Button>
        </span>
      </Tooltip>
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

  const selectable = filteredOpen.filter((p) => selected.has(p.id) && decidable(p));

  const renderCard = (p: ChangeProposal) => (
    <ProposalCard
      key={p.id}
      proposal={p}
      settings={settings}
      now={now}
      busy={busy.has(p.id)}
      notice={notices[p.id]}
      result={results[p.id]}
      readOnly={readOnlyFor(p)}
      contact={p.target_collection === 'contact' ? contacts[p.target_id] : undefined}
      contactNames={contactNames}
      selected={selected.has(p.id)}
      focused={focusedId === p.id}
      editing={editingId === p.id}
      serverErrors={serverErrors[p.id]}
      onSelect={toggleSelect}
      onFocusCard={setFocusedId}
      onArm={onArm}
      onEdit={(id, value) => setEditingId(value ? id : null)}
      onAccept={(proposal, choice) => accept(proposal, choice)}
      onAcceptEdits={(proposal, edits, drop, choice) => accept(proposal, choice, { edits, drop })}
      onRequestReject={(proposal) => setDialog({ type: 'reject', proposal })}
      onRequestReopen={(proposal) => setDialog({ type: 'reopen', proposal })}
      onPickOther={pickOther}
      acknowledged={acks[p.id] === p.seen_version}
      onAcknowledge={(proposal, value) => setAcks((a) => ({ ...a, [proposal.id]: value ? proposal.seen_version : '' }))}
    />
  );

  const emptyFor = (tab: ReviewTab) => {
    if (filtersActive) {
      return (
        <EmptyState
          icon={<ManageSearchOutlined />}
          title="Nothing matches these filters"
          action={
            <Button onClick={() => setQuery({ company: '', kind: '', proposer: '', evidence: '', decided: '' })}>
              Clear filters
            </Button>
          }
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

  return (
    <Box>
      {header(actions)}
      {help}

      {pageReadOnly && (
        <Alert severity="info" sx={{ mb: 2 }} data-testid="page-read-only">
          You can look at suggestions but not decide on them: <PlainText value={pageReadOnly} />
        </Alert>
      )}

      <Paper variant="outlined" sx={{ mb: 2 }}>
        <Tabs
          value={query.tab}
          onChange={(_, tab: ReviewTab) => {
            // Decided cards stay where they were decided only until the list changes.
            setSelected(new Set());
            setSticky({});
            setResults({});
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
            gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(5, minmax(0, 1fr))' },
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
            value={query.proposer}
            onChange={(proposer) => setQuery({ proposer })}
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
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              {filtersActive && (
                <Button
                  size="small"
                  onClick={() => setQuery({ company: '', kind: '', proposer: '', evidence: '', decided: '' })}
                >
                  Clear filters
                </Button>
              )}
            </Box>
          )}
        </Box>
      </Paper>

      {query.tab !== 'decided' && selectable.length > 0 && (
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
            {selectable.length} selected
          </Typography>
          <Button
            color="error"
            variant="contained"
            onClick={() => setDialog({ type: 'bulk' })}
            disabled={busy.size > 0}
          >
            Reject selected…
          </Button>
          <Button onClick={() => setSelected(new Set())}>Clear selection</Button>
          <Typography variant="caption" color="text.secondary">
            Accepting is always one card at a time.
          </Typography>
        </Paper>
      )}

      {truncated && query.tab !== 'decided' && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Showing the first 1,000 open suggestions. Decide on some, then refresh to see the rest.
        </Alert>
      )}

      {listLoad === 'error' && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={<Button onClick={() => (query.tab === 'decided' ? loadDecided(1) : loadOpen())}>Try again</Button>}
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
                const batchDecidable = batch.proposals.filter(decidable);
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

      {query.tab === 'decided' && shown.length > 0 && (
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          {shown.map(renderCard)}
          {decided.rows.length < decided.count && (
            <Box sx={{ textAlign: 'center', mt: 1 }}>
              <Button onClick={() => loadDecided(decided.page + 1)} disabled={decided.load === 'loading'}>
                {decided.load === 'loading' ? 'Loading…' : `Show more (${decided.count - decided.rows.length} left)`}
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
              {KIND_LABEL[dialog.proposal.kind]}, <PlainText value={dialog.proposal.company_name} />)
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
        title={`Reject ${selectable.length} suggestions`}
        intro="All of them get the same reason. Any that changed since you loaded them are left open and marked."
        label="Reason"
        confirmLabel={`Reject ${selectable.length}`}
        confirmColor="error"
        quickPicks={REJECT_REASONS}
        busy={dialogBusy}
        onClose={() => setDialog(null)}
        onConfirm={bulkReject}
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
      <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 3 }}>
        Press ? for keys. See also{' '}
        <Link component={RouterLink} to="/today">
          Today
        </Link>
        .
      </Typography>
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
  onChange: (value: string) => void;
}> = ({ label, value, options, onChange }) => (
  <TextField select size="small" label={label} value={value} onChange={(e) => onChange(e.target.value)} fullWidth>
    <MenuItem value="">
      <em>All</em>
    </MenuItem>
    {options.map(([v, text]) => (
      <MenuItem key={v} value={v}>
        {text}
      </MenuItem>
    ))}
  </TextField>
);

export default ReviewQueue;
