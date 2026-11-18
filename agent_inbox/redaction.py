"""Email content recorded here follows the mail-capture rules.

When a message is purged by the mail-capture app (a never-log rule, the
"CRM private" label, or its purge), ``redact_for_source`` removes the copies of
its content held here:

- every activity recorded for that source: voided, summary, body, participants
  and source link blanked, ``is_redacted`` set; the row, its ids and timestamps stay;
- every proposal that cites it (through the activity or its own evidence
  source): evidence quote and rationale blanked; open ones are closed as
  ``superseded`` with the reason in their history.

It runs in one transaction, writes one AuditLog row with counts only, and is
idempotent: a second call finds nothing left to change and writes nothing.

There is no REST endpoint or MCP tool for it. It is called by the receiver
below, which ``AgentInboxConfig.ready`` connects to the signal named in
``AGENT_INBOX_MAIL_PURGED_SIGNAL`` when that signal exists.
"""
import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from agent_inbox.message_ids import canonical_message_id
from agent_inbox.models import OPEN_STATUS, REASON_MAX, Activity, ChangeProposal

logger = logging.getLogger(__name__)

DEFAULT_REASON = 'The source message was purged.'
CLOSED_DETAIL = 'Closed: the source message was redacted.'


def _canonical_ref(source_system, source_ref):
    if source_system == 'gmail':
        return canonical_message_id(source_ref)
    ref = str(source_ref or '').strip()
    return ref or None


def redact_for_source(source_system, source_ref, reason=DEFAULT_REASON):
    """Redact every copy of one source's content. Returns the counts of rows changed."""
    from crm_app.models import AuditLog

    counts = {'activities': 0, 'proposals': 0, 'proposals_closed': 0}
    ref = _canonical_ref(source_system, source_ref)
    if not source_system or ref is None:
        return counts
    reason = (str(reason or '').strip() or DEFAULT_REASON)[:REASON_MAX]
    now = timezone.now()
    with transaction.atomic():
        activities = list(Activity.objects.select_for_update().filter(source_system=source_system, source_ref=ref))
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
            activity.is_redacted = True
            activity.redacted_at = now
            activity.save()
            counts['activities'] += 1
        citing = ChangeProposal.objects.select_for_update().filter(
            Q(activity__in=[activity.pk for activity in activities])
            | Q(evidence_source_system=source_system, evidence_source_ref=ref)
        )
        for proposal in citing:
            changed = False
            if proposal.evidence_quote or proposal.rationale:
                proposal.evidence_quote = ''
                proposal.rationale = ''
                changed = True
            if proposal.status == OPEN_STATUS:
                proposal.status = 'superseded'
                proposal.last_apply_error = CLOSED_DETAIL
                proposal.history = [*(proposal.history or []), {
                    'action': 'redacted', 'by': '', 'at': now.isoformat(), 'note': reason,
                }]
                counts['proposals_closed'] += 1
                changed = True
            if changed:
                proposal.save()
                counts['proposals'] += 1
        if counts['activities'] or counts['proposals']:
            AuditLog.objects.create(
                user=None, action='UPDATE', model_name='Activity', record_id='source-redaction',
                additional_data={'kind': 'source_redaction', 'source_system': source_system, **counts},
            )
    return counts


def on_mail_purged(sender=None, message_id=None, reason=None, **kwargs):
    """Receiver for the mail-capture app's purge signal (sent with the canonical Message-ID)."""
    message_id = message_id or kwargs.get('rfc_message_id')
    counts = redact_for_source('gmail', message_id, reason or DEFAULT_REASON)
    logger.info('agent_inbox redaction after mail purge: %s', counts)
    return counts


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
