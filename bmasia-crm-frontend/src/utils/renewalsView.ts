import type { RenewalRow, RenewalStateKey } from '../services/renewals';

/**
 * Filtering, sorting, totals and CSV for the Renewals page. Display only: the renewal
 * state of every row, the total it counts in (`summary_bucket`) and whether it counts in
 * the renewal rate (`in_rate`) come from the server and are never worked out here.
 */

/** The order states are listed in (filters, sort): from "needs work" to "done". */
export const STATE_ORDER: RenewalStateKey[] = [
  'not_started',
  'auto_unconfirmed',
  'drafted',
  'sent',
  'renewed_unlinked',
  'signed',
  'invoiced',
  'part_paid',
  'paid',
  'auto_renews',
  'live_unlinked',
  'lapsed',
  'lost',
  'placeholder',
];

export type ProductFilter = '' | 'Soundtrack' | 'Beat Breeze' | 'Other';
export const PRODUCT_FILTERS: ProductFilter[] = ['', 'Soundtrack', 'Beat Breeze', 'Other'];

export interface RowFilters {
  states: RenewalStateKey[];
  attentionOnly: boolean;
  product: ProductFilter;
  search: string;
  /** Placeholders closed by the data corrections are hidden unless this is on. */
  showPlaceholders?: boolean;
  /** Only terms that were never activated (still Sent). */
  neverActivatedOnly?: boolean;
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

export const isPlaceholder = (r: RenewalRow) => r.renewal.state === 'placeholder';

export function filterRows(rows: RenewalRow[], f: RowFilters): RenewalRow[] {
  const q = norm(f.search.trim());
  return rows.filter((r) => {
    if (isPlaceholder(r) && !f.showPlaceholders) return false;
    if (f.neverActivatedOnly && !r.never_activated) return false;
    if (f.states.length && !f.states.includes(r.renewal.state)) return false;
    if (f.attentionOnly && !r.renewal.attention) return false;
    if (f.product) {
      const shown = r.product_display || r.product;
      // 'Beat Breeze + Soundtrack' counts for either product.
      if (f.product === 'Other' ? shown !== 'Other' : !shown.split(' + ').includes(f.product)) return false;
    }
    if (q) {
      const hay = [r.company, r.corporate_group, r.property_name, r.contract_number, r.renewal.successor?.contract_number]
        .map(norm)
        .join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export const SORT_KEYS = ['company', 'contract', 'product', 'zones', 'end', 'value', 'state', 'renewal', 'change', 'owner'] as const;
export type SortKey = typeof SORT_KEYS[number];

/** Allowed values of ?sort=: '' (needs action first, then end date), 'end', '-end', ... */
export const SORT_VALUES: string[] = ['', ...SORT_KEYS.flatMap((k) => [k, `-${k}`])];

type SortValue = string | number | null | [string, number | null];

const sortValue = (r: RenewalRow, key: SortKey): SortValue => {
  switch (key) {
    case 'company':
      return norm(r.company);
    case 'contract':
      return r.contract_number;
    case 'product':
      return r.product_display || r.product;
    case 'zones':
      return r.zones;
    case 'end':
      return r.end_date;
    case 'value':
      // Money sorts by currency first, then amount: THB and USD are never compared as numbers.
      return [r.currency, r.value];
    case 'state':
      return STATE_ORDER.indexOf(r.renewal.state);
    case 'renewal':
      return r.renewal.successor?.contract_number ?? null;
    case 'change':
      return r.renewal.value_change === null ? null : [r.currency, r.renewal.value_change];
    case 'owner':
      return r.owner ? norm(r.owner) : null;
    default:
      return null;
  }
};

const compareScalar = (a: string | number, b: string | number) =>
  typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b));

const compareValues = (a: Exclude<SortValue, null>, b: Exclude<SortValue, null>): number => {
  if (Array.isArray(a) && Array.isArray(b)) {
    const byCurrency = a[0].localeCompare(b[0]);
    if (byCurrency !== 0) return byCurrency;
    return compareScalar(a[1] ?? 0, b[1] ?? 0);
  }
  return compareScalar(a as string | number, b as string | number);
};

/**
 * Sorts a copy. '' keeps the server's order (rows that need action first, then by end date).
 * Empty values always go last; ties keep the server's order. Money sorts by currency, then
 * amount; in descending order the currencies keep their order and the amounts reverse.
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
      if (Array.isArray(a.v) && Array.isArray(b.v) && a.v[0] !== b.v[0]) return a.v[0].localeCompare(b.v[0]);
      const cmp = compareValues(a.v, b.v);
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
  /** What the renewals are worth: the renewal contracts' values, in their own currency. */
  renewedValue: number;
  open: number;
  atRiskValue: number;
  lost: number;
  lostValue: number;
  auto: number;
  autoValue: number;
  /** Terms whose company has a live term that is not linked: probably renewed, not counted as lost. */
  unlinked: number;
  /** Lapsed 2025 placeholder terms: last year's records, not counted as lost. */
  history: number;
  /** Terms counted in the rate (decided, or ended without a renewal). */
  rateBase: number;
  rateRenewed: number;
  /** rateRenewed / rateBase; null when nothing has been decided or has ended yet. */
  rate: number | null;
}

const emptySummary = (currency: string): CurrencySummary => ({
  currency,
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
  unlinked: 0,
  history: 0,
  rateBase: 0,
  rateRenewed: 0,
  rate: null,
});

/**
 * Totals per currency of the rows given. Never adds currencies together. Placeholders count
 * nowhere; a renewal's value is added in the renewal's own currency.
 */
export function summarize(rows: RenewalRow[]): CurrencySummary[] {
  const by: Record<string, CurrencySummary> = {};
  const bucketOf = (cur: string) => (by[cur] = by[cur] || emptySummary(cur));
  rows.forEach((r) => {
    if (r.renewal.summary_bucket === 'excluded' && isPlaceholder(r)) return;
    const s = bucketOf(r.currency || 'USD');
    const v = Number(r.value) || 0;
    s.terms += 1;
    s.value += v;
    switch (r.renewal.summary_bucket) {
      case 'renewed': {
        s.renewed += 1;
        const succ = r.renewal.successor;
        if (succ) bucketOf(succ.currency || s.currency).renewedValue += Number(succ.value) || 0;
        break;
      }
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
      case 'unlinked':
        s.unlinked += 1;
        break;
      case 'history':
        s.history += 1;
        break;
    }
    if (r.renewal.in_rate) {
      s.rateBase += 1;
      if (r.renewal.summary_bucket === 'renewed') s.rateRenewed += 1;
    }
  });
  return Object.values(by)
    .map((s) => ({ ...s, rate: s.rateBase > 0 ? s.rateRenewed / s.rateBase : null }))
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
  'Product source',
  'Zones',
  'Zones source',
  'Term start',
  'Term end',
  'Term months',
  '2025 placeholder term',
  'Days from end (positive = ended, negative = days to go)',
  'Currency',
  'Annual value',
  'Renewal state',
  'Needs attention',
  'Renewal contract',
  'Renewal status',
  'Renewal link',
  'Renewal start',
  'Gap before renewal (days)',
  'Renewal currency',
  'New annual value',
  'Annual change',
  'Add-on',
  'Never activated',
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
        r.product_display || r.product,
        r.product_source === 'service_locations' ? 'service locations' : 'renewal book',
        r.zones,
        r.zones_source === 'contracted_zone_count' ? 'company funnel count' : 'service locations',
        r.start_date,
        r.end_date,
        r.term_months,
        r.term_2025_placeholder,
        r.days_from_end,
        r.currency,
        r.value,
        r.renewal.label,
        r.renewal.attention_label,
        s?.contract_number,
        s?.status,
        s?.link,
        s?.start_date,
        s?.gap_days,
        s?.currency,
        s ? s.value : null,
        r.renewal.value_change,
        r.is_addon,
        r.never_activated,
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
