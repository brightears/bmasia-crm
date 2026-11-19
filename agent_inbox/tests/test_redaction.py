"""Email content recorded here follows the mail-capture rules: a purged message is redacted here."""
import json
import sys
import types

import pytest
from django.dispatch import Signal

from agent_inbox import redaction
from agent_inbox.activities import record_activity
from agent_inbox.models import Activity, ChangeProposal, RedactedSource
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import (
    ACTIVITIES, PROPOSALS, activity_body, decide, make_user, session_client, token_client,
)
from crm_app.models import AuditLog

MESSAGE_ID = 'CAB987@mail.example.com'
MAIL_TEXT = 'Hello, our new reception number is +66 2 111 2222.'


@pytest.fixture
def captured(agent, person, company):
    job = make_user('capture-job')
    activity, _ = record_activity(job, activity_body(
        company, source_ref=f'<{MESSAGE_ID}>', body=MAIL_TEXT, summary='Reception number changed',
        source_url='https://mail.example.com/m/1'), via='job')
    open_one, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'our new reception number',
        'rationale': 'From the email', 'activity_id': str(activity.pk),
    }, via='rest')
    note_open, _ = create_proposal(agent, {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'notes': 'Customer wrote: our new reception number is +66 2 111 2222'},
        'evidence_quote': 'our new reception number', 'activity_id': str(activity.pk),
    }, via='rest')
    note_rejected, _ = create_proposal(person, {
        'kind': 'note', 'target_collection': 'contact', 'target_id': str(make_contact(company).pk),
        'patch': {'notes': 'Reception number per email'}, 'evidence_quote': 'reception number',
        'activity_id': str(activity.pk),
    }, via='ui')
    decide(session_client(make_user('third-person')), note_rejected.pk, 'reject',
           reason='The email says "our new reception number"')
    note_applied, _ = create_proposal(agent, {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'notes': 'Reception moved'}, 'evidence_quote': 'Hello',
        'evidence_source_system': 'gmail', 'evidence_source_ref': MESSAGE_ID,
    }, via='rest')
    decide(session_client(make_user('second-person')), note_applied.pk, 'accept')
    return {'activity': activity, 'open': open_one, 'note_open': note_open, 'note_rejected': note_rejected,
            'note_applied': note_applied}


def make_contact(company):
    from crm_app.models import Contact
    return Contact.objects.get_or_create(company=company, email='desk@riverside.example.com',
                                         defaults={'name': 'Desk Example'})[0]


def refreshed(rows):
    for row in rows.values():
        row.refresh_from_db()
    return rows


def test_redaction_removes_the_message_text_everywhere_it_was_copied(captured, company):
    result = redaction.redact_for_source('gmail', f' <{MESSAGE_ID}> ', 'Marked private in the mailbox')
    rows = refreshed(captured)
    activity = rows['activity']
    assert (activity.summary, activity.body, activity.participants, activity.source_url,
            activity.payload_sha256) == ('', '', [], '', '')
    assert activity.is_void and activity.is_redacted and activity.redacted_at
    assert activity.source_ref == MESSAGE_ID and activity.created_at
    for key in ('open', 'note_open', 'note_rejected', 'note_applied'):
        proposal = rows[key]
        assert (proposal.evidence_quote, proposal.rationale, proposal.evidence_source_url,
                proposal.decision_note) == ('', '', '', ''), key
        assert all(not entry.get('note') for entry in proposal.history), key
    assert rows['note_open'].patch == {} and rows['note_rejected'].patch == {}
    assert rows['note_applied'].patch == {'notes': 'Reception moved'}
    assert (rows['open'].status, rows['note_open'].status) == ('superseded', 'superseded')
    assert rows['note_rejected'].status == 'rejected' and rows['note_applied'].status == 'accepted'
    assert result['applied_text_to_review'] == [{
        'proposal_id': str(rows['note_applied'].pk), 'target_collection': 'company', 'target_id': str(company.pk),
        'audit_id': str(rows['note_applied'].applied_audit_id),
    }]
    stored = json.dumps([
        {k: v for k, v in row.__dict__.items() if not k.startswith('_')} for row in
        [*ChangeProposal.objects.all(), *Activity.objects.all()]
    ], default=str)
    assert 'reception number' not in stored.replace('Reception moved', '')


def test_redaction_writes_one_audit_row_with_counts_and_ids_only(captured, company):
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    row = AuditLog.objects.get(record_id='source-redaction')
    assert row.user is None and row.changes is None
    data = row.additional_data
    assert (data['activities'], data['proposals'], data['proposals_closed'], data['applied_text_to_review']) \
        == (1, 4, 2, 1)
    assert data['applied_text_to_review_records'][0]['target_id'] == str(company.pk)
    assert 'not changed automatically' in data['note']
    assert MESSAGE_ID not in json.dumps(data)


def test_redaction_is_idempotent_and_all_or_nothing(captured, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('audit store unavailable')

    with monkeypatch.context() as patched:
        patched.setattr(AuditLog.objects, 'create', broken)
        with pytest.raises(RuntimeError):
            redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    captured['activity'].refresh_from_db()
    assert captured['activity'].body and not RedactedSource.objects.exists()
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    again = redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    assert (again['activities'], again['proposals']) == (0, 0)
    assert AuditLog.objects.filter(record_id='source-redaction').count() == 1


def test_a_redacted_message_cannot_be_recorded_or_cited_again(captured, agent, other_agent, company):
    redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    tombstone = RedactedSource.objects.get()
    assert (tombstone.source_system, tombstone.source_ref, tombstone.reason) == ('gmail', MESSAGE_ID, 'Purged')
    for system, ref in (('gmail', f'<{MESSAGE_ID}>'), ('agent', MESSAGE_ID), ('other', f'<{MESSAGE_ID}>')):
        response = token_client(other_agent).post(ACTIVITIES, activity_body(
            company, idempotency_key=f'test:again-{system}', source_system=system, source_ref=ref,
            body=MAIL_TEXT), format='json')
        assert response.status_code == 409 and response.json()['code'] == 'source_redacted', system
    cite = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 999 9999'}, 'evidence_quote': 'x',
        'evidence_source_system': 'gmail', 'evidence_source_ref': MESSAGE_ID,
    }, format='json')
    assert cite.status_code == 409 and cite.json()['code'] == 'source_redacted'


def test_copies_logged_under_another_source_system_are_found(agent, company):
    copy, _ = record_activity(agent, activity_body(company, source_system='agent', source_ref=f'<{MESSAGE_ID}>',
                                                   body=MAIL_TEXT), via='rest')
    result = redaction.redact_for_source('gmail', MESSAGE_ID, 'Purged')
    copy.refresh_from_db()
    assert result['activities'] == 1 and copy.is_redacted and copy.body == ''


def test_nothing_happens_without_a_reference():
    for system, ref in (('gmail', ''), ('gmail', 'synthetic:' + 'a' * 64), ('', MESSAGE_ID)):
        result = redaction.redact_for_source(system, ref, 'x')
        assert (result['activities'], result['proposals']) == (0, 0)
    assert not RedactedSource.objects.exists() and not AuditLog.objects.filter(record_id='source-redaction')


def test_the_receiver_follows_the_capture_apps_signal(captured, monkeypatch):
    module = types.ModuleType('purge_signal_example')
    module.mail_purged = Signal()
    monkeypatch.setitem(sys.modules, 'purge_signal_example', module)
    assert redaction.connect_purge_signal('purge_signal_example.mail_purged') is True
    module.mail_purged.send(sender=None, source_system='gmail', source_refs=[MESSAGE_ID], reason='rule')
    activity = captured['activity']
    activity.refresh_from_db()
    assert activity.is_redacted and 'rule' in activity.void_reason


def test_a_missing_signal_is_simply_not_connected():
    assert redaction.connect_purge_signal('') is False
    assert redaction.connect_purge_signal('no_such_app_here.signals.mail_purged') is False


def test_agents_cannot_trigger_redaction(agent, captured):
    activity = captured['activity']
    client = token_client(agent)
    for path in (f'{ACTIVITIES}{activity.pk}/redact/', f'{ACTIVITIES}redact/', '/api/v1/redact/'):
        assert client.post(path, {'reason': 'x'}, format='json').status_code in (403, 404, 405)
    import crm_app.mcp  # noqa: F401
    from mcp_server.djangomcp import global_mcp_server
    assert not [tool for tool in global_mcp_server._tool_manager.list_tools() if 'redact' in tool.name]
    activity.refresh_from_db()
    assert not activity.is_redacted and not RedactedSource.objects.exists()
