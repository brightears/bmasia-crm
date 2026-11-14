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
