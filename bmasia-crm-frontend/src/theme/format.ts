/**
 * Display formats (no effect on stored data).
 * Dates read the same in every country: "14 Nov 2026".
 */
export const formatDate = (value?: string | Date | null): string => {
  if (!value) return '—';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};

/** "THB 108,000" / "USD 4,450": currency code first, no decimals for whole amounts. */
export const formatMoney = (amount?: number | string | null, currency: string = 'USD'): string => {
  if (amount === undefined || amount === null || amount === '') return '—';
  const n = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(n)) return '—';
  const hasCents = Math.round(n * 100) % 100 !== 0;
  return `${currency} ${n.toLocaleString('en-US', {
    minimumFractionDigits: hasCents ? 2 : 0,
    maximumFractionDigits: 2,
  })}`;
};

/**
 * Adds amounts per currency and never across currencies.
 * Returns [currency, total] pairs sorted by currency code, e.g. [["THB", 108000], ["USD", 4450]].
 */
export const totalsByCurrency = (
  items: { amount?: number | string | null; currency?: string | null }[]
): [string, number][] => {
  const totals: Record<string, number> = {};
  items.forEach(({ amount, currency }) => {
    const n = Number(amount || 0);
    if (Number.isNaN(n)) return;
    const cur = currency || 'USD';
    totals[cur] = (totals[cur] || 0) + n;
  });
  return Object.entries(totals).sort(([a], [b]) => a.localeCompare(b));
};
