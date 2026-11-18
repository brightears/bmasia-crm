import type { RenewalRow, RenewalStateKey } from '../services/renewals';

/**
 * Filtering, sorting, totals and CSV for the Renewals page. Display only: the renewal
 * state of every row comes from the server and is never worked out here.
 */

/** The order states are listed in (filters, sort): from "needs work" to "done". */
export const STATE_ORDER: RenewalStateKey[] = [
  'not_started',
  'drafted',
  'sent',
  'renewed_unlinked',
  'signed',
  'invoiced',
  'paid',
  'auto_renews',
  'lapsed',
  'lost',
];

export type ProductFilter = '' | 'Soundtrack' | 'Beat Breeze' | 'Other';
export const PRODUCT_FILTERS: ProductFilter[] = ['', 'Soundtrack', 'Beat Breeze', 'Other'];

export interface RowFilters {
  states: RenewalStateKey[];
  attentionOnly: boolean;
  product: ProductFilter;
  search: string;
}

/** "a,b" from the address -> known state keys only (unknown ones are dropped). */
export const parseStates = (value: string): RenewalStateKey[] =>
  value
    .split(',')
    .map((s) => s.trim())
    .filter((s): s is RenewalStateKey => (STATE_ORDER as string[]).includes(s));

const norm = (text: string | null | undefined) =>
  (text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();

export function filterRows(rows: RenewalRow[], f: RowFilters): RenewalRow[] {
  const q = norm(f.search.trim());
  return rows.filter((r) => {
    if (f.states.length && !f.states.includes(r.renewal.state)) return false;
    if (f.attentionOnly && !r.renewal.attention) return false;
    if (f.product && r.product !== f.product) return false;
    if (q) {
      const hay = [
        r.company,
        r.corporate_group,
        r.property_name,
        r.contract_number,
        r.renewal.successor?.contract_number,
      ]
        .map(norm)
        .join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export const SORT_KEYS = [
  'company',
  'contract',
  'product',
  'zones',
  'end',
  'value',
  'state',
  'renewal',
  'change',
  'owner',
] as const;
export type SortKey = typeof SORT_KEYS[number];

/** Allowed values of ?sort=: '' (needs action first, then end date), 'end', '-end', ... */
export const SORT_VALUES: string[] = ['', ...SORT_KEYS.flatMap((k) => [k, `-${k}`])];

const sortValue = (r: RenewalRow, key: SortKey): string | number | null => {
  switch (key) {
    case 'company':
      return norm(r.company);
    case 'contract':
      return r.contract_number;
    case 'product':
      return r.product;
    case 'zones':
      return r.zones;
    case 'end':
      return r.end_date;
    case 'value':
      return r.value;
    case 'state':
      return STATE_ORDER.indexOf(r.renewal.state);
    case 'renewal':
      return r.renewal.successor?.contract_number ?? null;
    case 'change':
      return r.renewal.value_change;
    case 'owner':
      return r.owner ? norm(r.owner) : null;
    default:
      return null;
  }
};

/**
 * Sorts a copy. '' keeps the server's order (rows that need action first, then by end date).
 * Empty values always go last; ties keep the server's order.
 */
export function sortRows(rows: RenewalRow[], sort: string): RenewalRow[] {
  if (!sort) return rows.slice();
  const desc = sort.startsWith('-');
  const key = (desc ? sort.slice(1) : sort) as SortKey;
  if (!(SORT_KEYS as readonly string[]).includes(key)) return rows.slice();
  return rows
    .map((row, index) => ({ row, index, v: sortValue(row, key) }))
    .sort((a, b) => {
      if (a.v === null && b.v === null) return a.index - b.index;
      if (a.v === null) return 1;
      if (b.v === null) return -1;
      const cmp = typeof a.v === 'number' && typeof b.v === 'number' ? a.v - b.v : String(a.v).localeCompare(String(b.v));
      if (cmp !== 0) return desc ? -cmp : cmp;
      return a.index - b.index;
    })
    .map((x) => x.row);
}

export interface CurrencySummary {
  currency: string;
  terms: number;
  value: number;
  renewed: number;
  renewedValue: number;
  open: number;
  atRiskValue: number;
  lost: number;
  lostValue: number;
  auto: number;
  autoValue: number;
  /** Renewed terms divided by terms ending, leaving out auto-renewing terms. Null when nothing to divide by. */
  rate: number | null;
}

/** Totals per currency of the rows given (current term values). Never adds currencies together. */
export function summarize(rows: RenewalRow[]): CurrencySummary[] {
  const by: Record<string, CurrencySummary> = {};
  rows.forEach((r) => {
    const cur = r.currency || 'USD';
    const s = (by[cur] = by[cur] || {
      currency: cur,
      terms: 0,
      value: 0,
      renewed: 0,
      renewedValue: 0,
      open: 0,
      atRiskValue: 0,
      lost: 0,
      lostValue: 0,
      auto: 0,
      autoValue: 0,
      rate: null,
    });
    const v = Number(r.value) || 0;
    s.terms += 1;
    s.value += v;
    switch (r.renewal.group) {
      case 'renewed':
        s.renewed += 1;
        s.renewedValue += v;
        break;
      case 'open':
        s.open += 1;
        s.atRiskValue += v;
        break;
      case 'lost':
        s.lost += 1;
        s.lostValue += v;
        break;
      case 'auto':
        s.auto += 1;
        s.autoValue += v;
        break;
    }
  });
  return Object.values(by)
    .map((s) => {
      const base = s.terms - s.auto;
      return { ...s, rate: base > 0 ? s.renewed / base : null };
    })
    .sort((a, b) => a.currency.localeCompare(b.currency));
}

/** "in 12 days", "today", "16 days ago". */
export const relativeDays = (days: number | null | undefined): string => {
  if (days === null || days === undefined) return '';
  if (days === 0) return 'today';
  const n = Math.abs(days);
  const unit = n === 1 ? 'day' : 'days';
  return days < 0 ? `in ${n} ${unit}` : `${n} ${unit} ago`;
};

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

/**
 * One CSV cell. Text that a spreadsheet would read as a formula (starting with = + - @,
 * a tab or a carriage return) gets a leading apostrophe. Numbers are written as numbers.
 */
export const csvCell = (value: string | number | boolean | null | undefined): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '';
  let text = typeof value === 'boolean' ? (value ? 'yes' : 'no') : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  if (/[",\n\r]/.test(text)) text = `"${text.replace(/"/g, '""')}"`;
  return text;
};

const ENTITY_NAMES: Record<string, string> = {
  th: 'BMAsia (Thailand) Co., Ltd.',
  hk: 'BMAsia Limited',
};

export const CSV_HEADER = [
  'Customer',
  'Corporate group',
  'Country',
  'Contract',
  'Property',
  'Product',
  'Zones',
  'Zones source',
  'Term start',
  'Term end',
  'Days from end',
  'Currency',
  'Current value',
  'Renewal state',
  'Needs attention',
  'Renewal contract',
  'Renewal status',
  'Renewal currency',
  'New value',
  'Change',
  'Change basis',
  'Owner',
  'Billing entity',
  'Contract status',
  'Auto-renew',
];

export function rowsToCsv(rows: RenewalRow[]): string {
  const lines = [CSV_HEADER.map(csvCell).join(',')];
  rows.forEach((r) => {
    const s = r.renewal.successor;
    lines.push(
      [
        r.company,
        r.corporate_group,
        r.country,
        r.contract_number,
        r.property_name,
        r.product,
        r.zones,
        r.zones_source === 'contracted_zone_count' ? 'company funnel count' : 'service locations',
        r.start_date,
        r.end_date,
        r.days_from_end,
        r.currency,
        r.value,
        r.renewal.label,
        r.renewal.attention_label,
        s?.contract_number,
        s?.status,
        s?.currency,
        s ? s.value : null,
        r.renewal.value_change,
        r.renewal.value_change_basis === 'per_year' ? 'per year' : r.renewal.value_change_basis === 'term' ? 'per term' : '',
        r.owner,
        r.entity ? ENTITY_NAMES[r.entity] : '',
        r.status,
        r.auto_renew,
      ]
        .map(csvCell)
        .join(',')
    );
  });
  // Byte order mark so spreadsheet programs read Thai and accented names correctly.
  return `﻿${lines.join('\r\n')}\r\n`;
}
