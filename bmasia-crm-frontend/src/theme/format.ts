/**
 * Display formats (no effect on stored data).
 * Dates read the same in every country: "14 Nov 2026".
 */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const formatDate = (value?: string | Date | null): string => {
  if (!value) return '—';
  let date: Date;
  if (value instanceof Date) {
    date = value;
  } else {
    // A plain "2026-11-14" is a calendar date: read it in local time so it never shifts a day.
    const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    date = plain ? new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3])) : new Date(value);
  }
  if (Number.isNaN(date.getTime())) return '—';
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
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
