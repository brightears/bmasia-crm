/**
 * Plain rules for the Review page: labels, field rules that mirror the API, text safety checks,
 * grouping and URL state. No React here, so all of it is unit-tested directly.
 */
import { formatDate } from '../../theme';
import { hasInvisible, hasUnusualSpaces, lookalikeScripts, mixesDirections, safeHttpUrl } from './textSafety';
import type { ChangeProposal, EvidenceState, ProposalStatus, ReviewSettings } from '../../services/reviewApi';

// ------------------------------------------------------------------ labels

export const KIND_LABEL: Record<string, string> = {
  field_update: 'Update fields',
  new_contact: 'New contact',
  note: 'Add to notes',
  task: 'New task',
  link: 'Link records',
  other: 'Other',
};

export const COLLECTION_LABEL: Record<string, string> = {
  company: 'Company',
  contact: 'Contact',
  task: 'Task',
};

export const PROPOSER_KIND_LABEL: Record<string, string> = {
  agent: 'Agent',
  ai: 'AI',
  job: 'Job',
  human: 'Person',
};

export const VIA_LABEL: Record<string, string> = {
  rest: 'REST API',
  mcp: 'MCP tool',
  ui: 'CRM website',
  job: 'Background job',
};

export const SOURCE_LABEL: Record<string, string> = {
  gmail: 'Gmail',
  google_chat: 'Google Chat',
  calendar: 'Calendar',
  phone: 'Phone',
  sheet: 'Google Sheet',
  drive: 'Google Drive',
  agent: 'Agent conversation',
  crm: 'CRM record',
  manual: 'Entered by a person',
  other: 'Other',
};

export const STATUS_LABEL: Record<ProposalStatus, string> = {
  proposed: 'Open',
  accepted: 'Accepted',
  edited: 'Accepted with edits',
  rejected: 'Rejected',
  expired: 'Expired',
  superseded: 'Superseded',
  failed: 'Failed',
};

export const STATUS_TONE: Record<ProposalStatus, 'success' | 'error' | 'warning' | 'default' | 'info'> = {
  proposed: 'info',
  accepted: 'success',
  edited: 'success',
  rejected: 'error',
  expired: 'default',
  superseded: 'default',
  failed: 'warning',
};

export const EVIDENCE_LABEL: Record<EvidenceState, string> = {
  verified_captured: 'From captured mail',
  verified_agent_recorded: 'From text an agent recorded',
  unverified: 'No evidence attached',
};

export const EVIDENCE_HELP: Record<EvidenceState, string> = {
  verified_captured:
    'The quote was found word for word in a message the capture job or a person recorded. Still check that it supports the change.',
  verified_agent_recorded:
    'The quote was found in text that an agent wrote into the CRM itself, not in a captured message. The agent could have written that text.',
  unverified: 'Nothing was checked: there is no stored message this quote was found in.',
};

const FIELD_LABEL: Record<string, string> = {
  name: 'Name',
  email: 'Email',
  phone: 'Phone',
  mobile: 'Mobile',
  title: 'Job title',
  department: 'Department',
  preferred_contact_method: 'Preferred contact method',
  linkedin_url: 'LinkedIn',
  notes: 'Notes',
  website: 'Website',
  address_line1: 'Address line 1',
  address_line2: 'Address line 2',
  city: 'City',
  state: 'State / province',
  postal_code: 'Postal code',
  country: 'Country',
  description: 'Description',
  priority: 'Priority',
  task_type: 'Task type',
  due_date: 'Due date',
  related_contact: 'Linked contact',
  related_contract: 'Linked contract',
  related_opportunity: 'Linked opportunity',
};

export const fieldLabel = (key: string): string =>
  FIELD_LABEL[key] || key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

export const kindLabel = (kind: string) => KIND_LABEL[kind] || kind;

/** "14 Nov 2026, 10:32" in the browser's time zone; "—" for nothing. */
export const formatDateTime = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${formatDate(date)}, ${hh}:${mm}`;
};

// ------------------------------------------------------------------ field rules (as the API enforces them)

export interface FieldRule {
  maxLength?: number;
  multiline?: boolean;
  kind?: 'email' | 'url' | 'choice' | 'datetime' | 'uuid' | 'contact_phone';
  choices?: string[];
  hint?: string;
}

/** Same limit as the API's PATCH_VALUE_MAX. */
export const PATCH_VALUE_MAX = 5000;

const COMMON: Record<string, FieldRule> = {
  notes: { multiline: true, hint: 'Plain text. Added below the existing notes.' },
  email: { kind: 'email', maxLength: 254, hint: 'One email address.' },
};

const RULES: Record<string, Record<string, FieldRule>> = {
  company: {
    ...COMMON,
    phone: { maxLength: 50 },
    website: { kind: 'url', maxLength: 200, hint: 'A full address starting with http:// or https://.' },
    address_line1: { maxLength: 255 },
    address_line2: { maxLength: 255 },
    city: { maxLength: 100 },
    state: { maxLength: 100 },
    postal_code: { maxLength: 20 },
    country: { maxLength: 100 },
  },
  contact: {
    ...COMMON,
    name: { maxLength: 100 },
    phone: {
      kind: 'contact_phone',
      maxLength: 20,
      hint: 'Digits with an optional leading +, 9 to 15 digits, no spaces.',
    },
    mobile: { maxLength: 20 },
    title: { maxLength: 100 },
    department: { maxLength: 100 },
    preferred_contact_method: { kind: 'choice', choices: ['Email', 'Phone', 'Mobile', 'LinkedIn'] },
    linkedin_url: { kind: 'url', maxLength: 200, hint: 'A full address starting with http:// or https://.' },
  },
  task: {
    title: { maxLength: 200 },
    description: { multiline: true },
    priority: { kind: 'choice', choices: ['Low', 'Medium', 'High', 'Urgent'] },
    task_type: { kind: 'choice', choices: ['Call', 'Email', 'Follow-up', 'Meeting', 'Other'] },
    due_date: { kind: 'datetime', hint: 'Date and time, e.g. 2026-11-20T09:00:00+07:00.' },
    related_contact: { kind: 'uuid', hint: 'ID of a contact of this company.' },
    related_contract: { kind: 'uuid', hint: 'ID of a contract of this company.' },
    related_opportunity: { kind: 'uuid', hint: 'ID of an opportunity of this company.' },
  },
};

export const fieldRule = (collection: string, key: string): FieldRule => RULES[collection]?.[key] || {};

/** Fields a creating proposal must keep (the API's PROPOSAL_REQUIRED_FIELDS). */
export const REQUIRED_FIELDS: Record<string, string[]> = {
  new_contact: ['name', 'email'],
  task: ['title'],
  note: ['notes'],
};

/** Fields the allowlist lets this kind change on this collection; null when the allowlist is unknown. */
export const editableFields = (
  settings: ReviewSettings | null | undefined,
  kind: string,
  collection: string,
): string[] | null => {
  const fields = settings?.kinds?.[kind]?.[collection];
  return Array.isArray(fields) ? fields : null;
};

// ------------------------------------------------------------------ text safety

export {
  hasInvisible,
  hasUnusualSpaces,
  segmentText,
  lookalikeScripts,
  mixesDirections,
  describeLink,
  safeHttpUrl,
} from './textSafety';
export type { TextSegment, LinkInfo } from './textSafety';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const UUID_RE = /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i;

/** What the API would refuse in one edited value, in plain words; null when it looks fine. */
export const validateValue = (collection: string, key: string, value: string): string | null => {
  const rule = fieldRule(collection, key);
  const text = value.trim();
  if (text.length > PATCH_VALUE_MAX) return `At most ${PATCH_VALUE_MAX.toLocaleString('en-US')} characters.`;
  if (rule.maxLength && text.length > rule.maxLength) return `At most ${rule.maxLength} characters.`;
  const withoutNewlines = rule.multiline ? text.replace(/\n/g, '') : text;
  if (hasInvisible(withoutNewlines) || (!rule.multiline && /[\r\n]/.test(text))) {
    return rule.multiline
      ? 'Remove control or invisible characters.'
      : 'One line only, without control or invisible characters.';
  }
  if (!text) return null;
  switch (rule.kind) {
    case 'email':
      return EMAIL_RE.test(text) ? null : 'Not an email address.';
    case 'url':
      return safeHttpUrl(text) ? null : 'Must start with http:// or https://.';
    case 'choice':
      return rule.choices?.includes(text) ? null : `One of: ${rule.choices?.join(', ')}.`;
    case 'datetime':
      return Number.isNaN(new Date(text).getTime()) ? 'Not a date and time.' : null;
    case 'uuid':
      return UUID_RE.test(text) ? null : 'Not a record ID.';
    case 'contact_phone':
      return /^\+?1?\d{9,15}$/.test(text) ? null : 'Digits only with an optional +, 9 to 15 digits.';
    default:
      return null;
  }
};

// ------------------------------------------------------------------ proposals

export const isOpen = (p: ChangeProposal) => p.status === 'proposed';

/** Why an open proposal belongs on "Needs another look". */
export const needsAnotherLook = (p: ChangeProposal): string[] => {
  const reasons: string[] = [];
  if (p.target_changed_at) reasons.push('record_changed');
  if (p.conflicts_with && p.conflicts_with.length) reasons.push('conflict');
  if (p.last_apply_error) reasons.push('apply_error');
  return reasons;
};

/** When the source says it happened, else when the suggestion was made. */
export const evidenceTime = (p: ChangeProposal): number => {
  const t = new Date(p.evidence_occurred_at || p.created_at).getTime();
  return Number.isNaN(t) ? 0 : t;
};

export interface BatchGroup {
  key: string;
  batchKey: string;
  proposals: ChangeProposal[];
}

export interface CompanyGroup {
  companyId: string;
  companyName: string;
  batches: BatchGroup[];
  count: number;
}

/**
 * Groups by company, then by source batch, newest evidence first at every level.
 * A proposal without a batch key forms its own group.
 */
/** Newest evidence first, or soonest to expire first. */
export const sortProposals = (rows: ChangeProposal[], sort: 'newest' | 'expiring' = 'newest'): ChangeProposal[] =>
  [...rows].sort((a, b) =>
    sort === 'expiring'
      ? Date.parse(a.expires_at) - Date.parse(b.expires_at) || a.created_at.localeCompare(b.created_at)
      : evidenceTime(b) - evidenceTime(a) || b.created_at.localeCompare(a.created_at),
  );

/** Groups rows by company, then by batch, in the order given by `sortProposals` (or as given when presorted). */
export const groupProposals = (
  rows: ChangeProposal[],
  sort: 'newest' | 'expiring' = 'newest',
  presorted = false,
): CompanyGroup[] => {
  const sorted = presorted ? rows : sortProposals(rows, sort);
  const companies = new Map<string, CompanyGroup>();
  sorted.forEach((p) => {
    let company = companies.get(p.company_id);
    if (!company) {
      company = { companyId: p.company_id, companyName: p.company_name, batches: [], count: 0 };
      companies.set(p.company_id, company);
    }
    const key = p.batch_key ? `batch:${p.batch_key}` : `single:${p.id}`;
    let batch = company.batches.find((b) => b.key === key);
    if (!batch) {
      batch = { key, batchKey: p.batch_key, proposals: [] };
      company.batches.push(batch);
    }
    batch.proposals.push(p);
    company.count += 1;
  });
  return Array.from(companies.values());
};

/** The backend's refusal in plain words, without the names of server settings. */
export const friendlyRefusal = (detail?: string | null, code?: string, configured?: boolean): string => {
  if (code === 'review_not_configured' || configured === false)
    return 'Reviewing is not set up yet. Ask an administrator.';
  if (code === 'not_a_reviewer') return 'Your account is not on the list of reviewers. Ask an administrator.';
  const text = (detail || '')
    .replace(/\s*\(?\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b\)?/g, '')
    .replace(/\s*:\s*(?=[.]|$)/g, '')
    .replace(/\s+([.,])/g, '$1')
    .trim();
  return text || 'Your account may not decide on suggestions.';
};

/** Who may decide this proposal from this page, or why not (one line). */
export const readOnlyReason = (
  p: ChangeProposal,
  username: string | undefined,
  pageReason: string | null,
): string | null => {
  if (pageReason) return pageReason;
  const me = (username || '').trim().toLowerCase();
  if (me && p.proposer_username && p.proposer_username.trim().toLowerCase() === me) {
    return 'You made this suggestion, so another person has to decide on it.';
  }
  if (me && p.evidence_recorded_by && p.evidence_recorded_by.trim().toLowerCase() === me) {
    return 'You recorded the evidence for this suggestion, so another person has to decide on it.';
  }
  return null;
};

/** Values that are shown in a field; null and empty mean "empty". */
export const displayValue = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return '';
  }
};

export type ValueWarning = 'lookalike' | 'direction' | 'server_mixed' | 'invisible' | 'spaces';

/**
 * What to flag on one proposal-supplied value. Look-alike alphabets and mixed writing directions
 * are told apart; when the server flags a value the local checks cannot explain, that is shown too.
 */
export const textWarnings = (value: string, serverFlag = false): ValueWarning[] => {
  const out: ValueWarning[] = [];
  const lookalike = lookalikeScripts(value).length > 0;
  const direction = mixesDirections(value);
  if (lookalike) out.push('lookalike');
  if (direction) out.push('direction');
  if (serverFlag && !lookalike && !direction) out.push('server_mixed');
  if (hasInvisible(value)) out.push('invisible');
  if (hasUnusualSpaces(value)) out.push('spaces');
  return out;
};

export const fieldWarnings = (p: ChangeProposal, key: string, value: string): ValueWarning[] => {
  const fromApi = (p.warnings || []).filter((w) => !w.field || w.field === key).map((w) => w.code);
  const ms = p.mixed_script;
  const apiMixed = Boolean(
    fromApi.includes('mixed_script') ||
    ms === true ||
    (Array.isArray(ms) && ms.includes(key)) ||
    (ms && typeof ms === 'object' && !Array.isArray(ms) && key in ms),
  );
  return textWarnings(value, apiMixed);
};

// ------------------------------------------------------------------ what can be done to a card

/** Fields whose change can redirect messages: they need a check against the source when unverified. */
export const CONTACT_ROUTE_FIELDS = ['email', 'phone', 'mobile'];

/** Accepting needs the reviewer's own check against the source: evidence not from captured mail, and an email or phone change. */
export const needsSourceCheck = (p: ChangeProposal): boolean =>
  p.evidence !== 'verified_captured' && Object.keys(p.patch || {}).some((k) => CONTACT_ROUTE_FIELDS.includes(k));

export interface CardState {
  /** One line of why this user may not decide, or null. */
  readOnly: string | null;
  /** Expired by the clock, while on screen. */
  expired: boolean;
  busy: boolean;
  /** A decision on this card has already been answered on this page. */
  decided: boolean;
  editing: boolean;
  /** The "I have compared the current values" tick, for the version shown. */
  acknowledged: boolean;
  /** Which of two conflicting suggestions to keep, for the version shown. */
  conflictChoice: 'this' | 'other' | null;
  /** The other suggestions' evidence is on screen. */
  partnersShown: boolean;
  /** The "I checked this against the source myself" tick, for the version shown. */
  sourceChecked: boolean;
  /** For a contact target: whether its primary/billing flags were read ('ok'), are being read, or could not be read. */
  contactCheck?: 'ok' | 'pending' | 'failed';
  /** The "I have checked this contact myself" tick, for the version shown, when the look-up failed. */
  contactChecked?: boolean;
  /** The other side of a conflict could not be read. */
  partnersFailed?: boolean;
}

export interface Allowed {
  ok: boolean;
  /** Why not, in one visible line. */
  reason?: string;
}

export interface CardActions {
  accept: Allowed;
  edit: Allowed;
  acceptEdits: Allowed;
  reject: Allowed;
  select: Allowed;
  reopen: Allowed;
}

const no = (reason: string): Allowed => ({ ok: false, reason });
const yes: Allowed = { ok: true };

/**
 * The one place that decides what can be done to a card right now. The buttons, the edit form and
 * the keyboard shortcuts all ask this, so they cannot disagree.
 */
export const cardActions = (p: ChangeProposal, s: CardState): CardActions => {
  const conflicts = p.status === 'proposed' ? (p.conflicts_with || []).length : 0;
  let base: Allowed = yes;
  if (s.decided) base = no('Already decided on this page.');
  else if (p.status !== 'proposed') base = no('This suggestion is closed.');
  else if (s.readOnly) base = no(s.readOnly);
  else if (s.expired) base = no('This suggestion has expired.');
  else if (s.busy) base = no('Waiting for the answer to the last decision.');

  let gate: Allowed = yes;
  if (p.target_changed_at && !s.acknowledged) gate = no('Tick “I have compared the current values” first.');
  else if (s.contactCheck === 'pending') gate = no('Checking whether this is the primary or billing contact…');
  else if (s.contactCheck === 'failed' && !s.contactChecked)
    gate = no('Tick “I have checked this contact myself” first.');
  else if (conflicts && s.partnersFailed && !s.partnersShown)
    gate = no('Could not load the other suggestion’s evidence. Retry first.');
  else if (conflicts && !s.partnersShown) gate = no('Wait until the other suggestion’s evidence is shown.');
  else if (conflicts && s.conflictChoice !== 'this') gate = no('Choose which of the two suggestions to keep first.');
  else if (needsSourceCheck(p) && !s.sourceChecked) gate = no('Tick “I checked this against the source myself” first.');

  const accepting = !base.ok ? base : !gate.ok ? gate : yes;
  return {
    accept: !accepting.ok ? accepting : s.editing ? no('Finish or cancel the edit first.') : yes,
    edit: !accepting.ok ? accepting : s.editing ? no('Already editing.') : yes,
    acceptEdits: !accepting.ok ? accepting : s.editing ? yes : no('Open the edit form first.'),
    reject: base,
    select: !base.ok ? base : s.editing ? no('Finish or cancel the edit first.') : yes,
    reopen:
      p.status === 'rejected' && !s.readOnly && !s.busy && !s.decided
        ? yes
        : no(s.readOnly || 'Only a rejected suggestion can be reopened.'),
  };
};

// ------------------------------------------------------------------ URL state

export type ReviewTab = 'open' | 'look' | 'decided';
export const TABS: ReviewTab[] = ['open', 'look', 'decided'];
export type ReviewSort = 'newest' | 'expiring';

/** Tab and filters kept in the URL. The proposer filter stays in the page, so no user name goes into the URL. */
export interface ReviewQuery {
  tab: ReviewTab;
  company: string;
  kind: string;
  evidence: string;
  decided: string;
  sort: ReviewSort;
}

export const readQuery = (search: URLSearchParams): ReviewQuery => {
  const tab = search.get('tab') as ReviewTab;
  return {
    tab: TABS.includes(tab) ? tab : 'open',
    company: search.get('company') || '',
    kind: search.get('kind') || '',
    evidence: search.get('evidence') || '',
    decided: search.get('decided') || '',
    sort: search.get('sort') === 'expiring' ? 'expiring' : 'newest',
  };
};

export const writeQuery = (query: ReviewQuery): URLSearchParams => {
  const out = new URLSearchParams();
  if (query.tab !== 'open') out.set('tab', query.tab);
  (['company', 'kind', 'evidence', 'decided'] as const).forEach((key) => {
    if (query[key]) out.set(key, query[key]);
  });
  if (query.sort !== 'newest') out.set('sort', query.sort);
  return out;
};

/** The API refuses a bulk reject of more than this many (BULK_REJECT_MAX). */
export const BULK_REJECT_MAX = 200;

export const DECIDED_STATUSES: ProposalStatus[] = ['accepted', 'edited', 'rejected', 'expired', 'superseded', 'failed'];

export const REJECT_REASONS = [
  'Wrong record',
  'The proposed value is wrong',
  'The evidence does not support it',
  'Already up to date',
  'Duplicate of another suggestion',
  'Not worth recording',
];

export const CONFLICT_REJECT_REASON = 'Another suggestion for the same field was chosen';
