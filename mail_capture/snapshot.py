"""Builds the matcher's ``Snapshot`` for one batch of parsed messages.

Reads only. Loads just the rows the batch can touch (its addresses, domains,
document numbers and conversation keys), so the cost does not grow with the
size of the CRM.
"""
import uuid
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import Lower

from crm_app.models import Contact, Contract, EmailLog, Invoice, Quote

from . import conf
from .match import (
    ContactRef, CrmSentRef, DocRef, DomainRef, Snapshot, find_document_numbers,
)
from .models import CaptureRule, CompanyDomain, MailConversation, MailMatch, MailParticipant
from .parse import is_internal, match_key, normalise_message_id
from .rules import rule_from_row


# X-BMAsia-Email-ID values set by crm_app.services.email_service:
# '<EmailLog uuid>' for the generic sender, '<prefix>_<document uuid>' for
# document mail, which logs one EmailLog row per recipient.
_CRM_HEADER_PREFIXES = (
    ('renewal_manual_', 'contract', 'renewal'),
    ('contract_', 'contract', 'contract_send'),
    ('quote_', 'quote', 'quote_send'),
    ('invoice_', 'invoice', 'invoice_send'),
    ('receipt_', 'invoice', 'receipt_send'),
)
_CRM_SENT_WINDOW = timedelta(days=2)


def _uuid_or_none(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def load_rules():
    return tuple(rule_from_row(row) for row in CaptureRule.objects.all())


def _email_log_documents(row):
    docs = []
    for target_type, attr in (('contract', 'contract_id'), ('quote', 'quote_id'), ('invoice', 'invoice_id')):
        value = getattr(row, attr, None)
        if value:
            docs.append((target_type, str(value)))
    return tuple(docs)


def resolve_crm_sent(parsed):
    """The ``EmailLog`` row for a message the CRM sent, or None.

    1. ``X-BMAsia-Email-ID`` holding an EmailLog id (generic sender).
    2. ``X-BMAsia-Email-ID`` holding ``quote_/contract_/invoice_/receipt_`` and
       a document id: the EmailLog row for that document and the message's
       recipient, closest in time, within two days.
    3. ``EmailLog.message_id`` equal to the Message-ID. (The generic sender
       stores an id from a second ``message()`` call, which is not the id that
       was sent; rows written by agents or a later fix will match here.)
    """
    header = (parsed.crm_email_id or '').strip()
    if header:
        log_id = _uuid_or_none(header)
        if log_id:
            row = EmailLog.objects.filter(pk=log_id).first()
            if row is not None:
                return row
        for prefix, target_type, email_type in _CRM_HEADER_PREFIXES:
            if not header.startswith(prefix):
                continue
            doc_id = _uuid_or_none(header[len(prefix):])
            recipients = [a.address for a in parsed.to]
            if not doc_id or not recipients:
                break
            rows = EmailLog.objects.annotate(to_lower=Lower('to_email')).filter(
                **{f'{target_type}_id': doc_id}, email_type=email_type,
                to_lower__in=recipients,
            )
            if parsed.sent_at is not None:
                rows = rows.filter(
                    Q(sent_at__isnull=True, created_at__range=(
                        parsed.sent_at - _CRM_SENT_WINDOW, parsed.sent_at + _CRM_SENT_WINDOW))
                    | Q(sent_at__range=(
                        parsed.sent_at - _CRM_SENT_WINDOW, parsed.sent_at + _CRM_SENT_WINDOW))
                )
            best, best_gap = None, None
            for row in rows[:20]:
                when = row.sent_at or row.created_at
                gap = abs((when - parsed.sent_at).total_seconds()) if parsed.sent_at else 0
                if best is None or gap < best_gap:
                    best, best_gap = row, gap
            if best is not None:
                return best
            break
    if parsed.message_id and not parsed.message_id_synthetic:
        candidates = {parsed.message_id, f'<{parsed.message_id}>'}
        for row in EmailLog.objects.filter(message_id__in=candidates)[:5]:
            if normalise_message_id(row.message_id) == parsed.message_id:
                return row
    return None


def build_snapshot(parsed_messages, conversation_keys=(), body_texts=(), rules=None):
    domains_internal = conf.internal_domains()
    addresses_internal = conf.internal_addresses()

    external = []
    for parsed in parsed_messages:
        for item in parsed.addresses():
            if not is_internal(item, domains_internal, addresses_internal):
                external.append(item)
    keys = {item.match_key for item in external} | {item.address for item in external}
    domains = {item.domain for item in external if item.domain}

    contacts = {}
    if keys:
        rows = (
            Contact.objects.annotate(email_lower=Lower('email'))
            .filter(email_lower__in=keys)
            .values_list('id', 'company_id', 'email_lower')
        )
        for contact_id, company_id, email_lower in rows:
            ref = ContactRef(str(contact_id), str(company_id))
            for key in {match_key(email_lower), email_lower}:
                bucket = contacts.setdefault(key, [])
                if ref not in bucket:
                    bucket.append(ref)
    contacts = {k: tuple(v) for k, v in contacts.items()}

    domain_refs = {}
    if domains:
        for row in CompanyDomain.objects.filter(domain__in=domains):
            domain_refs.setdefault(row.domain, []).append(
                DomainRef(str(row.company_id), row.shared_group_domain)
            )
    domain_refs = {k: tuple(v) for k, v in domain_refs.items()}

    ranking = {}
    for domain, refs in domain_refs.items():
        companies = {r.company_id for r in refs}
        if len(companies) > 1 or any(r.shared_group_domain for r in refs):
            ranking[domain] = _rank_shared_domain(domain, companies)

    texts = [p.subject for p in parsed_messages] + [t for t in body_texts if t]
    numbers = {}
    for text in texts:
        for kind, number in find_document_numbers(text):
            numbers.setdefault(kind, set()).add(number)
    documents = {}

    def put(number, ref):
        documents.setdefault(number, [])
        if ref not in documents[number]:
            documents[number].append(ref)

    if numbers.get('contract'):
        for pk, company_id, number in Contract.objects.filter(
            contract_number__in=numbers['contract']
        ).values_list('id', 'company_id', 'contract_number'):
            put(number.upper(), DocRef('contract', str(pk), str(company_id), number))
    if numbers.get('quote'):
        for pk, company_id, number in Quote.objects.filter(
            quote_number__in=numbers['quote']
        ).values_list('id', 'company_id', 'quote_number'):
            put(number.upper(), DocRef('quote', str(pk), str(company_id), number))
    if numbers.get('invoice'):
        for pk, company_id, number in Invoice.objects.filter(
            invoice_number__in=numbers['invoice']
        ).values_list('id', 'company_id', 'invoice_number'):
            put(number.upper(), DocRef('invoice', str(pk), str(company_id), number))
    if numbers.get('receipt'):
        for pk, company_id, number in Invoice.objects.filter(
            receipt_number__in=numbers['receipt']
        ).values_list('id', 'company_id', 'receipt_number'):
            put(number.upper(), DocRef('invoice', str(pk), str(company_id), number))
    documents = {k: tuple(v) for k, v in documents.items()}

    keys_conv = set(conversation_keys) | {p.conversation_key for p in parsed_messages}
    confirmed, rejected = {}, {}
    if keys_conv:
        for key, company_id in MailConversation.objects.filter(
            conversation_key__in=keys_conv, link_state='confirmed', company__isnull=False,
        ).values_list('conversation_key', 'company_id'):
            confirmed[key] = str(company_id)
        rows = MailMatch.objects.filter(status='rejected').filter(
            Q(conversation__conversation_key__in=keys_conv)
            | Q(message__conversation__conversation_key__in=keys_conv)
        ).values_list(
            'conversation__conversation_key', 'message__conversation__conversation_key',
            'target_type', 'target_id',
        )
        for conv_key, msg_conv_key, target_type, target_id in rows:
            key = conv_key or msg_conv_key
            rejected.setdefault(key, set()).add((target_type, str(target_id)))
    rejected = {k: frozenset(v) for k, v in rejected.items()}

    crm_sent = {}
    for parsed in parsed_messages:
        sender = parsed.from_address
        if sender is None or not is_internal(sender, domains_internal, addresses_internal):
            continue
        row = resolve_crm_sent(parsed)
        if row is not None:
            crm_sent[parsed.message_id] = CrmSentRef(
                str(row.pk), str(row.company_id) if row.company_id else '',
                _email_log_documents(row),
            )

    return Snapshot(
        internal_domains=domains_internal,
        internal_addresses=addresses_internal,
        contacts=contacts,
        domains=domain_refs,
        documents=documents,
        confirmed_conversations=confirmed,
        rejected=rejected,
        shared_domain_ranking=ranking,
        crm_sent=crm_sent,
        rules=load_rules() if rules is None else tuple(rules),
    )


def _rank_shared_domain(domain, companies):
    """Candidates for a shared domain: most contacts at that domain first,
    then most captured conversations, then id for a stable order."""
    contact_counts = dict(
        Contact.objects.annotate(email_lower=Lower('email'))
        .filter(email_lower__endswith='@' + domain, company_id__in=companies)
        .values('company_id').annotate(n=Count('id')).values_list('company_id', 'n')
    )
    conversation_counts = dict(
        MailParticipant.objects.filter(
            domain=domain, message__conversation__company_id__in=companies,
        ).values('message__conversation__company_id')
        .annotate(n=Count('message__conversation', distinct=True))
        .values_list('message__conversation__company_id', 'n')
    )
    contact_counts = {str(k): v for k, v in contact_counts.items()}
    conversation_counts = {str(k): v for k, v in conversation_counts.items()}
    return tuple(sorted(
        companies,
        key=lambda c: (-contact_counts.get(c, 0), -conversation_counts.get(c, 0), c),
    ))
