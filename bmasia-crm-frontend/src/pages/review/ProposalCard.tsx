import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  Link,
  Paper,
  Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  CheckCircleOutline,
  CancelOutlined,
  EditOutlined,
  OpenInNew,
  HistoryOutlined,
  InfoOutlined,
  LockOutlined,
  ReplayOutlined,
} from '@mui/icons-material';
import type { ChangeProposal, PatchValue, ProposalConflict, ReviewSettings } from '../../services/reviewApi';
import ChangePreview, { Empty, TextChecks } from './ChangePreview';
import EditForm from './EditForm';
import EvidenceBlock from './EvidenceBlock';
import PlainText from './PlainText';
import {
  PROPOSER_KIND_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  cardActions,
  displayValue,
  editableFields,
  fieldLabel,
  formatDateTime,
  kindLabel,
  needsSourceCheck,
} from './reviewModel';
import { formatDate } from '../../theme';

export interface ContactInfo {
  name?: string;
  is_primary?: boolean;
  contact_type?: string;
  receives_invoice_emails?: boolean;
  receives_payment_emails?: boolean;
}

export interface CardNotice {
  tone: 'info' | 'warning' | 'error';
  text: string;
  details?: string[];
}

export interface DecisionResult {
  tone: 'success' | 'info' | 'warning' | 'error';
  text: string;
}

export type ConflictChoice = 'this' | 'other';

/** One stable object of callbacks for every card, so a memoised card re-renders only when its own data changes. */
export interface CardHandlers {
  onSelect: (id: string, checked: boolean) => void;
  onFocusCard: (id: string) => void;
  onArm: (id: string, armed: boolean) => void;
  onEdit: (id: string, editing: boolean) => void;
  onAccept: (p: ChangeProposal) => void;
  onAcceptEdits: (p: ChangeProposal, edits: Record<string, PatchValue>, drop: string[]) => void;
  onRequestReject: (p: ChangeProposal) => void;
  onRequestReopen: (p: ChangeProposal) => void;
  onPickOther: (p: ChangeProposal, other: ProposalConflict) => void;
  onChoose: (p: ChangeProposal, choice: ConflictChoice | null) => void;
  onAcknowledge: (p: ChangeProposal, value: boolean) => void;
  onSourceCheck: (p: ChangeProposal, value: boolean) => void;
}

interface ProposalCardProps {
  proposal: ChangeProposal;
  settings: ReviewSettings | null;
  /** The backend re-reads current values whenever the record changes (PR 67). */
  valuesFollowTarget: boolean;
  busy: boolean;
  notice?: CardNotice;
  result?: DecisionResult;
  readOnly: string | null;
  contact?: ContactInfo;
  relatedName?: string;
  /** The conflicting suggestions, once their full rows are loaded. */
  partners?: ChangeProposal[];
  selected: boolean;
  focused: boolean;
  /** Changes when the page asks this card to take focus (after a decision or a refresh). */
  focusNonce: number;
  editing: boolean;
  serverErrors?: Record<string, string>;
  acknowledged: boolean;
  conflictChoice: ConflictChoice | null;
  sourceChecked: boolean;
  handlers: CardHandlers;
}

/** Time a card must stay focused and on screen before the "a" key accepts it. */
export const ARM_DELAY_MS = 1500;

export const recordLink = (p: ChangeProposal): { href: string; label: string } => {
  if (p.kind === 'task' && p.applied_record_id) return { href: `/tasks/${p.applied_record_id}`, label: 'Open task' };
  if (p.target_collection === 'contact' || p.kind === 'new_contact') {
    return { href: `/companies/${p.company_id}`, label: 'Open company contacts' };
  }
  return { href: `/companies/${p.company_id}`, label: 'Open company' };
};

const NewTabLink: React.FC<{ href: string; children: React.ReactNode }> = ({ href, children }) => (
  <Link
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    underline="hover"
    variant="body2"
    sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.25, whiteSpace: 'nowrap' }}
  >
    {children}
    <OpenInNew sx={{ fontSize: 14 }} aria-label="(opens in a new tab)" />
  </Link>
);

const targetLabel = (p: ChangeProposal, contact?: ContactInfo): React.ReactNode => {
  if (p.kind === 'new_contact')
    return (
      <>
        New contact at <PlainText value={p.company_name} />
      </>
    );
  if (p.kind === 'task')
    return (
      <>
        New task for <PlainText value={p.company_name} />
      </>
    );
  if (p.target_collection === 'contact') {
    return (
      <>
        {contact?.name ? <PlainText value={contact.name} /> : 'A contact'} at <PlainText value={p.company_name} />
      </>
    );
  }
  return <PlainText value={p.company_name} />;
};

const useExpired = (expiresAt: string, open: boolean): boolean => {
  const at = Date.parse(expiresAt);
  const [expired, setExpired] = useState(() => open && at <= Date.now());
  useEffect(() => {
    if (!open) return;
    const ms = at - Date.now();
    if (ms <= 0) {
      setExpired(true);
      return;
    }
    if (ms > 2_147_000_000) return; // further away than a timer can wait; a reload sees it
    const timer = setTimeout(() => setExpired(true), ms);
    return () => clearTimeout(timer);
  }, [at, open]);
  return expired;
};

const ProposalCard: React.FC<ProposalCardProps> = (props) => {
  const {
    proposal: p,
    settings,
    valuesFollowTarget,
    busy,
    notice,
    result,
    readOnly,
    contact,
    relatedName,
    partners,
    selected,
    focused,
    focusNonce,
    editing,
    serverErrors,
    acknowledged,
    conflictChoice,
    sourceChecked,
    handlers,
  } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [focusedHere, setFocusedHere] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const open = p.status === 'proposed';
  const expired = useExpired(p.expires_at, open);
  const conflicts = open ? p.conflicts_with || [] : [];
  const partnerFor = (id: string) => (partners || []).find((r) => r.id === id);
  const partnersShown = conflicts.every((c) => Boolean(partnerFor(c.id)));
  const actions = cardActions(p, {
    readOnly,
    expired,
    busy,
    decided: Boolean(result),
    editing,
    acknowledged,
    conflictChoice,
    partnersShown,
    sourceChecked,
  });
  const canTouch = open && !readOnly && !expired && !result;
  const editable = editableFields(settings, p.kind, p.target_collection);
  const outsideAllowlist = editable ? Object.keys(p.patch || {}).filter((k) => !editable.includes(k)) : [];
  const link = recordLink(p);
  const changesEmail = Object.prototype.hasOwnProperty.call(p.patch || {}, 'email');
  const roleContact =
    p.target_collection === 'contact' && contact && (contact.is_primary || contact.contact_type === 'Billing');
  const billingRecipient =
    p.target_collection === 'contact' &&
    contact &&
    (contact.receives_invoice_emails || contact.receives_payment_emails);

  // The "a" key works only after the card has been focused, and on screen, for a moment.
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.intersectionRatio >= 0.5), {
      threshold: [0, 0.5, 1],
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [result, showDetails]);

  const armable = focusedHere && visible && actions.accept.ok;
  const { onArm } = handlers;
  useEffect(() => {
    if (!armable) {
      onArm(p.id, false);
      return;
    }
    const timer = setTimeout(() => onArm(p.id, true), ARM_DELAY_MS);
    return () => {
      clearTimeout(timer);
      onArm(p.id, false);
    };
  }, [armable, p.id, p.seen_version, onArm]);

  useEffect(() => {
    const el = ref.current;
    if (!el || !focused) return;
    if (document.activeElement !== el && !el.contains(document.activeElement)) {
      el.focus({ preventScroll: false });
      if (typeof el.scrollIntoView === 'function') el.scrollIntoView({ block: 'nearest' });
    }
  }, [focused, focusNonce]);

  const decidedLine = () => {
    const last = [...(p.history || [])].reverse().find((h) => h.action !== 'reopened');
    const by = p.reviewer_username || last?.by;
    const at = p.reviewed_at || last?.at;
    if (p.status === 'expired') return `Expired ${formatDate(p.expires_at)}. Nothing was applied.`;
    if (p.status === 'superseded') return 'Replaced by a newer suggestion, or the record already had this value.';
    if (p.status === 'failed') return `Could not be applied${p.last_apply_error ? `: ${p.last_apply_error}` : '.'}`;
    return `${STATUS_LABEL[p.status]}${by ? ` by ${by}` : ''}${at ? `, ${formatDateTime(at)}` : ''}`;
  };

  // ------------------------------------------------------------------ collapsed result after a decision
  if (result && !showDetails) {
    return (
      <Paper
        ref={ref}
        tabIndex={-1}
        role="article"
        aria-label="Decision result"
        data-proposal-id={p.id}
        data-testid="proposal-result"
        variant="outlined"
        sx={{ px: 2, py: 1.25, display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', outline: 'none' }}
      >
        {result.tone === 'success' ? (
          <CheckCircleOutline color="success" fontSize="small" />
        ) : result.tone === 'error' ? (
          <CancelOutlined color="error" fontSize="small" />
        ) : (
          <InfoOutlined color={result.tone === 'warning' ? 'warning' : 'info'} fontSize="small" />
        )}
        <Typography variant="body2" sx={{ flex: '1 1 240px', minWidth: 0 }} role="status">
          <PlainText value={result.text} />
        </Typography>
        <NewTabLink href={link.href}>{link.label}</NewTabLink>
        <Button size="small" onClick={() => setShowDetails(true)}>
          Details
        </Button>
      </Paper>
    );
  }

  const disabledReason = open && !readOnly && !editing && !actions.accept.ok ? actions.accept.reason : undefined;

  return (
    <Paper
      ref={ref}
      tabIndex={0}
      role="article"
      data-proposal-id={p.id}
      data-testid="proposal-card"
      aria-label={`${kindLabel(p.kind)} suggestion for ${p.company_name}`}
      onFocus={() => {
        setFocusedHere(true);
        handlers.onFocusCard(p.id);
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setFocusedHere(false);
      }}
      variant="outlined"
      sx={(theme) => ({
        p: { xs: 1.5, sm: 2 },
        outline: 'none',
        borderColor: focused ? 'primary.main' : selected ? alpha(theme.palette.error.main, 0.6) : 'divider',
        boxShadow: focused ? `0 0 0 2px ${alpha(theme.palette.primary.main, 0.35)}` : 'none',
        transition: 'box-shadow 120ms, border-color 120ms',
      })}
    >
      {/* Header: what and where */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
        {canTouch && (
          <Checkbox
            size="small"
            checked={selected}
            disabled={!actions.select.ok}
            onChange={(e) => handlers.onSelect(p.id, e.target.checked)}
            inputProps={{ 'aria-label': 'Select for rejecting together' }}
            sx={{ p: 0.5, mt: -0.25 }}
          />
        )}
        <Box sx={{ flex: '1 1 260px', minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Chip size="small" label={kindLabel(p.kind)} variant="outlined" />
            <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 600, minWidth: 0 }}>
              {targetLabel(p, contact)}
            </Typography>
            <NewTabLink href={link.href}>{link.label}</NewTabLink>
            <TextChecks value={p.company_name} only={['lookalike', 'invisible']} />
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }} component="div">
            Suggested by <PlainText value={p.proposer_username || 'unknown'} />{' '}
            <span data-testid="proposer-kind">({PROPOSER_KIND_LABEL[p.proposer_kind] || p.proposer_kind})</span>
            {p.model ? (
              <>
                {' '}
                · model <PlainText value={p.model} />
              </>
            ) : null}
            {typeof p.confidence === 'number' ? ` · confidence ${Math.round(p.confidence * 100)}%` : ''}
            {` · ${formatDateTime(p.created_at)}`}
            {open ? ` · expires ${formatDate(p.expires_at)}` : ''}
            <TextChecks value={p.proposer_username || ''} only={['lookalike', 'invisible']} />
          </Typography>
        </Box>
        {!open && <Chip size="small" color={STATUS_TONE[p.status]} label={STATUS_LABEL[p.status] || p.status} />}
      </Box>

      {/* Warnings that must be seen before deciding */}
      <Box sx={{ display: 'grid', gap: 1, mt: 1.5 }}>
        {open && expired && (
          <Alert severity="warning" data-testid="expired-on-screen">
            This suggestion expired while it was on screen. Nothing can be applied; it will show as expired.
          </Alert>
        )}
        {open && p.target_changed_at && (
          <Alert severity="warning" data-testid="record-changed">
            <AlertTitle>The record changed after this was suggested</AlertTitle>
            The values under “Now” were re-read {formatDateTime(p.target_changed_at)}. Compare them with the suggestion
            before deciding.
            <Box>
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={acknowledged}
                    disabled={!canTouch || busy}
                    onChange={(e) => handlers.onAcknowledge(p, e.target.checked)}
                  />
                }
                label={<Typography variant="body2">I have compared the current values</Typography>}
              />
            </Box>
          </Alert>
        )}
        {conflicts.length > 0 && (
          <Alert severity="warning" icon={false} data-testid="conflict">
            <AlertTitle>Another open suggestion changes the same field</AlertTitle>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Pick one. Keeping this one rejects the other when you accept; nothing is left open by accident.
            </Typography>
            <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
              <ConflictOption
                title="This suggestion"
                by={p.proposer_username}
                when={p.evidence_occurred_at || p.created_at}
                patch={Object.fromEntries(
                  Object.keys(conflicts[0].patch || {}).map((k) => [k, (p.patch || {})[k] ?? null]),
                )}
                evidence={<EvidenceBlock proposal={p} compact />}
                chosen={conflictChoice === 'this'}
                disabled={!canTouch || busy || editing}
                actionLabel="Keep this one"
                onChoose={() => handlers.onChoose(p, conflictChoice === 'this' ? null : 'this')}
              />
              {conflicts.map((c) => {
                const row = partnerFor(c.id);
                return (
                  <ConflictOption
                    key={c.id}
                    title="The other suggestion"
                    by={c.proposer_username}
                    when={c.evidence_occurred_at || c.created_at}
                    patch={c.patch}
                    evidence={
                      row ? (
                        <EvidenceBlock proposal={row} compact />
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          Loading its evidence…
                        </Typography>
                      )
                    }
                    chosen={false}
                    disabled={!canTouch || busy || editing || !row}
                    actionLabel="Keep the other one"
                    onChoose={() => handlers.onPickOther(p, c)}
                  />
                );
              })}
            </Box>
          </Alert>
        )}
        {open && p.last_apply_error && !p.target_changed_at && (
          <Alert severity="error" data-testid="apply-error">
            <AlertTitle>The last attempt to apply this failed</AlertTitle>
            <PlainText value={p.last_apply_error} />
          </Alert>
        )}
        {open && outsideAllowlist.length > 0 && (
          <Alert severity="warning">
            No longer allowed to be changed by a suggestion: {outsideAllowlist.map(fieldLabel).join(', ')}. Use Edit to
            leave {outsideAllowlist.length === 1 ? 'it' : 'them'} out, or reject.
          </Alert>
        )}
        {open && roleContact && (
          <Alert severity="warning" data-testid="role-contact">
            This is the customer’s {contact?.is_primary ? 'primary' : 'billing'} contact. Check the change with extra
            care.
            {changesEmail
              ? ' The server refuses email changes for this contact; a person has to change it on the contact.'
              : ''}
          </Alert>
        )}
        {open && !roleContact && billingRecipient && changesEmail && (
          <Alert severity="warning" data-testid="billing-email">
            This contact receives invoices or payment emails, so the server will refuse this email change. A person has
            to change it on the contact.
          </Alert>
        )}
        {open && needsSourceCheck(p) && (
          <Alert severity="info" variant="outlined" data-testid="source-check">
            This changes an email address or phone number, and its evidence is not from captured mail. An address or
            number taken from a message can be forged: confirm it with the customer (for example by phone) before
            accepting.
            <Box>
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={sourceChecked}
                    disabled={!canTouch || busy}
                    onChange={(e) => handlers.onSourceCheck(p, e.target.checked)}
                  />
                }
                label={<Typography variant="body2">I checked this against the source myself</Typography>}
              />
            </Box>
          </Alert>
        )}
        {open && changesEmail && !needsSourceCheck(p) && (
          <Alert severity="info" variant="outlined" data-testid="email-caution">
            An email address taken from a message can be forged. If it is new to you, confirm it with the customer by
            phone before accepting.
          </Alert>
        )}
        {open && p.kind === 'new_contact' && (
          <Typography variant="caption" color="text.secondary">
            A contact created from a suggestion receives no automatic or document emails and is not the primary contact.
          </Typography>
        )}
      </Box>

      {/* Body: the change, and what it rests on */}
      <Box
        sx={{
          display: 'grid',
          gap: { xs: 2, md: 3 },
          gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.15fr) minmax(0, 1fr)' },
          mt: 1.5,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          {editing && canTouch ? (
            <EditForm
              proposal={p}
              editable={editable}
              busy={busy}
              blockedReason={actions.acceptEdits.ok ? null : actions.acceptEdits.reason}
              serverErrors={serverErrors}
              onCancel={() => handlers.onEdit(p.id, false)}
              onSubmit={(edits, drop) => handlers.onAcceptEdits(p, edits, drop)}
            />
          ) : (
            <ChangePreview
              proposal={p.status === 'edited' && p.applied_patch ? { ...p, patch: p.applied_patch } : p}
              relatedName={relatedName}
              valuesFollowTarget={valuesFollowTarget}
            />
          )}
        </Box>
        <Box sx={{ minWidth: 0, display: 'grid', gap: 1.5, alignContent: 'start' }}>
          <EvidenceBlock proposal={p} />
          {p.rationale && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                Why the {PROPOSER_KIND_LABEL[p.proposer_kind]?.toLowerCase() || 'proposer'} suggests it
              </Typography>
              <Typography variant="body2" component="div">
                <PlainText value={p.rationale} clampAt={400} />
              </Typography>
            </Box>
          )}
        </Box>
      </Box>

      {/* Decided: who, when, and the history */}
      {!open && (
        <Box sx={{ mt: 1.5 }} data-testid="decided-line">
          <Typography variant="body2">
            <PlainText value={decidedLine()} />
          </Typography>
          {p.decision_note && (
            <Typography variant="body2" color="text.secondary" component="div">
              {p.status === 'rejected' ? 'Reason: ' : 'Note: '}
              <PlainText value={p.decision_note} />
            </Typography>
          )}
          {p.status === 'edited' && p.applied_patch && (
            <Typography variant="caption" color="text.secondary" component="div">
              Originally suggested:{' '}
              {Object.entries(p.patch || {}).map(([k, v], i) => (
                <React.Fragment key={k}>
                  {i > 0 && '; '}
                  {fieldLabel(k)} ={' '}
                  {displayValue(v) ? <PlainText value={displayValue(v)} clampAt={120} edges /> : <Empty />}
                </React.Fragment>
              ))}
            </Typography>
          )}
          {(p.history || []).length > 0 && (
            <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5, color: 'text.secondary' }} aria-label="History">
              {(p.history || []).map((h, i) => (
                <Typography component="li" variant="caption" key={i}>
                  <HistoryOutlined sx={{ fontSize: 12, mr: 0.5, verticalAlign: 'middle' }} />
                  {h.action} by <PlainText value={h.by || 'unknown'} />, {formatDateTime(h.at)}
                  {h.note ? (
                    <>
                      : <PlainText value={h.note} clampAt={200} />
                    </>
                  ) : null}
                </Typography>
              ))}
            </Box>
          )}
        </Box>
      )}

      {/* The answer to the last decision attempt */}
      {notice && (
        <Alert severity={notice.tone} sx={{ mt: 1.5 }} role="alert" data-testid="card-notice">
          <PlainText value={notice.text} />
          {notice.details && notice.details.length > 0 && (
            <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
              {notice.details.map((d, i) => (
                <li key={i}>
                  <PlainText value={d} />
                </li>
              ))}
            </Box>
          )}
        </Alert>
      )}

      {readOnly && (open || p.status === 'rejected') && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1.5, display: 'flex', alignItems: 'center', gap: 0.75 }}
          data-testid="read-only-reason"
        >
          <LockOutlined sx={{ fontSize: 16 }} />
          <PlainText value={readOnly} />
        </Typography>
      )}

      {/* Decisions */}
      {canTouch && !editing && (
        <>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 2, alignItems: 'center' }}>
            <Button
              variant="contained"
              startIcon={<CheckCircleOutline />}
              disabled={!actions.accept.ok}
              onClick={() => handlers.onAccept(p)}
            >
              {busy ? 'Saving…' : conflicts.length ? 'Accept and reject the other' : 'Accept'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<EditOutlined />}
              disabled={!actions.edit.ok}
              onClick={() => handlers.onEdit(p.id, true)}
            >
              Edit
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelOutlined />}
              disabled={!actions.reject.ok}
              onClick={() => handlers.onRequestReject(p)}
            >
              Reject
            </Button>
          </Box>
          {disabledReason && !busy && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }} data-testid="accept-blocked-reason">
              {disabledReason}
            </Typography>
          )}
        </>
      )}
      {p.status === 'rejected' && actions.reopen.ok && (
        <Box sx={{ mt: 1.5 }}>
          <Button size="small" startIcon={<ReplayOutlined />} onClick={() => handlers.onRequestReopen(p)}>
            Reopen
          </Button>
        </Box>
      )}
      {result && showDetails && (
        <Box sx={{ mt: 1 }}>
          <Button size="small" onClick={() => setShowDetails(false)}>
            Hide details
          </Button>
        </Box>
      )}
    </Paper>
  );
};

const ConflictOption: React.FC<{
  title: string;
  by: string;
  when: string;
  patch: Record<string, PatchValue>;
  evidence: React.ReactNode;
  chosen: boolean;
  disabled: boolean;
  actionLabel: string;
  onChoose: () => void;
}> = ({ title, by, when, patch, evidence, chosen, disabled, actionLabel, onChoose }) => (
  <Box
    sx={(theme) => ({
      p: 1.25,
      borderRadius: 1,
      border: 1,
      borderColor: chosen ? 'success.main' : 'divider',
      bgcolor: chosen ? alpha(theme.palette.success.main, 0.08) : 'background.paper',
      minWidth: 0,
      color: 'text.primary',
    })}
  >
    <Typography variant="caption" color="text.secondary" component="div">
      {title} · by <PlainText value={by || 'unknown'} /> · source {formatDateTime(when)}
    </Typography>
    {Object.entries(patch || {}).map(([k, v]) => (
      <Typography variant="body2" key={k} component="div" sx={{ mt: 0.25 }}>
        {fieldLabel(k)}: <strong>{displayValue(v) ? <PlainText value={displayValue(v)} edges /> : <Empty />}</strong>
      </Typography>
    ))}
    <Box sx={{ mt: 1 }}>{evidence}</Box>
    <Button
      size="small"
      sx={{ mt: 0.75 }}
      variant={chosen ? 'contained' : 'outlined'}
      color="success"
      disabled={disabled}
      onClick={onChoose}
    >
      {chosen ? 'Chosen' : actionLabel}
    </Button>
  </Box>
);

export default React.memo(ProposalCard);
