/**
 * Plain rules for the Review page: labels, field rules that mirror the API, text safety checks,
 * grouping and URL state. No React here, so all of it is unit-tested directly.
 */
import { formatDate } from '../../theme';
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

/** Characters that change how text displays without showing themselves (bidi controls, zero-width, BOM, soft hyphen). */
const INVISIBLE_CHARS =
  '\\u00AD\\u061C\\u115F\\u1160\\u180E\\u200B-\\u200F\\u202A-\\u202E\\u2060-\\u2064\\u2066-\\u206F\\u3164\\uFEFF\\uFFA0';
const CONTROL_CHARS = '\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F\\u007F-\\u009F\\u2028\\u2029';
const INVISIBLE = new RegExp(`[${INVISIBLE_CHARS}]`);
const CONTROL = new RegExp(`[${CONTROL_CHARS}]`);
const CONTROL_OR_INVISIBLE_GLOBAL = new RegExp(`[${CONTROL_CHARS}${INVISIBLE_CHARS}]`, 'g');

export const hasInvisible = (text: string): boolean => INVISIBLE.test(text) || CONTROL.test(text);

export interface TextSegment {
  text: string;
  /** The code point, for characters shown as a visible marker instead of themselves. */
  hidden?: string;
}

/** Splits text so invisible and control characters can be shown as visible markers ("U+202E"). */
export const segmentText = (text: string): TextSegment[] => {
  const out: TextSegment[] = [];
  let last = 0;
  CONTROL_OR_INVISIBLE_GLOBAL.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CONTROL_OR_INVISIBLE_GLOBAL.exec(text)) !== null) {
    if (match.index > last) out.push({ text: text.slice(last, match.index) });
    const code = match[0].charCodeAt(0).toString(16).toUpperCase().padStart(4, '0');
    out.push({ text: '', hidden: `U+${code}` });
    last = match.index + match[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
};

const scriptTest = (script: string): RegExp | null => {
  try {
    return new RegExp(`\\p{Script=${script}}`, 'u');
  } catch {
    return null; // very old browser: the check is skipped, the server's warning still shows
  }
};
const LOOKALIKE_SCRIPTS = ['Latin', 'Cyrillic', 'Greek', 'Armenian'].map((s) => [s, scriptTest(s)] as const);

/** Scripts whose letters look alike, when more than one appears in one value (e.g. Latin "a" next to the Cyrillic U+0430). */
export const lookalikeScripts = (text: string): string[] => {
  const found = LOOKALIKE_SCRIPTS.filter(([, re]) => re && re.test(text)).map(([name]) => name);
  return found.length > 1 ? found : [];
};

/** A link only from an explicit URL field, only http(s), never anything that merely looks like one. */
export const safeHttpUrl = (value?: string | null): string | null => {
  if (!value || typeof value !== 'string') return null;
  if (!/^https?:\/\//.test(value) || hasInvisible(value) || /\s/.test(value)) return null;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
};

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
export const groupProposals = (rows: ChangeProposal[]): CompanyGroup[] => {
  const sorted = [...rows].sort(
    (a, b) => evidenceTime(b) - evidenceTime(a) || b.created_at.localeCompare(a.created_at),
  );
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

/** Mixed-script warnings for one field: from the API when it sends them, else from the local check. */
export const fieldWarnings = (p: ChangeProposal, key: string, value: string): string[] => {
  const out: string[] = [];
  const fromApi = (p.warnings || []).filter((w) => !w.field || w.field === key).map((w) => w.code);
  const ms = p.mixed_script;
  const apiMixed =
    fromApi.includes('mixed_script') ||
    ms === true ||
    (Array.isArray(ms) && ms.includes(key)) ||
    (ms && typeof ms === 'object' && !Array.isArray(ms) && key in ms);
  if (apiMixed || lookalikeScripts(value).length) out.push('mixed_script');
  if (hasInvisible(value)) out.push('invisible');
  return out;
};

// ------------------------------------------------------------------ URL state

export type ReviewTab = 'open' | 'look' | 'decided';
export const TABS: ReviewTab[] = ['open', 'look', 'decided'];

export interface ReviewQuery {
  tab: ReviewTab;
  company: string;
  kind: string;
  proposer: string;
  evidence: string;
  decided: string;
}

export const readQuery = (search: URLSearchParams): ReviewQuery => {
  const tab = search.get('tab') as ReviewTab;
  return {
    tab: TABS.includes(tab) ? tab : 'open',
    company: search.get('company') || '',
    kind: search.get('kind') || '',
    proposer: search.get('proposer') || '',
    evidence: search.get('evidence') || '',
    decided: search.get('decided') || '',
  };
};

export const writeQuery = (query: ReviewQuery): URLSearchParams => {
  const out = new URLSearchParams();
  if (query.tab !== 'open') out.set('tab', query.tab);
  (['company', 'kind', 'proposer', 'evidence', 'decided'] as const).forEach((key) => {
    if (query[key]) out.set(key, query[key]);
  });
  return out;
};

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
