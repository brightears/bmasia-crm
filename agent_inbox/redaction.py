"""Email content recorded here follows the mail-capture rules.

When the mail-capture app purges a message (a never-log rule, the "CRM private"
label, a Gmail deletion), ``redact_for_source`` removes every copy of its content
held here, in one transaction:

- every activity recorded for that reference, under any source system (the
  reference is compared as stored and in angle brackets): voided, and its
  summary, body, participants, source link and payload hash blanked; the row,
  its ids and timestamps stay, marked ``is_redacted``;
- every proposal that cites it (through such an activity or its own evidence
  source): evidence quote, rationale, evidence link, decision note and history
  notes blanked; for a note proposal that was not applied, its text too; open
  ones are closed as ``superseded`` with the reason in their history;
- a tombstone (``RedactedSource``: system, reference, when, reason; no content),
  so the same message cannot be recorded or cited again.

Text that a note proposal already added to a company's or contact's notes (and
the audit row of that update) is CRM data now and is not edited here: the
result lists it as ``applied_text_to_review`` with the record and audit ids, for
a person to review, and the audit entry says how many there are.

It writes one AuditLog row with counts and ids only, and is idempotent. There is
no REST endpoint or MCP tool for it. ``AgentInboxConfig.ready`` connects the
receiver below to the signal named in ``AGENT_INBOX_MAIL_PURGED_SIGNAL`` when
that signal exists.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from agent_inbox.message_ids import canonical_message_id
from agent_inbox.models import OPEN_STATUS, REASON_MAX, Activity, ChangeProposal, RedactedSource

logger = logging.getLogger(__name__)

DEFAULT_REASON = 'The source message was purged.'
CLOSED_DETAIL = 'Closed: the source message was redacted.'
APPLIED_STATUSES = ('accepted', 'edited')


def _canonical_ref(source_system, source_ref):
    if source_system == 'gmail':
        return canonical_message_id(source_ref) or None
    ref = str(source_ref or '').strip()
    return ref or None


def _ref_forms(ref):
    return {ref, f'<{ref}>'}


def is_redacted_source(source_ref):
    """Whether a reference (under any source system) was redacted here."""
    if not source_ref:
        return False
    forms = {source_ref, canonical_message_id(source_ref)} - {''}
    return RedactedSource.objects.filter(source_ref__in=forms).exists()


def _empty_counts():
    return {'activities': 0, 'proposals': 0, 'proposals_closed': 0, 'applied_text_to_review': 0}


def redact_for_source(source_system, source_ref, reason=DEFAULT_REASON):
    """Redact every copy of one source's content. Returns counts and the applied text to review."""
    from crm_app.models import AuditLog

    counts = _empty_counts()
    ref = _canonical_ref(source_system, source_ref)
    if not source_system or ref is None:
        return {**counts, 'applied_text_to_review': []}
    reason = (str(reason or '').strip() or DEFAULT_REASON)[:REASON_MAX]
    now = timezone.now()
    forms = _ref_forms(ref)
    with transaction.atomic():
        _, created = RedactedSource.objects.get_or_create(
            source_system=source_system, source_ref=ref, defaults={'reason': reason},
        )
        activities = list(Activity.objects.select_for_update().filter(source_ref__in=forms))
        for activity in activities:
            if activity.is_redacted:
                continue
            activity.is_void = True
            activity.voided_at = activity.voided_at or now
            activity.void_reason = reason
            activity.summary = ''
            activity.body = ''
            activity.participants = []
            activity.source_url = ''
            activity.payload_sha256 = ''
            activity.is_redacted = True
            activity.redacted_at = now
            activity.save()
            counts['activities'] += 1
        citing = ChangeProposal.objects.select_for_update().filter(
            Q(activity__in=[activity.pk for activity in activities]) | Q(evidence_source_ref__in=forms)
        )
        review = []
        for proposal in citing:
            changed = _redact_proposal(proposal, reason, now, counts)
            if proposal.kind == 'note' and proposal.status in APPLIED_STATUSES:
                review.append({
                    'proposal_id': str(proposal.pk), 'target_collection': proposal.target_collection,
                    'target_id': proposal.target_id, 'audit_id': str(proposal.applied_audit_id or ''),
                })
            if changed:
                proposal.save()
                counts['proposals'] += 1
        counts['applied_text_to_review'] = len(review)
        if counts['activities'] or counts['proposals'] or created:
            AuditLog.objects.create(
                user=None, action='UPDATE', model_name='Activity', record_id='source-redaction',
                additional_data={
                    'kind': 'source_redaction', 'source_system': source_system, **counts,
                    'applied_text_to_review_records': [
                        {'target_collection': item['target_collection'], 'target_id': item['target_id'],
                         'audit_id': item['audit_id']} for item in review
                    ],
                    'note': ('Text already added to customer records is not changed automatically; '
                             'a person reviews the records listed.') if review else '',
                },
            )
    return {**counts, 'applied_text_to_review': review}


def _redact_proposal(proposal, reason, now, counts):
    changed = False
    for field in ('evidence_quote', 'rationale', 'evidence_source_url', 'decision_note'):
        if getattr(proposal, field):
            setattr(proposal, field, '')
            changed = True
    history = proposal.history or []
    if any(entry.get('note') for entry in history):
        proposal.history = [{**entry, 'note': ''} for entry in history]
        changed = True
    if proposal.kind == 'note' and proposal.status not in APPLIED_STATUSES:
        if proposal.patch != {} or proposal.applied_patch is not None:
            proposal.patch = {}
            proposal.applied_patch = None
            changed = True
    if proposal.status == OPEN_STATUS:
        proposal.status = 'superseded'
        proposal.last_apply_error = CLOSED_DETAIL
        proposal.history = [*(proposal.history or []), {
            'action': 'redacted', 'by': '', 'at': now.isoformat(), 'note': '',
        }]
        counts['proposals_closed'] += 1
        changed = True
    return changed


def on_mail_purged(sender=None, source_system='gmail', source_refs=None, reason=None, **kwargs):
    """Receiver for the mail-capture app's ``mail_purged`` signal.

    The capture app sends ``source_system`` ('gmail'), ``source_refs`` (canonical
    Message-IDs) and ``reason`` ('rule', 'label' or 'gmail_deleted'), after commit.
    A single ``message_id`` keyword is accepted too.
    """
    refs = list(source_refs or [])
    if kwargs.get('message_id'):
        refs.append(kwargs['message_id'])
    results = [redact_for_source(source_system or 'gmail', ref, f'Purged by mail capture ({reason})'
                                 if reason else DEFAULT_REASON) for ref in refs]
    logger.info('agent_inbox redaction after mail purge: %d refs', len(refs))
    return results


def connect_purge_signal(path):
    """Connect ``on_mail_purged`` to the signal at dotted ``path`` if it exists. Returns whether it did."""
    if not path:
        return False
    from django.utils.module_loading import import_string

    try:
        signal = import_string(path)
    except ImportError:
        return False
    if not hasattr(signal, 'connect'):
        return False
    signal.connect(on_mail_purged, dispatch_uid='agent_inbox.redaction.on_mail_purged')
    return True
