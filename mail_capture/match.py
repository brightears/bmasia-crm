"""The deterministic matcher (research/11 B.7 "Matching").

``match_message`` is a pure function of a parsed message and a ``Snapshot``
of CRM reference data, so it can be re-run whenever a contact, domain or rule
changes. It reads nothing and writes nothing. Order, first decisive rule wins:

1. Classify participants. Every participant internal: skip. A never-log rule
   with a drop action: skip. A headers-only rule is remembered.
2. Exact contact email (case-insensitive, plus-addressing ignored). An
   address on contacts of more than one company is not decided: the result
   is ``ambiguous`` with every candidate company proposed.
   2b. Mail the CRM itself sent (an ``EmailLog`` row, resolved before
   matching, only for a copy with Gmail's SENT label and only when the log's
   recipient is among the message's To/Cc) links to that row's company.
3. Document numbers in the subject (and body when stored) in the CRM's
   numbering, shown here with the impossible year 99: TH-CT99001, HK-QT99001,
   TH-IV99001, INV-TH-2099-0001, REC-HK-2099-0001 and the older
   BMAT-99-C-0001 / BMAL-99-C-0001 contract form. When rule 2 already
   decided, a number of the same company is linked automatically and one of
   another company is only proposed.
4. Thread inheritance: a conversation a person confirmed to a company, but
   only when an external participant is on one of that company's domains. A
   stranger on the thread (a forward to an outsider, a reply from someone
   unknown) gets the company only as a low-confidence proposal (ambiguous).
5. Company domain: a non-freemail domain on exactly one company matches
   with medium confidence. A shared domain (marked shared, or on more than one
   company) never matches; its ranked candidates go to the queue.
6. Nothing: unmatched (queue row, headers only, never a body).

Links a person rejected for the conversation are never proposed again.

Direction comes from Gmail, not from the From header: ``outbound`` needs the
SENT label on the copy being processed; a From that only claims an internal
sender is ``claimed_internal``.
"""
import re
from dataclasses import dataclass, field

from . import rules as capture_rules
from .parse import is_internal


# --- document numbers ------------------------------------------------------

_DOC_PATTERNS = (
    # DocumentSequence numbers: {TH|HK}-{CT|QT|IV}{yy}{seq:03d}
    ('contract', re.compile(r'(?<![A-Za-z0-9])(TH|HK)[-\s]?CT\s?(\d{5,})(?![0-9])', re.I),
     lambda m: f'{m.group(1).upper()}-CT{m.group(2)}'),
    ('quote', re.compile(r'(?<![A-Za-z0-9])(TH|HK)[-\s]?QT\s?(\d{5,})(?![0-9])', re.I),
     lambda m: f'{m.group(1).upper()}-QT{m.group(2)}'),
    ('invoice', re.compile(r'(?<![A-Za-z0-9])(TH|HK)[-\s]?IV\s?(\d{5,})(?![0-9])', re.I),
     lambda m: f'{m.group(1).upper()}-IV{m.group(2)}'),
    # Invoice and receipt numbers made by the invoice views: INV-TH-2099-0001
    ('invoice', re.compile(r'(?<![A-Za-z0-9])INV[-\s]?(TH|HK)[-\s]?(\d{4})[-\s]?(\d{4,})(?![0-9])', re.I),
     lambda m: f'INV-{m.group(1).upper()}-{m.group(2)}-{m.group(3)}'),
    ('receipt', re.compile(r'(?<![A-Za-z0-9])REC[-\s]?(TH|HK)[-\s]?(\d{4})[-\s]?(\d{4,})(?![0-9])', re.I),
     lambda m: f'REC-{m.group(1).upper()}-{m.group(2)}-{m.group(3)}'),
    # Older contract form still in the database: BMAT-99-C-0001 / BMAL-99-C-0001
    ('contract', re.compile(r'(?<![A-Za-z0-9])(BMA[TL])[-\s]?(\d{2})[-\s]?C[-\s]?(\d{3,})(?![0-9])', re.I),
     lambda m: f'{m.group(1).upper()}-{m.group(2)}-C-{m.group(3)}'),
)


def find_document_numbers(text):
    """[(kind, normalised number)] in order of first appearance, no repeats.

    kind is contract, quote, invoice or receipt (a receipt number belongs to an
    invoice). Draft numbers (DRAFT-0001) are never matched.
    """
    found, seen = [], set()
    if not text:
        return found
    hits = []
    for kind, pattern, normalise in _DOC_PATTERNS:
        for m in pattern.finditer(text):
            hits.append((m.start(), kind, normalise(m)))
    for _, kind, number in sorted(hits):
        if number not in seen:
            seen.add(number)
            found.append((kind, number))
    return found


# --- snapshot --------------------------------------------------------------

@dataclass(frozen=True)
class ContactRef:
    contact_id: str
    company_id: str


@dataclass(frozen=True)
class DomainRef:
    company_id: str
    shared_group_domain: bool = False


@dataclass(frozen=True)
class DocRef:
    target_type: str     # contract | quote | invoice
    target_id: str
    company_id: str
    number: str


@dataclass(frozen=True)
class CrmSentRef:
    email_log_id: str
    company_id: str
    documents: tuple = ()   # ((target_type, target_id), ...)


@dataclass(frozen=True)
class Snapshot:
    """Reference data for one batch. Keys are lower-case."""

    internal_domains: tuple
    internal_addresses: tuple = ()
    contacts: dict = field(default_factory=dict)            # match key -> (ContactRef, ...)
    domains: dict = field(default_factory=dict)             # domain -> (DomainRef, ...)
    documents: dict = field(default_factory=dict)           # number -> (DocRef, ...)
    confirmed_conversations: dict = field(default_factory=dict)  # conversation key -> company id
    rejected: dict = field(default_factory=dict)            # conversation key -> {(type, id)}
    shared_domain_ranking: dict = field(default_factory=dict)    # domain -> (company id, ...)
    crm_sent: dict = field(default_factory=dict)            # rfc message id -> CrmSentRef
    rules: tuple = ()
    extra_freemail: frozenset = frozenset()


# --- result ----------------------------------------------------------------

SKIP_INTERNAL = 'skip_internal'
SKIP_RULE = 'skip_rule'
MATCHED = 'matched'
AMBIGUOUS = 'ambiguous'
UNMATCHED = 'unmatched'
MALFORMED = 'malformed'


@dataclass(frozen=True)
class Link:
    target_type: str
    target_id: str
    method: str
    confidence: str
    status: str          # auto | proposed
    detail: tuple = ()   # ((key, value), ...) kept hashable

    def detail_dict(self):
        return dict(self.detail)


@dataclass
class MatchResult:
    decision: str
    direction: str = 'inbound'
    company_id: str = None
    method: str = ''
    confidence: str = ''
    rule_action: str = None
    contacts: dict = field(default_factory=dict)       # address -> contact id
    companies: tuple = ()           # every company matched at message level
    links: list = field(default_factory=list)
    candidates: tuple = ()
    unmatched_reason: str = ''
    queue_addresses: tuple = ()     # external Address objects for the unmatched queue
    new_contact_candidates: tuple = ()   # ((Address, company id), ...)
    email_log_id: str = None

    @property
    def stores_message(self):
        return self.decision in (MATCHED, AMBIGUOUS)


def _add_link(links, link):
    for existing in links:
        if (existing.target_type, existing.target_id) == (link.target_type, link.target_id):
            return
    links.append(link)


def _priority(parsed, internal_flags, direction):
    """External participants in the order that decides the primary company:
    the sender for inbound mail, the recipients (To, Cc) for outbound."""
    ordered = []
    roles = ('from', 'reply_to', 'to', 'cc') if direction == 'inbound' \
        else ('to', 'cc', 'reply_to', 'from')
    by_role = {}
    for role, item in parsed.participants():
        by_role.setdefault(role, []).append(item)
    seen = set()
    for role in roles:
        for item in by_role.get(role, []):
            if internal_flags.get(item.address) or item.address in seen:
                continue
            seen.add(item.address)
            ordered.append(item)
    return ordered


def message_direction(parsed, internal_domains, internal_addresses=(), sent=None):
    """outbound (SENT label on this copy), claimed_internal (From claims one
    of our addresses, unverified) or inbound."""
    if sent is None:
        sent = parsed.sent_label
    if sent:
        return 'outbound'
    sender = parsed.from_address
    if sender is not None and is_internal(sender, internal_domains, internal_addresses):
        return 'claimed_internal'
    return 'inbound'


def match_message(parsed, snapshot, mailbox_id=None, conversation_key=None, body_text='', sent=None):
    """Match one ``parse.ParsedMessage`` against ``snapshot``. Pure.

    ``sent`` is whether this mailbox's copy carries Gmail's SENT label
    (defaults to the parsed copy's labels)."""
    conversation_key = conversation_key or parsed.conversation_key
    rejected = snapshot.rejected.get(conversation_key, frozenset())
    addresses = parsed.addresses()
    internal_flags = {
        a.address: is_internal(a, snapshot.internal_domains, snapshot.internal_addresses)
        for a in addresses
    }
    sender = parsed.from_address
    direction = message_direction(parsed, snapshot.internal_domains, snapshot.internal_addresses, sent)

    # 1. classify
    if not addresses:
        return MatchResult(decision=MALFORMED, direction=direction)
    externals = _priority(parsed, internal_flags, direction)
    # Recipients past the address cap (a cheap scan of the whole header): they
    # count for never-log rules and for matching, never for the queue.
    listed = externals
    seen = {a.address for a in addresses}
    extra = [
        a for a in getattr(parsed, 'overflow', ()) or ()
        if a.address not in seen
        and not is_internal(a, snapshot.internal_domains, snapshot.internal_addresses)
    ]
    externals = listed + extra
    if not externals:
        return MatchResult(decision=SKIP_INTERNAL, direction=direction)
    action = capture_rules.message_rule_action(
        addresses + list(getattr(parsed, 'overflow', ()) or ()), snapshot.rules, mailbox_id)
    if action in (capture_rules.ACTION_SKIP, capture_rules.ACTION_PRIVATE):
        return MatchResult(decision=SKIP_RULE, direction=direction, rule_action=action)

    result = MatchResult(decision='', direction=direction, rule_action=action)
    links = result.links

    def allowed(target_type, target_id):
        return (target_type, str(target_id)) not in rejected

    # 2. exact contact email
    per_address = {}
    for item in externals:
        refs = snapshot.contacts.get(item.match_key) or snapshot.contacts.get(item.address) or ()
        refs = tuple(r for r in refs if allowed('company', r.company_id))
        if refs:
            per_address[item.address] = refs
    unambiguous = {}
    ambiguous_companies = []
    for item in externals:
        refs = per_address.get(item.address)
        if not refs:
            continue
        companies = sorted({r.company_id for r in refs})
        if len(companies) == 1:
            unambiguous[item.address] = refs[0]
        else:
            for company_id in companies:
                if company_id not in ambiguous_companies:
                    ambiguous_companies.append(company_id)
    matched_companies = []
    if unambiguous:
        for item in externals:
            ref = unambiguous.get(item.address)
            if ref is None:
                continue
            result.contacts[item.address] = ref.contact_id
            if ref.company_id not in matched_companies:
                matched_companies.append(ref.company_id)
            if allowed('contact', ref.contact_id):
                _add_link(links, Link('contact', ref.contact_id, 'contact_email', 'high', 'auto'))
        for company_id in matched_companies:
            _add_link(links, Link('company', company_id, 'contact_email', 'high', 'auto'))
        result.decision = MATCHED
        result.company_id = matched_companies[0]
        result.method, result.confidence = 'contact_email', 'high'
        result.companies = tuple(matched_companies)
    elif ambiguous_companies:
        result.decision = AMBIGUOUS
        result.candidates = tuple(ambiguous_companies)
        result.method, result.confidence = 'contact_email', 'low'
        for company_id in ambiguous_companies:
            _add_link(links, Link('company', company_id, 'contact_email', 'low', 'proposed'))

    # 2b. sent by the CRM
    crm = snapshot.crm_sent.get(parsed.message_id) if direction == 'outbound' else None
    if crm is not None:
        result.email_log_id = crm.email_log_id
        if not result.decision and crm.company_id and allowed('company', crm.company_id):
            result.decision = MATCHED
            result.company_id = crm.company_id
            result.method, result.confidence = 'crm_sent', 'high'
            matched_companies.append(crm.company_id)
            _add_link(links, Link('company', crm.company_id, 'crm_sent', 'high', 'auto'))
        for target_type, target_id in crm.documents:
            if allowed(target_type, target_id):
                status = 'auto' if result.company_id == crm.company_id else 'proposed'
                _add_link(links, Link(target_type, str(target_id), 'crm_sent', 'high', status))

    # 3. document numbers
    text = parsed.subject + ('\n' + body_text if body_text else '')
    doc_refs = []
    for _, number in find_document_numbers(text):
        for ref in snapshot.documents.get(number, ()):
            if allowed(ref.target_type, ref.target_id):
                doc_refs.append(ref)
    if doc_refs:
        if result.decision == MATCHED:
            for ref in doc_refs:
                status = 'auto' if ref.company_id in matched_companies else 'proposed'
                confidence = 'high' if status == 'auto' else 'medium'
                _add_link(links, Link(ref.target_type, ref.target_id, 'doc_number', confidence,
                                      status, (('number', ref.number),)))
        elif result.decision == AMBIGUOUS:
            for ref in doc_refs:
                _add_link(links, Link(ref.target_type, ref.target_id, 'doc_number', 'medium',
                                      'proposed', (('number', ref.number),)))
        else:
            companies = []
            for ref in doc_refs:
                if ref.company_id not in companies:
                    companies.append(ref.company_id)
            if len(companies) == 1 and allowed('company', companies[0]):
                result.decision = MATCHED
                result.company_id = companies[0]
                result.method, result.confidence = 'doc_number', 'high'
                _add_link(links, Link('company', companies[0], 'doc_number', 'high', 'auto'))
                for ref in doc_refs:
                    _add_link(links, Link(ref.target_type, ref.target_id, 'doc_number', 'high',
                                          'auto', (('number', ref.number),)))
            else:
                result.decision = AMBIGUOUS
                result.candidates = tuple(c for c in companies if allowed('company', c))
                result.method, result.confidence = 'doc_number', 'low'
                for ref in doc_refs:
                    _add_link(links, Link(ref.target_type, ref.target_id, 'doc_number', 'medium',
                                          'proposed', (('number', ref.number),)))

    # 4. thread inheritance, only with evidence that the people belong there
    if not result.decision:
        company_id = snapshot.confirmed_conversations.get(conversation_key)
        if company_id and allowed('company', company_id):
            evidence = any(
                r.company_id == company_id
                for item in externals for r in snapshot.domains.get(item.domain, ())
            )
            if evidence:
                result.decision = MATCHED
                result.company_id = company_id
                result.method, result.confidence = 'thread', 'high'
                _add_link(links, Link('company', company_id, 'thread', 'high', 'auto'))
            else:
                result.decision = AMBIGUOUS
                result.candidates = (company_id,)
                result.method, result.confidence = 'thread', 'low'
                _add_link(links, Link('company', company_id, 'thread', 'low', 'proposed'))

    # 5. company domain
    shared_candidates = []
    if not result.decision:
        for item in externals:
            if not item.domain or capture_rules.is_freemail(item.domain, snapshot.extra_freemail):
                continue
            refs = tuple(
                r for r in snapshot.domains.get(item.domain, ()) if allowed('company', r.company_id)
            )
            if not refs:
                continue
            companies = sorted({r.company_id for r in refs})
            shared = len(companies) > 1 or any(r.shared_group_domain for r in refs)
            if shared:
                ranked = snapshot.shared_domain_ranking.get(item.domain) or tuple(companies)
                for company_id in ranked:
                    if company_id not in shared_candidates and allowed('company', company_id):
                        shared_candidates.append(company_id)
                continue
            result.decision = MATCHED
            result.company_id = companies[0]
            result.method, result.confidence = 'company_domain', 'medium'
            _add_link(links, Link('company', companies[0], 'company_domain', 'medium', 'auto',
                                  (('domain', item.domain),)))
            break

    # 6. nothing decisive
    if not result.decision:
        result.decision = UNMATCHED
        result.candidates = tuple(shared_candidates)
        if shared_candidates:
            result.unmatched_reason = 'shared_domain'
        elif all(capture_rules.is_freemail(a.domain, snapshot.extra_freemail) for a in externals):
            result.unmatched_reason = 'freemail'
        else:
            result.unmatched_reason = 'unknown'
        if direction == 'inbound':
            queue = [a for a in listed if sender is not None and a.address == sender.address]
            queue = queue or listed[:1]
        else:
            queue = list(listed)
        result.queue_addresses = tuple(queue)
        return result

    # Unknown external people at a matched company: candidates for a new contact.
    if result.decision == MATCHED:
        company_domains = {
            domain for domain, refs in snapshot.domains.items()
            for r in refs if r.company_id == result.company_id
        }
        contact_domains = {
            item.domain for item in externals if item.address in result.contacts
        }
        candidates = []
        # Listed recipients only: an address found past the recipient cap is
        # used for matching and never-log rules, never queued or proposed.
        for item in listed:
            if item.address in result.contacts or not item.valid:
                continue
            if capture_rules.is_freemail(item.domain, snapshot.extra_freemail):
                continue
            if item.domain in company_domains or item.domain in contact_domains:
                candidates.append((item, result.company_id))
        result.new_contact_candidates = tuple(candidates)
    return result
