"""Header parsing for captured mail. Pure functions: no database, no network.

Input is a message in Gmail API shape (``users.messages.get`` with
``format=metadata`` or ``format=full``). Header values may arrive folded and
with RFC 2047 encoded words still in place; both are handled.

Hostile input is bounded before it is parsed, so one message costs at most
milliseconds and a few MB however it is built:

* every header value is cut to ``MAX_HEADER`` (Subject to ``MAX_SUBJECT_RAW``)
  before unfolding or decoding;
* at most ``MAX_ENCODED_WORDS`` encoded words are decoded per header;
* address lists are split by a linear scanner and cut at ``MAX_ADDRESSES``;
* References keeps the first id and the last ``MAX_REFERENCES_TAIL``;
* MIME is walked iteratively, at most ``MAX_MIME_DEPTH`` deep and
  ``MAX_MIME_PARTS`` parts, each text part cut to ``MAX_PART_BYTES``;
* HTML is turned into text by a linear scanner, not by regular expressions.

Every stored string is cleaned for the database (NUL removed, lone surrogates
replaced) and cut to its column limit. Anything cut or bounded is recorded in
``ParsedMessage.flags`` ('truncated', 'bounded'). Nothing here raises on bad
input: what cannot be parsed is recorded in ``ParsedMessage.defects``.
"""
import base64
import binascii
import email.header
import email.utils
import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone


# Column limits (see models.py).
MAX_SUBJECT = 300
MAX_NAME = 200
MAX_ADDRESS = 320
MAX_DOMAIN = 253
MAX_MESSAGE_ID = 500          # column is 512; longer ids are hashed
MAX_GMAIL_ID = 64
MAX_LABELS = 100
MAX_FILENAME = 255
MAX_BODY_CHARS = 64 * 1024

# Input bounds, applied before any parsing.
MAX_HEADER = 16 * 1024
MAX_SUBJECT_RAW = 2 * 1024
MAX_HEADER_ENTRIES = 500
MAX_ENCODED_WORDS = 100
MAX_ADDRESSES = 100
MAX_ADDRESS_PIECE = 1024
MAX_REFERENCES_TAIL = 20
MAX_MIME_DEPTH = 20
MAX_MIME_PARTS = 200
MAX_PART_BYTES = 512 * 1024
MAX_ATTACHMENTS = 50

# A claimed Date further than this from Gmail's internal date is flagged.
DATE_MISMATCH = timedelta(days=2)

# Headers the sync engine asks Gmail for with format=metadata.
# X-BMAsia-Email-ID is set by crm_app.services.email_service on mail the CRM sends.
METADATA_HEADERS = (
    'From', 'To', 'Cc', 'Reply-To', 'Subject', 'Date', 'Message-ID', 'In-Reply-To',
    'References', 'List-Id', 'Auto-Submitted', 'Precedence', 'X-BMAsia-Email-ID',
)

FLAG_TRUNCATED = 'truncated'      # a value was cut to its column limit
FLAG_BOUNDED = 'bounded'          # an input bound was hit; only part was read
FLAG_DATE_MISMATCH = 'date_mismatch'
FLAG_SYNTHETIC_ID = 'synthetic_id'

_FOLD_RE = re.compile(r'\r?\n[ \t]*')
_ANGLE_ID_RE = re.compile(r'<([^<>\s]+)>')
_ENCODED_WORD_RE = re.compile(r'=\?[^?\s]{1,40}\?[bBqQ]\?[^?\s]{0,2000}\?=')
_SURROGATE_RE = re.compile('[\ud800-\udfff]')
_REPLY_PREFIX_RE = re.compile(
    r'^\s*(?:(?:re|aw|sv|vs|antw|fw|fwd|wg|tr|rv|ตอบกลับ|ส่งต่อ)\s*(?:\[\d+\])?\s*[:：]\s*'
    r'|\[(?:ext|external)\]\s*)',
    re.IGNORECASE,
)
_WS_RE = re.compile(r'\s+')
_QUOTE_INTRO_RE = re.compile(
    r'^(?:On .{0,200} wrote:|-{2,}\s*Original Message\s*-{2,}|_{10,}|From: .{1,500})$',
    re.IGNORECASE,
)


class Flags(set):
    """The flags and defects collected while parsing one message."""


# --- cleaning and bounds ---------------------------------------------------

def clean(value, limit=None, flags=None):
    """A string the database accepts: NUL removed, lone surrogates replaced,
    cut to ``limit`` (recorded as 'truncated' in ``flags``)."""
    if value is None:
        return ''
    value = str(value)
    if '\x00' in value:
        value = value.replace('\x00', '')
    value = _SURROGATE_RE.sub('�', value)
    if limit is not None and len(value) > limit:
        value = value[:limit]
        if flags is not None:
            flags.add(FLAG_TRUNCATED)
    return value


def bound(value, limit, flags=None):
    """Cut raw input before parsing it (recorded as 'bounded')."""
    value = '' if value is None else str(value)
    if len(value) > limit:
        if flags is not None:
            flags.add(FLAG_BOUNDED)
        return value[:limit]
    return value


def clip(value, limit):
    value = value or ''
    return value if len(value) <= limit else value[:limit]


def unfold(value, limit=MAX_HEADER, flags=None):
    """Join folded header lines (CRLF or LF followed by whitespace)."""
    value = bound(value, limit, flags)
    if not value:
        return ''
    return _FOLD_RE.sub(' ', value).replace('\r', '').replace('\n', ' ').strip()


def decode_words(value, flags=None, limit=MAX_HEADER):
    """Decode RFC 2047 encoded words; never raises. At most
    ``MAX_ENCODED_WORDS`` words are decoded; unknown charsets degrade to
    replacement characters rather than losing the text."""
    value = unfold(value, limit, flags)
    if not value or '=?' not in value:
        return clean(value)
    count, cut = 0, None
    for match in _ENCODED_WORD_RE.finditer(value):
        count += 1
        if count == MAX_ENCODED_WORDS:
            cut = match.end()
            break
    if count == 0:
        return clean(value)
    if cut is not None and cut < len(value):
        value = value[:cut]
        if flags is not None:
            flags.add(FLAG_BOUNDED)
    try:
        parts = email.header.decode_header(value)
    except Exception:
        return clean(value)
    try:
        text = str(email.header.make_header(parts))
    except Exception:
        pieces = []
        for chunk, charset in parts:
            if isinstance(chunk, str):
                pieces.append(chunk)
                continue
            decoded = None
            for candidate in (charset, 'utf-8'):
                if not candidate:
                    continue
                try:
                    decoded = chunk.decode(candidate, errors='replace')
                    break
                except (LookupError, TypeError):
                    continue
            pieces.append(decoded if decoded is not None else chunk.decode('latin-1', 'replace'))
        text = ''.join(pieces)
    return clean(_WS_RE.sub(' ', text).strip())


# --- addresses -------------------------------------------------------------

@dataclass(frozen=True)
class Address:
    address: str          # lower-case, as written (plus tag kept); never the display name
    display_name: str
    domain: str           # lower-case ASCII (IDN as punycode); '' when there is none
    valid: bool           # False when the address could not be parsed cleanly

    @property
    def match_key(self):
        return match_key(self.address)


def _ascii_domain(domain):
    if not domain or domain.isascii():
        return domain
    try:
        return domain.encode('idna').decode('ascii')
    except (UnicodeError, ValueError):
        return domain


def normalise_address(value, flags=None):
    """Lower-case, trim, drop angle brackets, 'mailto:' and a trailing dot;
    the domain as ASCII; cut to the column limits."""
    value = clean(value).strip().strip('<>').strip().rstrip('.').lower()
    if value.startswith('mailto:'):
        value = value[7:]
    if '@' in value:
        local, domain = value.rsplit('@', 1)
        domain = clean(_ascii_domain(domain.strip().rstrip('.')), MAX_DOMAIN, flags)
        value = f'{local}@{domain}'
    return clean(value, MAX_ADDRESS, flags)


def address_domain(address):
    if '@' not in address:
        return ''
    return clip(address.rsplit('@', 1)[1].strip().rstrip('.').lower(), MAX_DOMAIN)


def match_key(address):
    """Key used to compare addresses: lower-case, plus-addressing removed.

    ``Name+tag@Example.com`` and ``name@example.com`` give the same key.
    """
    address = normalise_address(address)
    if '@' not in address:
        return address
    local, domain = address.rsplit('@', 1)
    local = local.split('+', 1)[0] if '+' in local and not local.startswith('+') else local
    return f'{local}@{domain}'


def _make_address(addr, name, flags=None):
    address = normalise_address(addr, flags)
    name = clean(decode_words(name or '', flags).strip().strip('"').replace('\\"', '"').strip(),
                 MAX_NAME, flags)
    domain = address_domain(address)
    local = address.rsplit('@', 1)[0] if '@' in address else ''
    valid = (bool(local) and '@' not in local and bool(domain) and '.' in domain
             and ' ' not in address and '"' not in address)
    return Address(address=address, display_name=name, domain=domain, valid=valid)


def _split_address_list(raw, flags=None):
    """Split on ',' and ';' outside quotes, comments and angle brackets; drop
    group names ('Team:'). Linear in the input; at most ``MAX_ADDRESSES``."""
    pieces, buf = [], []
    quote = esc = False
    angle = paren = 0
    for ch in raw:
        if esc:
            buf.append(ch)
            esc = False
            continue
        if quote:
            if ch == '\\':
                esc = True
            elif ch == '"':
                quote = False
            buf.append(ch)
            continue
        if ch == '"':
            quote = True
        elif ch == '(':
            paren += 1
        elif ch == ')' and paren:
            paren -= 1
        elif ch == '<' and not paren:
            angle += 1
        elif ch == '>' and angle and not paren:
            angle -= 1
        elif not paren and not angle and ch in ',;':
            piece = ''.join(buf).strip()
            if piece:
                pieces.append(piece)
                if len(pieces) >= MAX_ADDRESSES:
                    if flags is not None:
                        flags.add(FLAG_BOUNDED)
                    return pieces
            buf = []
            continue
        elif not paren and not angle and ch == ':':
            buf = []          # a group name ends here
            continue
        buf.append(ch)
    piece = ''.join(buf).strip()
    if piece:
        pieces.append(piece)
    return pieces


_ANGLE_RE = re.compile(r'<([^<>]*)>')
_COMMENT_RE = re.compile(r'\([^()]*\)')


def _piece_to_address(piece, flags=None):
    piece = bound(piece.strip(), MAX_ADDRESS_PIECE, flags)
    if not piece:
        return None
    angles = _ANGLE_RE.findall(piece)
    with_at = [a for a in angles if '@' in a]
    if angles:
        # The angle address is the address, whatever the display name says:
        # 'evil@x.test <real@y.test>' is from real@y.test.
        addr = (with_at or angles)[-1]
        name = piece[:piece.find('<')]
    else:
        text = _COMMENT_RE.sub(' ', piece)
        tokens = [t for t in text.split() if '@' in t]
        addr = tokens[-1] if tokens else text.strip()
        name = ''
    if not addr.strip() and not name.strip():
        return None
    return _make_address(addr, name, flags)


def parse_address_list(value, flags=None):
    """Parse a From/To/Cc/Reply-To value into ``Address`` objects.

    Handles folding, encoded-word display names, group syntax (members are
    returned, the group name is dropped), duplicates (first one wins) and
    malformed input (returned with ``valid=False`` rather than dropped).
    Linear in the input and bounded; never raises.
    """
    raw = unfold(value, MAX_HEADER, flags)
    if not raw:
        return []
    out, seen = [], set()
    for piece in _split_address_list(raw, flags):
        try:
            item = _piece_to_address(piece, flags)
        except Exception:
            item = None
        if item is None or not item.address or item.address in seen:
            continue
        seen.add(item.address)
        out.append(item)
    return out


# --- message ids and conversations -----------------------------------------

def _hash_id(prefix, raw):
    return f'{prefix}:' + hashlib.sha256(raw.encode('utf-8', 'replace')).hexdigest()


def normalise_message_id(value):
    """The canonical form of an RFC 5322 Message-ID (see ``identity.py``).

    1. Unfold and take the first ``<...>`` token without whitespace inside;
       remove the angle brackets and surrounding whitespace; keep the case.
    2. A value without such a token but without whitespace is used as is
       (angle brackets stripped).
    3. Anything else that is not empty (``<a b@x.test>``) becomes
       ``raw:<sha256 of the unfolded value>``, so different malformed ids never
       collide.
    4. An id longer than ``MAX_MESSAGE_ID`` becomes ``long:<sha256>``.
    NUL and lone surrogates are removed first. Returns '' when there is none.
    """
    raw = clean(unfold(value, 4096)).strip()
    if not raw:
        return ''
    found = _ANGLE_ID_RE.search(raw)
    if found:
        token = found.group(1).strip()
    elif not any(c.isspace() for c in raw):
        token = raw.strip('<>').strip()
    else:
        return _hash_id('raw', raw)
    if not token:
        return _hash_id('raw', raw)
    if len(token) > MAX_MESSAGE_ID:
        return _hash_id('long', token)
    return token


def parse_id_list(value, flags=None):
    """Message-ids from References or In-Reply-To, in order, de-duplicated;
    the first id and the last ``MAX_REFERENCES_TAIL`` are kept. An over-long
    header is read from its first KB and its last part, where the root and
    the most recent parents are."""
    value = '' if value is None else str(value)
    if len(value) > MAX_HEADER:
        value = value[:1024] + ' ' + value[-(MAX_HEADER - 1024):]
        if flags is not None:
            flags.add(FLAG_BOUNDED)
    raw = unfold(value, MAX_HEADER + 1, flags)
    if not raw:
        return []
    ids = _ANGLE_ID_RE.findall(raw)
    if not ids:
        ids = [t.strip('<>') for t in raw.split() if '@' in t]
    out, seen = [], set()
    for item in ids:
        item = normalise_message_id(f'<{item}>')
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    if len(out) > MAX_REFERENCES_TAIL + 1:
        out = out[:1] + out[-MAX_REFERENCES_TAIL:]
        if flags is not None:
            flags.add(FLAG_BOUNDED)
    return out


def conversation_key(message_id, in_reply_to, references):
    """First id in References, else In-Reply-To, else the message's own id."""
    if references:
        return references[0]
    if in_reply_to:
        return in_reply_to
    return message_id


def normalise_subject(subject, flags=None):
    """Subject without reply/forward prefixes, lower-case, whitespace collapsed."""
    text = decode_words(subject or '', flags, MAX_SUBJECT_RAW)
    for _ in range(20):
        new = _REPLY_PREFIX_RE.sub('', text, count=1)
        if new == text:
            break
        text = new
    return clean(_WS_RE.sub(' ', text).strip().lower(), MAX_SUBJECT)


def is_reply_subject(subject):
    return bool(_REPLY_PREFIX_RE.match(decode_words(subject or '', None, MAX_SUBJECT_RAW)))


def synthetic_message_id(from_address, date_value, subject, recipients, internal=None,
                         in_reply_to='', references=()):
    """Fallback key for a message without a usable Message-ID.

    Built only from what every mailbox sees the same way: sender, sorted To/Cc,
    subject, the claimed Date, In-Reply-To and References, plus Gmail's
    internal date rounded down to the minute.

    Limits, stated honestly: two different messages with identical headers
    received within the same minute still share a key (the second is seen as
    a copy of the first); and the same message received by two mailboxes on
    either side of a minute boundary gets two keys (stored twice). The Gmail
    thread id is per mailbox, so it cannot be part of a cross-mailbox key.
    """
    minute = ''
    if internal is not None:
        minute = internal.replace(second=0, microsecond=0).isoformat()
    parts = [
        from_address or '', unfold(date_value, 512), unfold(subject, MAX_SUBJECT_RAW),
        ','.join(sorted(recipients or ())), in_reply_to or '', ' '.join(references or ()), minute,
    ]
    digest = hashlib.sha256('|'.join(parts).encode('utf-8', 'replace')).hexdigest()
    return f'synthetic:{digest}'


# --- dates -----------------------------------------------------------------

def parse_date(value):
    """Date header to an aware UTC datetime, or None. This is what the sender
    claims; Gmail's internal date is the trusted clock."""
    raw = unfold(value, 512)
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    try:
        return parsed.astimezone(dt_timezone.utc)
    except (OverflowError, ValueError):
        return None


def internal_date(value):
    """Gmail ``internalDate`` (epoch milliseconds as a string) to a datetime."""
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(millis / 1000, tz=dt_timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


# --- classification --------------------------------------------------------

def domain_in(domain, domains):
    """True when ``domain`` is one of ``domains`` or a subdomain of one."""
    domain = (domain or '').lower()
    if not domain:
        return False
    for item in domains:
        if domain == item or domain.endswith('.' + item):
            return True
    return False


def is_internal(address, internal_domains, internal_addresses=()):
    """An address in our own domains, or one of our extra sending addresses."""
    if not address:
        return False
    if address.address in internal_addresses or address.match_key in internal_addresses:
        return True
    return domain_in(address.domain, internal_domains)


# --- MIME ------------------------------------------------------------------

def _headers_of(part, flags=None):
    out = {}
    headers = (part or {}).get('headers') or ()
    if not isinstance(headers, (list, tuple)):
        return out
    for index, item in enumerate(headers):
        if index >= MAX_HEADER_ENTRIES:
            if flags is not None:
                flags.add(FLAG_BOUNDED)
            break
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '')[:100].lower()
        if name:
            out.setdefault(name, []).append(item.get('value') or '')
    return out


def _b64url(data, limit=MAX_PART_BYTES):
    if not data:
        return b''
    data = str(data)[: (limit * 4) // 3 + 8]
    try:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))[:limit]
    except (binascii.Error, ValueError):
        return b''


def _charset(part_headers):
    ctype = ' '.join(str(v) for v in part_headers.get('content-type', ['']))[:1000]
    found = re.search(r'charset\s*=\s*"?([A-Za-z0-9_\-:.]{1,40})"?', ctype, re.IGNORECASE)
    return found.group(1) if found else 'utf-8'


def _decode_part_text(part):
    body = (part or {}).get('body') or {}
    data = _b64url(body.get('data') if isinstance(body, dict) else None)
    if not data:
        return ''
    charset = _charset(_headers_of(part))
    for candidate in (charset, 'utf-8'):
        try:
            text = data.decode(candidate, errors='replace')
            return clean(text)
        except (LookupError, TypeError, ValueError):
            continue
    return clean(data.decode('latin-1', errors='replace'))


def walk_parts(payload, flags=None):
    """The MIME parts of a payload, iteratively, depth-first in document
    order, at most ``MAX_MIME_DEPTH`` deep and ``MAX_MIME_PARTS`` parts."""
    if not isinstance(payload, dict):
        return
    stack = [(payload, 0)]
    seen = 0
    while stack:
        part, depth = stack.pop()
        seen += 1
        if seen > MAX_MIME_PARTS:
            if flags is not None:
                flags.add(FLAG_BOUNDED)
            return
        yield part
        children = part.get('parts') or ()
        if not isinstance(children, (list, tuple)) or not children:
            continue
        if depth + 1 > MAX_MIME_DEPTH:
            if flags is not None:
                flags.add(FLAG_BOUNDED)
            continue
        for child in reversed(children[:MAX_MIME_PARTS]):
            if isinstance(child, dict):
                stack.append((child, depth + 1))


_SKIP_TAGS = {'script', 'style', 'head', 'title'}
_BREAK_TAGS = {'br', 'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'table'}
# '<' then anything but '<' or '>', then '>': it cannot overlap itself, so the
# scan is linear even on a run of unclosed '<' (the old '<[^>]+>' was not).
_TAG_SCAN_RE = re.compile(r'<(/?)\s*+([A-Za-z][A-Za-z0-9]*+)?[^<>]*+>')  # possessive: no backtracking
MAX_HTML_CHARS = 128 * 1024


def html_to_text(value):
    """Visible text of HTML in one linear scan. Script and style content is
    dropped; block tags become line breaks. At most ``MAX_HTML_CHARS`` read
    (the stored text is capped at 64 KB anyway)."""
    value = (value or '')[:MAX_HTML_CHARS]
    out = []
    pos = 0
    skipping = None
    for match in _TAG_SCAN_RE.finditer(value):
        start = match.start()
        if skipping is None and start > pos:
            out.append(value[pos:start])
        pos = match.end()
        closing, name = match.group(1), (match.group(2) or '').lower()
        if skipping is not None:
            if closing and name == skipping:
                skipping = None
        elif name in _SKIP_TAGS and not closing and value[pos - 2] != '/':
            skipping = name
        else:
            out.append('\n' if name in _BREAK_TAGS else ' ')
    if skipping is None and pos < len(value):
        tail = value[pos:]
        cut = tail.find('<')
        out.append(tail if cut == -1 else tail[:cut])
    text = html.unescape(''.join(out))
    lines = [_WS_RE.sub(' ', line).strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)


def strip_quoted(text):
    """Drop quoted history: lines starting with '>' and everything after a
    reply introduction such as 'On ... wrote:'."""
    kept = []
    for line in (text or '').splitlines():
        stripped = line.strip()
        if len(stripped) <= 600 and _QUOTE_INTRO_RE.match(stripped):
            break
        if stripped.startswith('>'):
            continue
        kept.append(line.rstrip())
    while kept and not kept[-1].strip():
        kept.pop()
    return '\n'.join(kept).strip()


def extract_body_text(payload, limit=MAX_BODY_CHARS, flags=None):
    """Plain text of a ``format=full`` payload: text/plain preferred, else
    text/html converted; quoted history stripped; capped at ``limit``.
    Bounded and iterative; never raises."""
    plain, rich = [], []
    size = 0
    try:
        for part in walk_parts(payload or {}, flags):
            mime = str(part.get('mimeType', '')).lower()[:100]
            if part.get('filename'):
                continue
            if mime not in ('text/plain', 'text/html'):
                continue
            text = _decode_part_text(part)
            size += len(text)
            (plain if mime == 'text/plain' else rich).append(text)
            if size > 4 * MAX_PART_BYTES:
                if flags is not None:
                    flags.add(FLAG_BOUNDED)
                break
        if plain:
            text = '\n'.join(plain)
        elif rich:
            text = html_to_text('\n'.join(rich))
        else:
            text = ''
        return clean(strip_quoted(text), limit, flags)
    except Exception:
        if flags is not None:
            flags.add('body_unreadable')
        return ''


def attachment_metadata(payload, gmail_id='', flags=None):
    """Filename, type, size and Gmail ids of each attachment; inline images skipped."""
    out = []
    for part in walk_parts(payload or {}, flags):
        filename = part.get('filename') or ''
        body = part.get('body') or {}
        if not filename or not isinstance(body, dict) or not body.get('attachmentId'):
            continue
        headers = _headers_of(part)
        disposition = ' '.join(str(v) for v in headers.get('content-disposition', ['']))[:200].lower()
        mime = str(part.get('mimeType', '')).lower()
        if mime.startswith('image/') and disposition.startswith('inline'):
            continue
        try:
            size = int(body.get('size') or 0)
        except (TypeError, ValueError):
            size = 0
        out.append({
            'filename': clean(decode_words(filename, flags, 1024), MAX_FILENAME, flags),
            'mime_type': clean(mime, 100),
            'size': max(0, min(size, 2 ** 40)),
            'gmail_message_id': clean(gmail_id, MAX_GMAIL_ID),
            'attachment_id': clean(body.get('attachmentId'), 512),
        })
        if len(out) >= MAX_ATTACHMENTS:
            if flags is not None:
                flags.add(FLAG_BOUNDED)
            break
    return out


# --- the parsed message ----------------------------------------------------

@dataclass
class ParsedMessage:
    gmail_id: str
    gmail_thread_id: str
    label_ids: list
    internal_date: object             # Gmail's clock: the trusted time
    message_id: str
    message_id_synthetic: bool
    in_reply_to: str
    references: list
    conversation_key: str
    subject: str
    subject_normalised: str
    is_reply: bool
    sent_at: object                   # internal date (or the claimed date if Gmail gave none)
    claimed_date: object              # the Date header, as claimed by the sender
    from_address: object              # Address or None
    to: list = field(default_factory=list)
    cc: list = field(default_factory=list)
    reply_to: list = field(default_factory=list)
    list_id: str = ''
    precedence: str = ''
    auto_submitted: str = ''
    crm_email_id: str = ''
    attachments: list = field(default_factory=list)
    defects: list = field(default_factory=list)
    flags: set = field(default_factory=set)

    @property
    def has_attachments(self):
        return bool(self.attachments)

    @property
    def sent_label(self):
        """Gmail's SENT label on this mailbox's copy: sent from this mailbox."""
        return 'SENT' in self.label_ids

    def participants(self):
        """(role, Address) pairs; Bcc is never read."""
        out = []
        if self.from_address is not None:
            out.append(('from', self.from_address))
        for role, items in (('to', self.to), ('cc', self.cc), ('reply_to', self.reply_to)):
            for item in items:
                out.append((role, item))
        return out

    def addresses(self):
        seen, out = set(), []
        for _, item in self.participants():
            if item.address not in seen:
                seen.add(item.address)
                out.append(item)
        return out

    @property
    def is_bulk(self):
        """Mailing lists, bulk senders and auto-replies are never captured."""
        if self.list_id:
            return True
        if self.precedence.lower() in ('bulk', 'list', 'junk'):
            return True
        auto = self.auto_submitted.lower()
        return bool(auto) and auto != 'no'

    def sorted_flags(self):
        return sorted(self.flags)


def _first(headers, name):
    values = headers.get(name.lower()) or []
    return values[0] if values else ''


def parse_gmail_message(message):
    """Turn a Gmail API message dict into a ``ParsedMessage``. Never raises."""
    try:
        return _parse(message if isinstance(message, dict) else {})
    except Exception:
        # Last line of defence: a message we cannot read at all still gets a
        # stable key, so it is counted as malformed and never silently lost.
        message = message if isinstance(message, dict) else {}
        gid = clean(message.get('id'), MAX_GMAIL_ID)
        key = _hash_id('unreadable', f'{gid}|{message.get("internalDate")}')
        return ParsedMessage(
            gmail_id=gid, gmail_thread_id='', label_ids=[], internal_date=None,
            message_id=key, message_id_synthetic=True, in_reply_to='', references=[],
            conversation_key=key, subject='', subject_normalised='', is_reply=False,
            sent_at=None, claimed_date=None, from_address=None,
            defects=['unreadable message'], flags={FLAG_SYNTHETIC_ID},
        )


def _parse(message):
    payload = message.get('payload') or {}
    if not isinstance(payload, dict):
        payload = {}
    flags = Flags()
    headers = _headers_of(payload, flags)
    defects = []

    from_list = parse_address_list(_first(headers, 'From'), flags)
    if len(headers.get('from', [])) > 1:
        defects.append('several From headers')
    from_address = from_list[0] if from_list else None
    if from_address is None:
        defects.append('no From address')
    elif not from_address.valid:
        defects.append('malformed From address')

    to = parse_address_list(', '.join(str(v) for v in headers.get('to', [])[:5]), flags)
    cc = parse_address_list(', '.join(str(v) for v in headers.get('cc', [])[:5]), flags)
    reply_to = parse_address_list(_first(headers, 'Reply-To'), flags)
    for group in (to, cc, reply_to):
        if any(not a.valid for a in group):
            defects.append('malformed recipient address')
            break

    raw_subject = bound(_first(headers, 'Subject'), MAX_SUBJECT_RAW, flags)
    subject = clean(decode_words(raw_subject, flags, MAX_SUBJECT_RAW), MAX_SUBJECT, flags)
    date_value = bound(_first(headers, 'Date'), 512, flags)
    claimed = parse_date(date_value)
    gmail_internal = internal_date(message.get('internalDate'))
    if claimed is None and date_value:
        defects.append('unparseable Date')
    if claimed is not None and gmail_internal is not None and abs(claimed - gmail_internal) > DATE_MISMATCH:
        flags.add(FLAG_DATE_MISMATCH)
    sent_at = gmail_internal or claimed

    references = parse_id_list(' '.join(str(v) for v in headers.get('references', [])[:5]), flags)
    in_reply_to_ids = parse_id_list(_first(headers, 'In-Reply-To'), flags)
    in_reply_to = in_reply_to_ids[0] if in_reply_to_ids else ''

    message_id = normalise_message_id(_first(headers, 'Message-ID'))
    synthetic = False
    if not message_id:
        recipients = [a.address for a in to + cc]
        message_id = synthetic_message_id(
            from_address.address if from_address else '', date_value, raw_subject, recipients,
            gmail_internal, in_reply_to, references,
        )
        synthetic = True
        flags.add(FLAG_SYNTHETIC_ID)
        defects.append('no Message-ID')

    references = [r for r in references if r != message_id]
    if in_reply_to == message_id:
        in_reply_to = ''

    label_ids = message.get('labelIds') or []
    if not isinstance(label_ids, (list, tuple)):
        label_ids = []
    if len(label_ids) > MAX_LABELS:
        flags.add(FLAG_BOUNDED)
    label_ids = [clean(x, MAX_GMAIL_ID) for x in label_ids[:MAX_LABELS]]
    gmail_id = clean(message.get('id'), MAX_GMAIL_ID)

    return ParsedMessage(
        gmail_id=gmail_id,
        gmail_thread_id=clean(message.get('threadId'), MAX_GMAIL_ID),
        label_ids=label_ids,
        internal_date=gmail_internal,
        message_id=message_id,
        message_id_synthetic=synthetic,
        in_reply_to=in_reply_to,
        references=references,
        conversation_key=conversation_key(message_id, in_reply_to, references),
        subject=subject,
        subject_normalised=normalise_subject(raw_subject, flags),
        is_reply=is_reply_subject(raw_subject),
        sent_at=sent_at,
        claimed_date=claimed,
        from_address=from_address,
        to=to,
        cc=cc,
        reply_to=reply_to,
        list_id=clean(unfold(_first(headers, 'List-Id'), 1024), 200),
        precedence=clean(unfold(_first(headers, 'Precedence'), 200), 40),
        auto_submitted=clean(unfold(_first(headers, 'Auto-Submitted'), 200), 40),
        crm_email_id=clean(unfold(_first(headers, 'X-BMAsia-Email-ID'), 512), 120),
        attachments=attachment_metadata(payload, gmail_id, flags),
        defects=defects,
        flags=set(flags),
    )
