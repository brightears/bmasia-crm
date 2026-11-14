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
 * Two-letter initials for an avatar. Uses Latin letters and digits when there are any
 * ("Lumen Bay Resort" -> "LB"); otherwise the first character of the name, so Thai and
 * other scripts still get a letter instead of an empty avatar.
 */
export const initialsOf = (name?: string | null): string => {
  const text = (name || '').trim();
  if (!text) return '?';
  const latin = text
    .replace(/[^A-Za-z0-9 ]/g, ' ')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase();
  return latin || Array.from(text)[0];
};
