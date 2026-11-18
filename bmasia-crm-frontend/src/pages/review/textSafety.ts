/**
 * Checks on text a proposal supplies, so a value cannot display differently from what would be
 * saved: invisible and control characters, unusual spaces, look-alike alphabets, mixed writing
 * directions, and links that hide where they go. Display only; the server decides what it accepts.
 *
 * Code points are listed as numbers and the patterns are built at run time, so the source itself
 * holds no invisible characters.
 */

const BS = String.fromCharCode(92);
type Range = [number, number?];
const cls = (ranges: Range[]) =>
  ranges
    .map(([a, b]) =>
      b === undefined ? `${BS}u{${a.toString(16)}}` : `${BS}u{${a.toString(16)}}-${BS}u{${b.toString(16)}}`,
    )
    .join('');

/** Format, zero-width, filler, variation-selector and tag characters: they show nothing or a blank. */
const INVISIBLE_RANGES: Range[] = [
  [0xad],
  [0x34f],
  [0x61c],
  [0x115f, 0x1160],
  [0x17b4, 0x17b5],
  [0x180b, 0x180f],
  [0x200b, 0x200f],
  [0x202a, 0x202e],
  [0x2060, 0x2064],
  [0x2066, 0x206f],
  [0x2800],
  [0x3164],
  [0xfe00, 0xfe0f],
  [0xfeff],
  [0xffa0],
  [0xfff9, 0xfffb],
  [0x1bca0, 0x1bca3],
  [0x1d173, 0x1d17a],
  [0xe0000, 0xe007f],
  [0xe0100, 0xe01ef],
];
const CONTROL_RANGES: Range[] = [
  [0x0, 0x8],
  [0xb, 0xc],
  [0xe, 0x1f],
  [0x7f, 0x9f],
  [0x2028, 0x2029],
];
/** Spaces that look like an ordinary space but are not one. */
const SPACE_RANGES: Range[] = [[0xa0], [0x1680], [0x2000, 0x200a], [0x202f], [0x205f], [0x3000]];

const re = (source: string, flags = 'u'): RegExp | null => {
  try {
    return new RegExp(source, flags);
  } catch {
    return null; // a very old browser: the check is skipped; the server's own checks still apply
  }
};

const INVISIBLE = re(`[${cls(INVISIBLE_RANGES)}]`);
const CONTROL = re(`[${cls(CONTROL_RANGES)}]`);
const SPACE = re(`[${cls(SPACE_RANGES)}]`);
const ANY_MARKED = re(`[${cls(CONTROL_RANGES)}${cls(INVISIBLE_RANGES)}${cls(SPACE_RANGES)}]`, 'gu');

export const hasInvisible = (text: string): boolean =>
  Boolean((INVISIBLE && INVISIBLE.test(text)) || (CONTROL && CONTROL.test(text)));

/** Non-breaking and other unusual spaces, leading or trailing spaces, or a run of spaces. */
export const hasUnusualSpaces = (text: string): boolean =>
  Boolean((SPACE && SPACE.test(text)) || /^\s|\s$/.test(text) || / {2,}/.test(text));

export interface TextSegment {
  text: string;
  /** Shown as a visible marker instead of the character: "U+202E", or "\u2423" for an edge space. */
  marker?: string;
  kind?: 'invisible' | 'space' | 'edge';
}

const hex = (cp: number) => `U+${cp.toString(16).toUpperCase().padStart(4, '0')}`;

/**
 * Splits text so invisible, control and unusual-space characters show as markers. With `edges`,
 * ordinary spaces at the start and end of a value show as "\u2423" too.
 */
export const segmentText = (text: string, edges = false): TextSegment[] => {
  const out: TextSegment[] = [];
  let body = text;
  let lead = 0;
  let trail = 0;
  if (edges) {
    lead = /^ */.exec(body)![0].length;
    body = body.slice(lead);
    trail = / *$/.exec(body)![0].length;
    body = body.slice(0, body.length - trail);
  }
  for (let i = 0; i < lead; i += 1) out.push({ text: '', marker: '\u2423', kind: 'edge' });
  if (!ANY_MARKED) {
    if (body) out.push({ text: body });
  } else {
    let last = 0;
    ANY_MARKED.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = ANY_MARKED.exec(body)) !== null) {
      if (match.index > last) out.push({ text: body.slice(last, match.index) });
      const cp = match[0].codePointAt(0) || 0;
      const isSpace = Boolean(SPACE && SPACE.test(match[0]));
      out.push({ text: '', marker: hex(cp), kind: isSpace ? 'space' : 'invisible' });
      last = match.index + match[0].length;
    }
    if (last < body.length) out.push({ text: body.slice(last) });
  }
  for (let i = 0; i < trail; i += 1) out.push({ text: '', marker: '\u2423', kind: 'edge' });
  return out;
};

const script = (name: string) => re(`${BS}p{Script=${name}}`);
const LOOKALIKE = ['Latin', 'Cyrillic', 'Greek', 'Armenian'].map((s) => [s, script(s)] as const);
const RTL = re(
  `[${['Hebrew', 'Arabic', 'Syriac', 'Thaana', 'Nko', 'Samaritan', 'Mandaic', 'Adlam'].map((s) => `${BS}p{Script=${s}}`).join('')}]`,
);
const LTR_LETTER_OR_DIGIT = re(
  `[${BS}p{Script=Latin}${BS}p{Script=Cyrillic}${BS}p{Script=Greek}${BS}p{Script=Thai}0-9]`,
);

/** Alphabets whose letters look alike, when more than one appears in one value (a Latin a next to a Cyrillic one). */
export const lookalikeScripts = (text: string): string[] => {
  const found = LOOKALIKE.filter(([, pattern]) => pattern && pattern.test(text)).map(([name]) => name);
  return found.length > 1 ? found : [];
};

/** Right-to-left letters together with left-to-right letters or digits: the order on screen can differ. */
export const mixesDirections = (text: string): boolean =>
  Boolean(RTL && LTR_LETTER_OR_DIGIT && RTL.test(text) && LTR_LETTER_OR_DIGIT.test(text));

// ------------------------------------------------------------------ links

/** Second-level suffixes under which the registrable name has three labels (example.co.th). */
const TWO_LEVEL = new Set([
  'co.th',
  'ac.th',
  'go.th',
  'in.th',
  'or.th',
  'co.uk',
  'org.uk',
  'ac.uk',
  'com.au',
  'net.au',
  'org.au',
  'com.hk',
  'org.hk',
  'com.sg',
  'com.my',
  'co.id',
  'co.jp',
  'co.kr',
  'com.cn',
  'com.vn',
  'com.ph',
  'co.nz',
  'co.in',
  'com.tw',
]);

export interface LinkInfo {
  /** Set only when the address may be shown as a link. */
  href: string | null;
  host: string;
  /** The part of the host that names who owns it (example.com in mail.example.com). */
  registrable: string;
  /** The part before it ("mail."). */
  prefix: string;
  /** Why it is not shown as a link. */
  refused?: string;
  /** "Open in Gmail" only for exactly mail.google.com, otherwise "Open link". */
  label: string;
}

const IPV4 = /^\d{1,3}(\.\d{1,3}){3}$/;

/**
 * Whether a URL from an explicit URL field may be shown as a link, and the host to print next to it.
 * Refused: anything but lowercase http(s), a user name or password, '@' in the address part,
 * punycode or non-ASCII hosts, invisible characters or spaces.
 */
export const describeLink = (value?: string | null): LinkInfo | null => {
  if (!value || typeof value !== 'string') return null;
  const refuse = (reason: string, host = ''): LinkInfo => ({
    href: null,
    host,
    registrable: host,
    prefix: '',
    refused: reason,
    label: '',
  });
  if (!/^https?:\/\//.test(value)) return refuse('not an http or https address');
  if (hasInvisible(value) || /\s/.test(value)) return refuse('hidden characters or spaces in the address');
  const authority = value.replace(/^https?:\/\//, '').split(/[/?#]/)[0];
  if (authority.includes('@')) return refuse('the address contains a user name or an @ before the host');
  if (/[^\x21-\x7e]/.test(authority)) return refuse('the host uses non-ASCII letters');
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return refuse('not a valid address');
  }
  const host = url.hostname.toLowerCase();
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return refuse('not an http or https address', host);
  if (url.username || url.password) return refuse('the address contains a user name or password', host);
  if (host.split('.').some((label) => label.startsWith('xn--'))) return refuse('the host is written in punycode', host);
  if (!host || host.includes('@')) return refuse('not a valid host', host);
  // A trailing dot ("example.com.") is the same host; it must not make "com." look like the owner.
  const bare = host.replace(/\.+$/, '');
  const labels = bare.split('.');
  const n = IPV4.test(bare) ? labels.length : TWO_LEVEL.has(labels.slice(-2).join('.')) ? 3 : 2;
  const registrable = labels.slice(-n).join('.');
  const prefix = labels.length > n ? `${labels.slice(0, -n).join('.')}.` : '';
  return {
    href: url.href,
    host,
    registrable,
    prefix,
    label: host === 'mail.google.com' ? 'Open in Gmail' : 'Open link',
  };
};

/** Kept for callers that only need a yes/no: the href when the link may be shown. */
export const safeHttpUrl = (value?: string | null): string | null => describeLink(value)?.href ?? null;
