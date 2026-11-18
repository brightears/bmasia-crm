"""Header parsing for captured mail. Pure functions: no database, no network.

Input is a message in Gmail API shape (``users.messages.get`` with
``format=metadata`` or ``format=full``). Header values may arrive folded and
with RFC 2047 encoded words still in place; both are handled. Nothing here
raises on bad input: a header that cannot be parsed is recorded in
``ParsedMessage.defects`` and the message is still returned.
"""
import base64
import binascii
import email.header
import email.policy
import email.utils
import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone


MAX_SUBJECT = 300
MAX_NAME = 200
MAX_ADDRESS = 320
MAX_MESSAGE_ID = 500
MAX_BODY_CHARS = 64 * 1024

# Headers the sync engine asks Gmail for with format=metadata.
# X-BMAsia-Email-ID is set by crm_app.services.email_service on mail the CRM sends.
METADATA_HEADERS = (
    'From', 'To', 'Cc', 'Reply-To', 'Subject', 'Date', 'Message-ID', 'In-Reply-To',
    'References', 'List-Id', 'Auto-Submitted', 'Precedence', 'X-BMAsia-Email-ID',
)

_FOLD_RE = re.compile(r'\r?\n[ \t]*')
_ANGLE_ID_RE = re.compile(r'<([^<>\s]+)>')
_ENCODED_WORD_RE = re.compile(r'=\?[^?\s]+\?[bBqQ]\?[^?\s]*\?=')
_REPLY_PREFIX_RE = re.compile(
    r'^\s*(?:(?:re|aw|sv|vs|antw|fw|fwd|wg|tr|rv|ตอบกลับ|ส่งต่อ)\s*(?:\[\d+\])?\s*[:：]\s*'
    r'|\[(?:ext|external)\]\s*)',
    re.IGNORECASE,
)
_WS_RE = re.compile(r'\s+')
_TAG_RE = re.compile(r'<[^>]+>')
_STYLE_RE = re.compile(r'<(script|style)\b.*?</\1>', re.IGNORECASE | re.DOTALL)
_QUOTE_INTRO_RE = re.compile(
    r'^(?:On .{0,200} wrote:|-{2,}\s*Original Message\s*-{2,}|_{10,}|From: .+)$',
    re.IGNORECASE,
)


# --- small helpers ---------------------------------------------------------

def unfold(value):
    """Join folded header lines (CRLF or LF followed by whitespace)."""
    if value is None:
        return ''
    return _FOLD_RE.sub(' ', str(value)).replace('\r', '').replace('\n', ' ').strip()


def decode_words(value):
    """Decode RFC 2047 encoded words; never raises. Unknown charsets degrade to
    replacement characters rather than losing the text."""
    value = unfold(value)
    if not value or not _ENCODED_WORD_RE.search(value):
        return value
    try:
        parts = email.header.decode_header(value)
    except Exception:
        return value
    try:
        text = str(email.header.make_header(parts))
    except Exception:
        # Unknown or broken charset: decode each chunk on its own, lossy but kept.
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
    return _WS_RE.sub(' ', text).strip()


def clip(value, limit):
    value = value or ''
    return value if len(value) <= limit else value[:limit]


# --- addresses -------------------------------------------------------------

@dataclass(frozen=True)
class Address:
    address: str          # lower-case, as written (plus tag kept)
    display_name: str
    domain: str           # lower-case; '' when the address has no domain
    valid: bool           # False when the address could not be parsed cleanly

    @property
    def match_key(self):
        return match_key(self.address)


def normalise_address(value):
    """Lower-case, trim, drop angle brackets and a trailing dot."""
    value = (value or '').strip().strip('<>').strip().rstrip('.').lower()
    if value.startswith('mailto:'):
        value = value[7:]
    return clip(value, MAX_ADDRESS)


def address_domain(address):
    if '@' not in address:
        return ''
    return address.rsplit('@', 1)[1].strip().rstrip('.').lower()


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


def _make_address(addr, name):
    address = normalise_address(addr)
    name = clip(decode_words(name or '').strip().strip('"').strip(), MAX_NAME)
    domain = address_domain(address)
    local = address.rsplit('@', 1)[0] if '@' in address else ''
    valid = bool(local) and bool(domain) and '.' in domain and ' ' not in address
    return Address(address=address, display_name=name, domain=domain, valid=valid)


def parse_address_list(value):
    """Parse a From/To/Cc/Reply-To value into ``Address`` objects.

    Handles folding, encoded-word display names, group syntax
    (``Team: a@x, b@y;``, members are returned, the group name is dropped),
    duplicates (first one wins) and malformed input (returned with
    ``valid=False`` rather than dropped). Never raises.
    """
    raw = unfold(value)
    if not raw:
        return []
    found = []
    try:
        header = email.policy.default.header_factory('to', raw)
        for addr in header.addresses:
            spec = addr.addr_spec or ''
            if not spec and not addr.display_name:
                continue
            found.append(_make_address(spec, addr.display_name))
    except Exception:
        found = []
    if not found:
        try:
            for name, addr in email.utils.getaddresses([raw]):
                if addr or name:
                    found.append(_make_address(addr, name))
        except Exception:
            found = []
    if not found:
        # Last resort: anything that looks like an address.
        for token in re.findall(r'[^\s<>,;:"]+@[^\s<>,;:"]+', raw):
            found.append(_make_address(token, ''))
    out, seen = [], set()
    for item in found:
        if not item.address:
            continue
        if item.address in seen:
            continue
        seen.add(item.address)
        out.append(item)
    return out


# --- message ids and conversations -----------------------------------------

def normalise_message_id(value):
    """Return the Message-ID without angle brackets and outer whitespace, case
    kept; ``''`` when there is none. Overlong ids are replaced by a hash."""
    raw = unfold(value)
    if not raw:
        return ''
    found = _ANGLE_ID_RE.search(raw)
    token = found.group(1) if found else raw.split()[0].strip('<>')
    token = token.strip()
    if not token:
        return ''
    if len(token) > MAX_MESSAGE_ID:
        token = 'long:' + hashlib.sha256(token.encode('utf-8', 'replace')).hexdigest()
    return token


def parse_id_list(value):
    """Message-ids from References or In-Reply-To, in order, de-duplicated."""
    raw = unfold(value)
    if not raw:
        return []
    ids = _ANGLE_ID_RE.findall(raw)
    if not ids:
        ids = [t.strip('<>') for t in raw.split() if '@' in t]
    out = []
    for item in ids:
        item = normalise_message_id(f'<{item}>')
        if item and item not in out:
            out.append(item)
    return out


def conversation_key(message_id, in_reply_to, references):
    """First id in References, else In-Reply-To, else the message's own id."""
    if references:
        return references[0]
    if in_reply_to:
        return in_reply_to
    return message_id


def normalise_subject(subject):
    """Subject without reply/forward prefixes, lower-case, whitespace collapsed."""
    text = decode_words(subject or '')
    previous = None
    while previous != text:
        previous = text
        text = _REPLY_PREFIX_RE.sub('', text, count=1)
    return clip(_WS_RE.sub(' ', text).strip().lower(), MAX_SUBJECT)


def is_reply_subject(subject):
    return bool(_REPLY_PREFIX_RE.match(decode_words(subject or '')))


def synthetic_message_id(from_address, date_value, subject, recipients, text=''):
    """Fallback key when a message has no Message-ID (research/11 B.2)."""
    parts = [
        from_address or '', unfold(date_value), unfold(subject),
        ','.join(sorted(recipients or ())), (text or '')[:1024],
    ]
    digest = hashlib.sha256('|'.join(parts).encode('utf-8', 'replace')).hexdigest()
    return f'synthetic:{digest}'


# --- dates -----------------------------------------------------------------

def parse_date(value):
    """Date header to an aware UTC datetime, or None."""
    raw = unfold(value)
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

def _headers_of(part):
    out = {}
    for item in (part or {}).get('headers') or ():
        name = str(item.get('name', '')).lower()
        if name:
            out.setdefault(name, []).append(item.get('value', ''))
    return out


def _b64url(data):
    if not data:
        return b''
    data = str(data)
    try:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))
    except (binascii.Error, ValueError):
        return b''


def _charset(part_headers):
    ctype = ' '.join(part_headers.get('content-type', ['']))
    found = re.search(r'charset\s*=\s*"?([A-Za-z0-9_\-:.]+)"?', ctype, re.IGNORECASE)
    return found.group(1) if found else 'utf-8'


def _decode_part_text(part):
    data = _b64url(((part or {}).get('body') or {}).get('data'))
    if not data:
        return ''
    charset = _charset(_headers_of(part))
    for candidate in (charset, 'utf-8'):
        try:
            return data.decode(candidate, errors='replace')
        except LookupError:
            continue
    return data.decode('latin-1', errors='replace')


def _walk(part):
    yield part
    for child in (part or {}).get('parts') or ():
        yield from _walk(child)


def html_to_text(value):
    value = _STYLE_RE.sub(' ', value or '')
    value = re.sub(r'<br\s*/?>|</p>|</div>|</tr>', '\n', value, flags=re.IGNORECASE)
    value = _TAG_RE.sub(' ', value)
    value = html.unescape(value)
    lines = [_WS_RE.sub(' ', line).strip() for line in value.splitlines()]
    return '\n'.join(line for line in lines if line)


def strip_quoted(text):
    """Drop quoted history: lines starting with '>' and everything after a
    reply introduction such as 'On ... wrote:'."""
    kept = []
    for line in (text or '').splitlines():
        stripped = line.strip()
        if _QUOTE_INTRO_RE.match(stripped):
            break
        if stripped.startswith('>'):
            continue
        kept.append(line.rstrip())
    while kept and not kept[-1].strip():
        kept.pop()
    return '\n'.join(kept).strip()


def extract_body_text(payload, limit=MAX_BODY_CHARS):
    """Plain text of a ``format=full`` payload: text/plain preferred, else
    text/html converted; quoted history stripped; capped at ``limit``."""
    plain, rich = [], []
    for part in _walk(payload or {}):
        mime = str(part.get('mimeType', '')).lower()
        if part.get('filename'):
            continue
        if mime == 'text/plain':
            plain.append(_decode_part_text(part))
        elif mime == 'text/html':
            rich.append(_decode_part_text(part))
    if plain:
        text = '\n'.join(plain)
    elif rich:
        text = html_to_text('\n'.join(rich))
    else:
        text = ''
    return clip(strip_quoted(text), limit)


def attachment_metadata(payload, gmail_id=''):
    """Filename, type, size and Gmail ids of each attachment; inline images skipped."""
    out = []
    for part in _walk(payload or {}):
        filename = part.get('filename') or ''
        body = part.get('body') or {}
        if not filename or not body.get('attachmentId'):
            continue
        headers = _headers_of(part)
        disposition = ' '.join(headers.get('content-disposition', [''])).lower()
        mime = str(part.get('mimeType', '')).lower()
        if mime.startswith('image/') and disposition.startswith('inline'):
            continue
        out.append({
            'filename': clip(decode_words(filename), 255),
            'mime_type': clip(mime, 100),
            'size': int(body.get('size') or 0),
            'gmail_message_id': gmail_id,
            'attachment_id': str(body.get('attachmentId'))[:512],
        })
    return out


# --- the parsed message ----------------------------------------------------

@dataclass
class ParsedMessage:
    gmail_id: str
    gmail_thread_id: str
    label_ids: list
    internal_date: object
    message_id: str
    message_id_synthetic: bool
    in_reply_to: str
    references: list
    conversation_key: str
    subject: str
    subject_normalised: str
    is_reply: bool
    sent_at: object
    from_address: object               # Address or None
    to: list = field(default_factory=list)
    cc: list = field(default_factory=list)
    reply_to: list = field(default_factory=list)
    list_id: str = ''
    precedence: str = ''
    auto_submitted: str = ''
    crm_email_id: str = ''
    attachments: list = field(default_factory=list)
    defects: list = field(default_factory=list)

    @property
    def has_attachments(self):
        return bool(self.attachments)

    def participants(self):
        """(role, Address) pairs; duplicates within a role removed."""
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


def _first(headers, name):
    values = headers.get(name.lower()) or []
    return values[0] if values else ''


def parse_gmail_message(message):
    """Turn a Gmail API message dict into a ``ParsedMessage``. Never raises."""
    message = message or {}
    payload = message.get('payload') or {}
    headers = _headers_of(payload)
    defects = []

    from_list = parse_address_list(_first(headers, 'From'))
    if len(headers.get('from', [])) > 1:
        defects.append('several From headers')
    from_address = from_list[0] if from_list else None
    if from_address is None:
        defects.append('no From address')
    elif not from_address.valid:
        defects.append('malformed From address')

    to = parse_address_list(', '.join(headers.get('to', [])))
    cc = parse_address_list(', '.join(headers.get('cc', [])))
    reply_to = parse_address_list(_first(headers, 'Reply-To'))
    for group in (to, cc, reply_to):
        if any(not a.valid for a in group):
            defects.append('malformed recipient address')
            break

    raw_subject = _first(headers, 'Subject')
    subject = clip(decode_words(raw_subject), MAX_SUBJECT)
    date_value = _first(headers, 'Date')
    sent_at = parse_date(date_value)
    gmail_internal = internal_date(message.get('internalDate'))
    if sent_at is None:
        if date_value:
            defects.append('unparseable Date')
        sent_at = gmail_internal

    message_id = normalise_message_id(_first(headers, 'Message-ID'))
    synthetic = False
    if not message_id:
        recipients = [a.address for a in to + cc]
        message_id = synthetic_message_id(
            from_address.address if from_address else '', date_value, raw_subject, recipients,
        )
        synthetic = True
        defects.append('no Message-ID')

    references = parse_id_list(' '.join(headers.get('references', [])))
    in_reply_to_ids = parse_id_list(_first(headers, 'In-Reply-To'))
    in_reply_to = in_reply_to_ids[0] if in_reply_to_ids else ''
    references = [r for r in references if r != message_id]
    if in_reply_to == message_id:
        in_reply_to = ''

    crm_email_id = unfold(_first(headers, 'X-BMAsia-Email-ID'))[:120]

    return ParsedMessage(
        gmail_id=str(message.get('id') or '')[:64],
        gmail_thread_id=str(message.get('threadId') or '')[:64],
        label_ids=[str(x) for x in (message.get('labelIds') or [])],
        internal_date=gmail_internal,
        message_id=message_id,
        message_id_synthetic=synthetic,
        in_reply_to=in_reply_to,
        references=references,
        conversation_key=conversation_key(message_id, in_reply_to, references),
        subject=subject,
        subject_normalised=normalise_subject(raw_subject),
        is_reply=is_reply_subject(raw_subject),
        sent_at=sent_at,
        from_address=from_address,
        to=to,
        cc=cc,
        reply_to=reply_to,
        list_id=unfold(_first(headers, 'List-Id'))[:200],
        precedence=unfold(_first(headers, 'Precedence'))[:40],
        auto_submitted=unfold(_first(headers, 'Auto-Submitted'))[:40],
        crm_email_id=crm_email_id,
        attachments=attachment_metadata(payload, str(message.get('id') or '')),
        defects=defects,
    )
