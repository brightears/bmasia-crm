import { CurrencyTotal, RevenueTrendPoint } from '../types';
import { currencyForEntity, formatCurrency } from '../constants/entities';
import { formatMoney } from '../theme';

/**
 * Dashboard money, one line per currency. Works with both API shapes:
 * - newer responses carry `*_by_currency` lists: each currency is shown on its own line and
 *   nothing is added across currencies;
 * - older responses only have the single total, shown as before in the entity's currency.
 */

/** The entity's own currency always first (as 0 when it has nothing), then the others A–Z. */
const withEntityFirst = (rows: CurrencyTotal[], entity: string) => {
  const own = currencyForEntity(entity);
  const all = rows.some((r) => r.currency === own) ? rows : [{ currency: own, total: '0' }, ...rows];
  return [...all].sort((a, b) => (a.currency === own ? -1 : b.currency === own ? 1 : a.currency.localeCompare(b.currency)));
};

const roundedTotal = (row: CurrencyTotal) => Math.round(Number(row.total));

/** Display lines for one money figure, e.g. ["THB 108,000", "USD 2,160"]. */
export function moneyLines(byCurrency: CurrencyTotal[] | undefined, fallback: number | null | undefined, entity: string): string[] {
  if (!Array.isArray(byCurrency)) return [formatCurrency(Number(fallback ?? 0), entity)];
  return withEntityFirst(byCurrency, entity).map((row) => formatMoney(roundedTotal(row), row.currency || '—'));
}

/** Same as moneyLines, for a figure that is subtracted (churn): a minus sign on non-zero lines. */
export function negativeMoneyLines(byCurrency: CurrencyTotal[] | undefined, fallback: number | null | undefined, entity: string): string[] {
  const values = Array.isArray(byCurrency) ? withEntityFirst(byCurrency, entity).map(roundedTotal) : [Math.round(Number(fallback ?? 0))];
  return moneyLines(byCurrency, fallback, entity).map((line, i) => (values[i] > 0 ? `-${line}` : line));
}

/**
 * Month-on-month change in percent. With per-currency figures it compares the entity's own currency
 * only (a THB and a USD sum cannot be compared as one number) and says which currency it used when
 * other currencies are present.
 */
export function revenueChange(
  current: { total: number; byCurrency?: CurrencyTotal[] },
  previous: { total: number; byCurrency?: CurrencyTotal[] },
  entity: string
): { value: number; label: string } {
  // The API sends decimals as text ("0.00"), so compare numbers, not strings.
  const pct = (now: number, before: number) => (Number(before) === 0 ? 0 : ((Number(now) - Number(before)) / Number(before)) * 100);
  if (!Array.isArray(current.byCurrency) || !Array.isArray(previous.byCurrency)) {
    return { value: pct(current.total, previous.total), label: 'vs last month' };
  }
  const own = currencyForEntity(entity);
  const pick = (rows: CurrencyTotal[]) => Number(rows.find((r) => r.currency === own)?.total ?? 0);
  const mixed = [...current.byCurrency, ...previous.byCurrency].some((r) => r.currency !== own);
  return { value: pct(pick(current.byCurrency), pick(previous.byCurrency)), label: mixed ? `vs last month (${own} only)` : 'vs last month' };
}

/** Currencies in the trend's per-currency series, the entity's own first; [] for older responses. */
export function trendCurrencies(trend: RevenueTrendPoint[] | undefined, entity: string): string[] {
  if (!trend || trend.length === 0 || trend.some((p) => !Array.isArray(p.by_currency))) return [];
  const all = Array.from(new Set(trend.flatMap((p) => (p.by_currency || []).map((r) => r.currency))));
  const own = currencyForEntity(entity);
  return all.sort((a, b) => (a === own ? -1 : b === own ? 1 : a.localeCompare(b)));
}

/** The trend in one currency (numbers for the chart), or the old mixed series when currency is null. */
export function trendSeries(trend: RevenueTrendPoint[], currency: string | null): RevenueTrendPoint[] {
  if (!currency) return trend;
  return trend.map((p) => {
    const row = (p.by_currency || []).find((r) => r.currency === currency);
    const n = (v?: string) => Number(v ?? 0);
    return {
      month: p.month,
      revenue: n(row?.revenue),
      new_revenue: n(row?.new_revenue),
      renewal_revenue: n(row?.renewal_revenue),
      churned_revenue: n(row?.churned_revenue),
      net_revenue: n(row?.net_revenue),
    };
  });
}
