/**
 * Shapes and display helpers for the company timeline
 * (GET /api/v1/companies/:id/timeline/, built in crm_app/timeline.py).
 */
import { formatDate, formatMoney } from '../../theme/format';

export type TimelineCategory =
  | 'note'
  | 'task'
  | 'email'
  | 'care'
  | 'quote'
  | 'contract'
  | 'invoice'
  | 'opportunity'
  | 'ticket'
  | 'change';

export type TimelineRecordType = 'contract' | 'quote' | 'contact' | 'opportunity' | 'ticket' | 'task' | 'invoice';

export interface TimelineActor {
  id: string | null;
  name: string;
  kind: 'user' | 'agent' | 'system';
}

export interface TimelineLink {
  type: TimelineRecordType;
  id: string;
  label: string;
  contract_id?: string;
}

export interface TimelineChange {
  field: string;
  label: string;
  kind: 'text' | 'date' | 'datetime' | 'money' | 'number' | 'bool' | 'ref' | 'collection' | 'opaque';
  old: string | null;
  new: string | null;
  /** Money: the currency after the save, and before it when the save changed it ('' = unknown). */
  currency?: string;
  old_currency?: string;
}

export interface TimelineEvent {
  id: string;
  type: string;
  category: TimelineCategory;
  occurred_at: string;
  precision: 'datetime' | 'date';
  /** Calendar day (YYYY-MM-DD) for events recorded without a time of day. */
  date?: string;
  title: string;
  detail: string;
  actor: TimelineActor | null;
  links: TimelineLink[];
  changes: TimelineChange[];
  extra: Record<string, any>;
}

export interface TimelineFacetActor extends TimelineActor {
  count: number;
}

export interface TimelinePage {
  results: TimelineEvent[];
  next_cursor: string | null;
  has_more: boolean;
  categories: { key: TimelineCategory; label: string }[];
  facets?: { types: Record<string, number>; actors: TimelineFacetActor[] };
}

export interface TimelineQuery {
  types?: TimelineCategory[];
  from?: string;
  to?: string;
  record?: { type: TimelineRecordType; id: string };
  actor?: string;
  q?: string;
  cursor?: string;
  page_size?: number;
  facets?: boolean;
}

/** Query-string parameters for the API call. */
export const timelineParams = (query: TimelineQuery): Record<string, string> => {
  const params: Record<string, string> = {};
  if (query.types && query.types.length) params.types = query.types.join(',');
  if (query.from) params.from = query.from;
  if (query.to) params.to = query.to;
  if (query.record) params.record = `${query.record.type}:${query.record.id}`;
  if (query.actor) params.actor = query.actor;
  if (query.q && query.q.trim()) params.q = query.q.trim();
  if (query.cursor) params.cursor = query.cursor;
  if (query.page_size) params.page_size = String(query.page_size);
  if (query.facets) params.facets = '1';
  return params;
};

/**
 * The business runs on Bangkok time, and the server stores date-only facts as Bangkok
 * days, so days are grouped, labelled and timed in this zone whatever the viewer's clock.
 */
export const BUSINESS_TIME_ZONE = 'Asia/Bangkok';
export const BUSINESS_TIME_ZONE_LABEL = 'Bangkok time';

const zoneParts = (d: Date): Record<string, string> => {
  const parts: Record<string, string> = {};
  new Intl.DateTimeFormat('en-GB', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
    .formatToParts(d)
    .forEach((p) => {
      parts[p.type] = p.value;
    });
  return parts;
};

/** The Bangkok calendar day of a moment, as YYYY-MM-DD. */
export const businessDay = (d: Date): string => {
  const p = zoneParts(d);
  return `${p.year}-${p.month}-${p.day}`;
};

/** Calendar day of an event in Bangkok time. Date-only events keep their recorded day. */
export const eventDay = (event: TimelineEvent): string => {
  if (event.precision === 'date' && event.date) return event.date;
  return businessDay(new Date(event.occurred_at));
};

const previousDay = (day: string): string => {
  const [y, m, d] = day.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d) - 24 * 3600 * 1000);
  return `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, '0')}-${String(t.getUTCDate()).padStart(2, '0')}`;
};

/** "Today", "Yesterday" (in Bangkok), otherwise "14 Nov 2026". */
export const dayLabel = (day: string, now: Date = new Date()): string => {
  const today = businessDay(now);
  if (day === today) return 'Today';
  if (day === previousDay(today)) return 'Yesterday';
  return formatDate(day);
};

export interface DayGroup {
  day: string;
  label: string;
  events: TimelineEvent[];
}

/** Consecutive events of the same day, in the order the server sent them (newest first). */
export const groupByDay = (events: TimelineEvent[], now: Date = new Date()): DayGroup[] => {
  const groups: DayGroup[] = [];
  events.forEach((event) => {
    const day = eventDay(event);
    const last = groups[groups.length - 1];
    if (last && last.day === day) {
      last.events.push(event);
    } else {
      groups.push({ day, label: dayLabel(day, now), events: [event] });
    }
  });
  return groups;
};

/** "just now", "5 min ago", "3 h ago", "2 days ago", "4 months ago", "2 years ago". */
export const relativeTime = (iso: string, now: Date = new Date()): string => {
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (Number.isNaN(seconds)) return '';
  if (seconds < 0) return 'in the future';
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 31) return days === 1 ? '1 day ago' : `${days} days ago`;
  const months = Math.floor(days / 30.44);
  if (months < 12) return months <= 1 ? '1 month ago' : `${months} months ago`;
  const years = Math.floor(days / 365.25);
  return years <= 1 ? '1 year ago' : `${years} years ago`;
};

/** "14 Nov 2026, 09:30 (Bangkok time)". */
export const exactTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const p = zoneParts(d);
  return `${formatDate(`${p.year}-${p.month}-${p.day}`)}, ${p.hour}:${p.minute} (${BUSINESS_TIME_ZONE_LABEL})`;
};

/** Time shown in the hover text for an event, honest about date-only records. */
export const eventExactTime = (event: TimelineEvent): string =>
  event.precision === 'date' && event.date ? `${formatDate(event.date)} (no time recorded)` : exactTime(event.occurred_at);

/** An amount with its currency when known ("THB 108,000"); a plain number when not ("108,000"). */
export const formatAmount = (amount: number | string | null | undefined, currency?: string | null): string => {
  if (currency) return formatMoney(amount, currency);
  if (amount === undefined || amount === null || amount === '') return '—';
  const n = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(n)) return String(amount);
  return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
};

const changeValue = (change: TimelineChange, value: string | null, currency?: string): string => {
  if (value === null || value === '') return 'empty';
  if (change.kind === 'date') return formatDate(value);
  if (change.kind === 'datetime') return exactTime(value) || value;
  if (change.kind === 'money') return formatAmount(value, currency);
  if (change.kind === 'number') return formatAmount(value, null);
  return value;
};

/** "Changed End date from 31 Dec 2026 to 31 Dec 2027". */
export const changeSentence = (change: TimelineChange): string => {
  if (change.kind === 'collection' || change.kind === 'opaque') return `Changed ${change.label}`;
  const oldCurrency = change.old_currency ?? change.currency;
  return `Changed ${change.label} from ${changeValue(change, change.old, oldCurrency)} to ${changeValue(
    change,
    change.new,
    change.currency
  )}`;
};

/** Where a link opens in the app; null when the record has no page of its own. */
export const linkHref = (link: TimelineLink): string | null => {
  switch (link.type) {
    case 'contract':
      return `/contracts/${link.id}`;
    case 'quote':
      return `/quotes/${link.id}`;
    case 'opportunity':
      return `/opportunities/${link.id}`;
    case 'ticket':
      return `/tickets/${link.id}`;
    case 'task':
      return `/tasks/${link.id}`;
    case 'invoice':
      // Invoices have no page of their own: open their contract, or the list searched for the number.
      return link.contract_id ? `/contracts/${link.contract_id}` : `/invoices?q=${encodeURIComponent(link.label)}`;
    default:
      return null; // contacts open in the side panel of the company page
  }
};

/** A short second line for some event types: an amount, a status, who it is assigned to. */
export const eventSummary = (event: TimelineEvent): string | null => {
  const parts: string[] = [];
  const money = event.extra?.money;
  if (money && money.amount !== undefined && money.amount !== null) {
    parts.push(formatAmount(money.amount, money.currency));
  }
  if (event.category === 'email' && event.extra?.email_type_label) parts.push(event.extra.email_type_label);
  if (event.category === 'care' && event.extra?.outcome && event.extra.outcome !== 'none') {
    parts.push(event.extra.outcome_label);
  }
  if (event.type === 'task_created' && event.extra?.assigned_to) parts.push(`Assigned to ${event.extra.assigned_to}`);
  if (event.extra?.is_private) parts.push('Private');
  if (event.extra?.is_internal) parts.push('Internal');
  if (event.extra?.reason) parts.push(event.extra.reason);
  return parts.length ? parts.join(' · ') : null;
};

/** Detail longer than the two lines shown under an event. */
export const isLongDetail = (detail?: string | null): boolean => {
  const text = (detail || '').trim();
  return text.length > 160 || text.split('\n').length > 2;
};

/** Whether an event has more to show than its collapsed form: field changes or a long detail. */
export const hasMore = (event: TimelineEvent): boolean =>
  Boolean((event.changes && event.changes.length) || isLongDetail(event.detail));
