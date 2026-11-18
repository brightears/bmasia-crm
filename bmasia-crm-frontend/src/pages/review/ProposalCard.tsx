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
  Tooltip,
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
import ChangePreview from './ChangePreview';
import EditForm from './EditForm';
import EvidenceBlock from './EvidenceBlock';
import PlainText from './PlainText';
import {
  PROPOSER_KIND_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  displayValue,
  editableFields,
  fieldLabel,
  formatDateTime,
  kindLabel,
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

interface ProposalCardProps {
  proposal: ChangeProposal;
  settings: ReviewSettings | null;
  now: number;
  busy: boolean;
  notice?: CardNotice;
  result?: DecisionResult;
  readOnly: string | null;
  contact?: ContactInfo;
  contactNames: Record<string, string>;
  selected: boolean;
  focused: boolean;
  editing: boolean;
  serverErrors?: Record<string, string>;
  onSelect: (id: string, checked: boolean) => void;
  onFocusCard: (id: string) => void;
  onArm: (id: string, armed: boolean) => void;
  onEdit: (id: string, editing: boolean) => void;
  onAccept: (p: ChangeProposal, conflictChoice?: ConflictChoice) => void;
  onAcceptEdits: (
    p: ChangeProposal,
    edits: Record<string, PatchValue>,
    drop: string[],
    conflictChoice?: ConflictChoice,
  ) => void;
  onRequestReject: (p: ChangeProposal) => void;
  onRequestReopen: (p: ChangeProposal) => void;
  onPickOther: (p: ChangeProposal, other: ProposalConflict) => void;
  /** Look again acknowledged for a changed record; the page keeps it per seen_version. */
  acknowledged: boolean;
  onAcknowledge: (p: ChangeProposal, value: boolean) => void;
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

const ProposalCard: React.FC<ProposalCardProps> = (props) => {
  const {
    proposal: p,
    settings,
    now,
    busy,
    notice,
    result,
    readOnly,
    contact,
    contactNames,
    selected,
    focused,
    editing,
    serverErrors,
    onSelect,
    onFocusCard,
    onArm,
    onEdit,
    onAccept,
    onAcceptEdits,
    onRequestReject,
    onRequestReopen,
    onPickOther,
    acknowledged,
    onAcknowledge,
  } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  const [focusedHere, setFocusedHere] = useState(false);
  const [conflictChoice, setConflictChoice] = useState<ConflictChoice | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const open = p.status === 'proposed';
  const expiredOnScreen = open && new Date(p.expires_at).getTime() <= now;
  const conflicts = open ? p.conflicts_with || [] : [];
  const canDecide = open && !readOnly && !expiredOnScreen;
  const needsAck = open && Boolean(p.target_changed_at) && !acknowledged;
  const needsChoice = conflicts.length > 0 && conflictChoice !== 'this';
  const acceptBlocked = !canDecide || busy || needsAck || needsChoice;
  const editable = editableFields(settings, p.kind, p.target_collection);
  const outsideAllowlist = editable ? Object.keys(p.patch || {}).filter((k) => !editable.includes(k)) : [];
  const link = recordLink(p);
  const changesEmail = Object.prototype.hasOwnProperty.call(p.patch || {}, 'email');
  const roleContact =
    p.target_collection === 'contact' && contact && (contact.is_primary || contact.contact_type === 'Billing');
  // The server refuses an email change on a contact that gets invoices or payment emails.
  const billingRecipient =
    p.target_collection === 'contact' &&
    contact &&
    (contact.receives_invoice_emails || contact.receives_payment_emails);

  // Reset the conflict choice whenever what is shown changes.
  useEffect(() => setConflictChoice(null), [p.seen_version]);

  // The "a" key works only after the card has been focused, and on screen, for a moment.
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.intersectionRatio >= 0.5), {
      threshold: [0, 0.5, 1],
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!focusedHere || !visible || !canDecide) {
      onArm(p.id, false);
      return;
    }
    const timer = setTimeout(() => onArm(p.id, true), ARM_DELAY_MS);
    return () => {
      clearTimeout(timer);
      onArm(p.id, false);
    };
  }, [focusedHere, visible, canDecide, p.id, p.seen_version, onArm]);

  useEffect(() => {
    if (
      focused &&
      ref.current &&
      document.activeElement !== ref.current &&
      !ref.current.contains(document.activeElement)
    ) {
      ref.current.focus({ preventScroll: false });
      if (typeof ref.current.scrollIntoView === 'function') ref.current.scrollIntoView({ block: 'nearest' });
    }
  }, [focused]);

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
        data-proposal-id={p.id}
        data-testid="proposal-result"
        variant="outlined"
        sx={{ px: 2, py: 1.25, display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}
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

  return (
    <Paper
      ref={ref}
      tabIndex={0}
      data-proposal-id={p.id}
      data-testid="proposal-card"
      aria-label={`${kindLabel(p.kind)} suggestion for ${p.company_name}`}
      onFocus={() => {
        setFocusedHere(true);
        onFocusCard(p.id);
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
        opacity: open || showDetails ? 1 : 0.92,
      })}
    >
      {/* Header: what and where */}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
        {open && canDecide && (
          <Checkbox
            size="small"
            checked={selected}
            onChange={(e) => onSelect(p.id, e.target.checked)}
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
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Suggested by <PlainText value={p.proposer_username || 'unknown'} /> (
            {PROPOSER_KIND_LABEL[p.proposer_kind] || p.proposer_kind})
            {p.model ? (
              <>
                {' '}
                · model <PlainText value={p.model} />
              </>
            ) : null}
            {typeof p.confidence === 'number' ? ` · confidence ${Math.round(p.confidence * 100)}%` : ''}
            {` · ${formatDateTime(p.created_at)}`}
            {open ? ` · expires ${formatDate(p.expires_at)}` : ''}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {!open && <Chip size="small" color={STATUS_TONE[p.status]} label={STATUS_LABEL[p.status] || p.status} />}
        </Box>
      </Box>

      {/* Warnings that must be seen before deciding */}
      <Box sx={{ display: 'grid', gap: 1, mt: 1.5 }}>
        {expiredOnScreen && (
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
                    disabled={!canDecide}
                    onChange={(e) => onAcknowledge(p, e.target.checked)}
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
              Pick one. Accepting this one rejects the other; nothing is left open by accident.
            </Typography>
            <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              <ConflictOption
                title="This suggestion"
                by={p.proposer_username}
                when={p.evidence_occurred_at || p.created_at}
                patch={Object.fromEntries(
                  Object.keys(conflicts[0].patch || {}).map((k) => [k, (p.patch || {})[k] ?? null]),
                )}
                chosen={conflictChoice === 'this'}
                disabled={!canDecide || busy}
                actionLabel="Keep this one"
                onChoose={() => setConflictChoice('this')}
              />
              {conflicts.map((c) => (
                <ConflictOption
                  key={c.id}
                  title="The other suggestion"
                  by={c.proposer_username}
                  when={c.evidence_occurred_at || c.created_at}
                  patch={c.patch}
                  chosen={false}
                  disabled={!canDecide || busy}
                  actionLabel="Keep the other one"
                  onChoose={() => onPickOther(p, c)}
                />
              ))}
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
        {open && changesEmail && (
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
          {editing && canDecide ? (
            <EditForm
              proposal={p}
              editable={editable}
              busy={busy}
              serverErrors={serverErrors}
              onCancel={() => onEdit(p.id, false)}
              onSubmit={(edits, drop) => onAcceptEdits(p, edits, drop, conflictChoice || undefined)}
            />
          ) : (
            <ChangePreview
              proposal={p.status === 'edited' && p.applied_patch ? { ...p, patch: p.applied_patch } : p}
              contactNames={contactNames}
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
                <PlainText value={p.rationale} multiline clampAt={400} />
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
              <PlainText value={p.decision_note} multiline />
            </Typography>
          )}
          {p.status === 'edited' && p.applied_patch && (
            <Typography variant="caption" color="text.secondary" component="div">
              Originally suggested:{' '}
              {Object.entries(p.patch || {}).map(([k, v], i) => (
                <React.Fragment key={k}>
                  {i > 0 && '; '}
                  {fieldLabel(k)} = <PlainText value={displayValue(v) || 'empty'} clampAt={120} />
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
      {open && canDecide && !editing && (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 2, alignItems: 'center' }}>
          <Tooltip
            title={
              needsAck
                ? 'Tick “I have compared the current values” first.'
                : needsChoice
                  ? 'Pick which of the two suggestions to keep first.'
                  : 'Accept (key A once the card has been in focus for a moment)'
            }
          >
            <span>
              <Button
                variant="contained"
                startIcon={<CheckCircleOutline />}
                disabled={acceptBlocked}
                onClick={() => onAccept(p, conflictChoice || undefined)}
              >
                {busy ? 'Saving…' : conflicts.length ? 'Accept and reject the other' : 'Accept'}
              </Button>
            </span>
          </Tooltip>
          <Button
            variant="outlined"
            startIcon={<EditOutlined />}
            disabled={busy || needsAck || needsChoice}
            onClick={() => onEdit(p.id, true)}
          >
            Edit
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelOutlined />}
            disabled={busy}
            onClick={() => onRequestReject(p)}
          >
            Reject
          </Button>
        </Box>
      )}
      {p.status === 'rejected' && !readOnly && !result && (
        <Box sx={{ mt: 1.5 }}>
          <Button size="small" startIcon={<ReplayOutlined />} disabled={busy} onClick={() => onRequestReopen(p)}>
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
  chosen: boolean;
  disabled: boolean;
  actionLabel: string;
  onChoose: () => void;
}> = ({ title, by, when, patch, chosen, disabled, actionLabel, onChoose }) => (
  <Box
    sx={(theme) => ({
      p: 1.25,
      borderRadius: 1,
      border: 1,
      borderColor: chosen ? 'success.main' : 'divider',
      bgcolor: chosen ? alpha(theme.palette.success.main, 0.08) : 'background.paper',
      minWidth: 0,
    })}
  >
    <Typography variant="caption" color="text.secondary" component="div">
      {title} · by <PlainText value={by || 'unknown'} /> · source {formatDateTime(when)}
    </Typography>
    {Object.entries(patch || {}).map(([k, v]) => (
      <Typography variant="body2" key={k} component="div" sx={{ mt: 0.25 }}>
        {fieldLabel(k)}:{' '}
        <strong>
          <PlainText value={displayValue(v) || 'empty'} />
        </strong>
      </Typography>
    ))}
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

export default ProposalCard;
