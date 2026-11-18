"""Email content recorded here follows the mail-capture rules: a purged message is redacted here."""
import json
import sys
import types

import pytest
from django.dispatch import Signal

from agent_inbox import redaction
from agent_inbox.activities import record_activity
from agent_inbox.message_ids import canonical_message_id
from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import ACTIVITIES, activity_body, decide, make_user, session_client, token_client
from crm_app.models import AuditLog

MESSAGE_ID = 'CAB987@mail.example.com'


@pytest.fixture
def captured(agent, person, company):
    job = make_user('capture-job')
    activity, _ = record_activity(job, activity_body(
        company, source_ref=f'<{MESSAGE_ID}>', body='Hello, our new reception number is +66 2 111 2222.',
        summary='Reception number changed'), via='job')
    open_one, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'unverified copy', 'rationale': 'From the email',
        'evidence_source_system': 'gmail', 'evidence_source_ref': MESSAGE_ID,
    }, via='rest')
    linked, _ = create_proposal(person, {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'notes': 'Reception number changed'}, 'evidence_quote': 'our new reception number',
        'rationale': 'Seen in the email', 'activity_id': str(activity.pk),
    }, via='ui')
    decided, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'city': 'Chiang Mai'}, 'evidence_quote': 'moving to Chiang Mai', 'rationale': 'From the email',
        'evidence_source_system': 'gmail', 'evidence_source_ref': MESSAGE_ID,
    }, via='rest')
    decide(session_client(make_user('third-person')), decided.pk, 'reject', reason='Not yet')
    return activity, open_one, linked, decided


def test_redaction_blanks_content_and_closes_open_proposals(captured):
    activity, open_one, linked, decided = captured
    counts = redaction.redact_for_source('gmail', f' <{MESSAGE_ID}> ', 'Marked private in the mailbox')
    assert counts == {'activities': 1, 'proposals': 3, 'proposals_closed': 2}
    activity.refresh_from_db()
    assert (activity.summary, activity.body, activity.participants, activity.source_url) == ('', '', [], '')
    assert activity.is_void and activity.is_redacted and activity.redacted_at
    assert activity.source_ref == MESSAGE_ID and activity.created_at
    for proposal in (open_one, linked, decided):
        proposal.refresh_from_db()
        assert (proposal.evidence_quote, proposal.rationale) == ('', '')
    assert (open_one.status, linked.status, decided.status) == ('superseded', 'superseded', 'rejected')
    assert open_one.history[-1]['action'] == 'redacted'


def test_redaction_writes_one_audit_row_with_counts_only(captured):
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    row = AuditLog.objects.get(record_id='source-redaction')
    assert row.user is None and row.changes is None
    assert row.additional_data == {'kind': 'source_redaction', 'source_system': 'gmail', 'activities': 1,
                                   'proposals': 3, 'proposals_closed': 2}
    assert MESSAGE_ID not in json.dumps(row.additional_data)


def test_redaction_is_idempotent(captured):
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    again = redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    assert again == {'activities': 0, 'proposals': 0, 'proposals_closed': 0}
    assert AuditLog.objects.filter(record_id='source-redaction').count() == 1


def test_redaction_is_all_or_nothing(captured, monkeypatch):
    activity = captured[0]

    def broken(*args, **kwargs):
        raise RuntimeError('audit store unavailable')

    monkeypatch.setattr(AuditLog.objects, 'create', broken)
    with pytest.raises(RuntimeError):
        redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    activity.refresh_from_db()
    assert activity.body and not activity.is_redacted
    assert ChangeProposal.objects.filter(status='proposed').count() == 2


def test_other_messages_are_untouched(captured, company, agent):
    other, _ = record_activity(agent, activity_body(company, idempotency_key='test:other-0001',
                                                    source_ref='other@mail.example.com'), via='rest')
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    other.refresh_from_db()
    assert other.body and not other.is_redacted


def test_an_invalid_reference_redacts_nothing(captured):
    assert redaction.redact_for_source('gmail', '18c2a4f0b1d2e3f4', 'x') == {
        'activities': 0, 'proposals': 0, 'proposals_closed': 0}
    assert redaction.redact_for_source('', MESSAGE_ID, 'x')['activities'] == 0


def test_the_receiver_connects_to_a_signal_found_by_its_path(captured, monkeypatch):
    module = types.ModuleType('purge_signal_example')
    module.mail_purged = Signal()
    monkeypatch.setitem(sys.modules, 'purge_signal_example', module)
    assert redaction.connect_purge_signal('purge_signal_example.mail_purged') is True
    module.mail_purged.send(sender=None, message_id=MESSAGE_ID, reason='Never-log rule')
    activity = captured[0]
    activity.refresh_from_db()
    assert activity.is_redacted and activity.void_reason == 'Never-log rule'


def test_a_missing_signal_is_simply_not_connected():
    assert redaction.connect_purge_signal('') is False
    assert redaction.connect_purge_signal('no_such_app_here.signals.mail_purged') is False


def test_the_message_id_rule_matches_the_documented_examples():
    assert canonical_message_id(' <a.b@c.example> ') == 'a.b@c.example'
    assert canonical_message_id('A.B@C.example') == 'A.B@C.example'
    assert canonical_message_id('long:' + 'f' * 64) == 'long:' + 'f' * 64
    for bad in ('18c2a4f0b1d2e3f4', '', '<>', 'a @b', None, 'synthetic:xyz'):
        assert canonical_message_id(bad) is None


def test_agents_cannot_trigger_redaction(agent, captured):
    activity = captured[0]
    client = token_client(agent)
    for path in (f'{ACTIVITIES}{activity.pk}/redact/', f'{ACTIVITIES}redact/', '/api/v1/redact/'):
        assert client.post(path, {'reason': 'x'}, format='json').status_code in (403, 404, 405)
    import crm_app.mcp  # noqa: F401
    from mcp_server.djangomcp import global_mcp_server
    assert not [tool for tool in global_mcp_server._tool_manager.list_tools() if 'redact' in tool.name]
    activity.refresh_from_db()
    assert not activity.is_redacted and Activity.objects.filter(is_redacted=True).count() == 0
