"""Change proposals over REST: storing, de-duplication, evidence, decisions, apply, expiry, switch."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from agent_inbox.activities import record_activity
from agent_inbox.models import EVIDENCE_QUOTE_MAX, ChangeProposal
from agent_inbox.tests.conftest import (
    PROPOSALS, activity_body, jwt_client, session_client, token_client,
)

QUOTE = 'our new reception number is +66 2 111 2222 from Monday'


def propose(client, **body):
    return client.post(PROPOSALS, body, format='json')


def phone_body(company, **overrides):
    body = {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': QUOTE,
        'rationale': 'The customer gave a new reception number.', 'batch_key': 'gmail:msg-0001',
    }
    body.update(overrides)
    return body


@pytest.fixture
def activity(agent, company):
    row, _ = record_activity(agent, activity_body(company), via='rest')
    return row


def accept(client, proposal_id, **body):
    return client.post(f'{PROPOSALS}{proposal_id}/accept/', body, format='json')


# ------------------------------------------------------------------ storing


def test_agent_proposal_is_stored_and_nothing_changes(agent, company, activity):
    response = propose(token_client(agent), **phone_body(company, activity_id=str(activity.pk),
                                                       confidence=0.8, model='example-model', prompt_version='v1'))
    assert response.status_code == 201, response.content
    data = response.json()
    assert data['status'] == 'proposed'
    assert data['proposer_username'] == 'theo' and data['proposer_kind'] == 'agent'
    assert data['current_values'] == {'phone': '+66 2 000 0000'}
    assert data['expected_version']
    assert data['evidence_verified'] is True
    assert data['evidence_source_system'] == 'gmail' and data['evidence_source_ref'] == 'msg-0001'
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'


def test_expiry_is_set_from_the_setting(agent, company):
    with override_settings(CHANGE_PROPOSAL_EXPIRY_DAYS=3):
        data = propose(token_client(agent), **phone_body(company)).json()
    proposal = ChangeProposal.objects.get(pk=data['id'])
    assert timedelta(days=2, hours=23) < proposal.expires_at - proposal.created_at <= timedelta(days=3, minutes=1)


def test_retry_of_the_same_proposal_is_a_replay(agent, company):
    client = token_client(agent)
    first = propose(client, **phone_body(company))
    second = propose(client, **phone_body(company))
    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()['replayed'] is True and second.json()['id'] == first.json()['id']
    assert ChangeProposal.objects.count() == 1


def test_same_change_from_another_proposer_is_a_duplicate(agent, other_agent, company):
    first = propose(token_client(agent), **phone_body(company)).json()
    response = propose(token_client(other_agent), **phone_body(company))
    assert response.status_code == 409
    assert response.json()['code'] == 'duplicate_open'
    assert response.json()['existing_proposal_id'] == first['id']


def test_rejected_proposal_never_comes_back(agent, person, company):
    client = token_client(agent)
    first = propose(client, **phone_body(company)).json()
    reject = session_client(person).post(f"{PROPOSALS}{first['id']}/reject/", {'reason': 'Old number'}, format='json')
    assert reject.status_code == 200
    for proposer in (client, token_client(person)):
        again = propose(proposer, **phone_body(company, evidence_quote=QUOTE, rationale='Trying again'))
        assert again.status_code == 409
        assert again.json()['code'] == 'previously_rejected'
    assert ChangeProposal.objects.count() == 1


def test_accepted_proposal_is_not_raised_again(agent, person, company):
    first = propose(token_client(agent), **phone_body(company)).json()
    assert accept(session_client(person), first['id']).status_code == 200
    again = propose(token_client(agent), **phone_body(company))
    # The record now holds the value, which is reported first.
    assert again.status_code == 422 and again.json()['code'] == 'no_change'


def test_expired_proposal_may_be_raised_again(agent, company):
    client = token_client(agent)
    first = propose(client, **phone_body(company)).json()
    ChangeProposal.objects.filter(pk=first['id']).update(expires_at=timezone.now() - timedelta(minutes=1))
    again = propose(client, **phone_body(company))
    assert again.status_code == 201
    assert ChangeProposal.objects.get(pk=first['id']).status == 'expired'


def test_a_newer_value_for_the_same_fields_supersedes_the_open_one(agent, company):
    client = token_client(agent)
    first = propose(client, **phone_body(company)).json()
    second = propose(client, **phone_body(company, patch={'phone': '+66 2 333 4444'},
                                          evidence_quote='Our number is +66 2 333 4444')).json()
    old = ChangeProposal.objects.get(pk=first['id'])
    assert old.status == 'superseded' and str(old.superseded_by_id) == second['id']


def test_no_change_proposal_is_refused(agent, company):
    response = propose(token_client(agent), **phone_body(company, patch={'phone': '+66 2 000 0000'}))
    assert response.status_code == 422 and response.json()['code'] == 'no_change'


def test_values_are_validated_by_the_record_serializer(agent, company, contact):
    response = propose(token_client(agent), kind='field_update', target_collection='contact',
                       target_id=str(contact.pk), patch={'phone': 'not a phone'}, evidence_quote='call me')
    assert response.status_code == 422
    assert response.json()['code'] == 'invalid_value'
    assert 'phone' in response.json()['errors']


@pytest.mark.parametrize('overrides, status, code', [
    ({'kind': 'link'}, 422, 'kind_not_allowed'),
    ({'kind': 'other'}, 422, 'kind_not_allowed'),
    ({'target_collection': 'contract'}, 422, 'collection_not_allowed'),
    ({'target_collection': 'invoice'}, 422, 'collection_not_allowed'),
    ({'target_id': '00000000-0000-0000-0000-000000000001'}, 422, 'unknown_record'),
    ({'patch': {}}, 400, 'invalid'),
    ({'patch': ['phone']}, 400, 'invalid'),
    ({'patch': {'phone': 5}}, 400, 'invalid'),
    ({'patch': {'phone': 'x' * 5001}}, 400, 'invalid'),
    ({'evidence_quote': ''}, 422, 'evidence_required'),
    ({'evidence_quote': 'x' * (EVIDENCE_QUOTE_MAX + 1)}, 400, 'invalid'),
    ({'rationale': 'x' * 1001}, 400, 'invalid'),
    ({'confidence': 1.5}, 400, 'invalid'),
    ({'confidence': True}, 400, 'invalid'),
    ({'batch_key': 'has space'}, 400, 'invalid'),
    ({'model': 'x' * 101}, 400, 'invalid'),
    ({'evidence_source_url': 'ftp://example.com/x'}, 400, 'invalid'),
    ({'evidence_source_system': 'fax'}, 400, 'invalid'),
    ({'proposer_kind': 'human'}, 403, 'proposer_kind_not_allowed'),
    ({'proposer_kind': 'job'}, 403, 'proposer_kind_not_allowed'),
    ({'surprise': 1}, 400, 'invalid'),
])
def test_invalid_proposals_are_refused(agent, company, overrides, status, code):
    response = propose(token_client(agent), **phone_body(company, **overrides))
    assert response.status_code == status, response.content
    assert response.json()['code'] == code
    assert ChangeProposal.objects.count() == 0


def test_people_may_propose_without_a_quote(person, company):
    response = propose(session_client(person), **phone_body(company, evidence_quote=''))
    assert response.status_code == 201
    assert response.json()['proposer_kind'] == 'human'


def test_ai_proposer_needs_a_quote_even_from_a_person_account(person, company):
    response = propose(session_client(person), **phone_body(company, evidence_quote='', proposer_kind='ai'))
    assert response.status_code == 422 and response.json()['code'] == 'evidence_required'


def test_daily_cap_per_proposer(agent, company, contact):
    client = token_client(agent)
    with override_settings(CHANGE_PROPOSALS_DAILY_CAP=1):
        assert propose(client, **phone_body(company)).status_code == 201
        refused = propose(client, kind='field_update', target_collection='contact', target_id=str(contact.pk),
                          patch={'title': 'Director'}, evidence_quote='I am now the director')
    assert refused.status_code == 429 and refused.json()['code'] == 'daily_cap'


# ------------------------------------------------------------------ evidence


def test_quote_must_occur_verbatim_in_the_activity_body(agent, company, activity):
    response = propose(token_client(agent), **phone_body(
        company, activity_id=str(activity.pk), evidence_quote='our new phone number is +66 2 111 2222',
    ))
    assert response.status_code == 422
    assert response.json()['code'] == 'quote_not_verbatim'


def test_quote_check_ignores_line_breaks_and_spacing_only(agent, company, activity):
    body = phone_body(company, activity_id=str(activity.pk),
                      evidence_quote='Hello,   our new reception number\n is +66 2 111 2222')
    assert propose(token_client(agent), **body).status_code == 201
    case_changed = phone_body(company, activity_id=str(activity.pk), patch={'phone': '+66 2 999 9999'},
                              evidence_quote='OUR NEW RECEPTION NUMBER')
    assert propose(token_client(agent), **case_changed).json()['code'] == 'quote_not_verbatim'


def test_activity_of_another_company_or_void_is_refused(agent, company, other_company, activity):
    from agent_inbox.activities import void_activity
    other, _ = record_activity(agent, activity_body(other_company, idempotency_key='test:other-act-1'), via='rest')
    response = propose(token_client(agent), **phone_body(company, activity_id=str(other.pk)))
    assert response.json()['code'] == 'wrong_company'
    void_activity(agent, activity.pk, {'reason': 'wrong'})
    response = propose(token_client(agent), **phone_body(company, activity_id=str(activity.pk)))
    assert response.json()['code'] == 'activity_void'


def test_evidence_without_a_stored_body_is_kept_unverified(agent, company):
    response = propose(token_client(agent), **phone_body(company, evidence_source_system='google_chat',
                                                          evidence_source_ref='spaces/x/messages/y'))
    assert response.status_code == 201
    assert response.json()['evidence_verified'] is False


# ------------------------------------------------------------------ accept


def _audit_for(model_name, record_id):
    from crm_app.models import AuditLog
    return list(AuditLog.objects.filter(model_name=model_name, record_id=str(record_id)))


def test_accept_applies_through_the_guarded_path_as_the_reviewer(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    response = accept(jwt_client(person), proposal['id'], note='Checked with the customer')
    assert response.status_code == 200, response.content
    data = response.json()
    assert data['status'] == 'accepted'
    assert data['reviewer_username'] == 'reviewer-person'
    assert data['applied_patch'] == {'phone': '+66 2 111 2222'}
    assert data['decision_note'] == 'Checked with the customer'
    company.refresh_from_db()
    assert company.phone == '+66 2 111 2222'
    rows = _audit_for('Company', company.pk)
    assert len(rows) == 1
    row = rows[0]
    assert row.user == person
    assert row.action == 'UPDATE'
    assert row.changes == {'phone': {'before': '+66 2 000 0000', 'after': '+66 2 111 2222'}}
    assert row.additional_data['kind'] == 'guarded_update'
    assert row.additional_data['expected_version'] == proposal['expected_version']
    assert row.additional_data['change_proposal_id'] == proposal['id']
    assert row.additional_data['change_proposal_proposer'] == 'theo'
    assert row.additional_data['applied_via'] == 'change_proposal'
    assert data['applied_audit_id'] == str(row.pk)
    assert data['applied_record_id'] == str(company.pk)


def test_accept_with_edits_applies_the_edited_value(agent, person, contact):
    proposal = propose(token_client(agent), kind='field_update', target_collection='contact',
                       target_id=str(contact.pk), patch={'title': 'Director', 'department': 'Ops'},
                       evidence_quote='I am now Director of Ops').json()
    client = session_client(person)
    path = f"{PROPOSALS}{proposal['id']}/accept-with-edits/"
    assert client.post(path, {}, format='json').status_code == 400
    outside = client.post(path, {'edits': {'email': 'x@example.com'}}, format='json')
    assert outside.status_code == 422 and outside.json()['code'] == 'edit_not_allowed'
    response = client.post(path, {'edits': {'title': 'Director of Operations'}, 'drop_fields': ['department']},
                           format='json')
    assert response.status_code == 200, response.content
    assert response.json()['status'] == 'edited'
    assert response.json()['patch'] == {'title': 'Director', 'department': 'Ops'}
    assert response.json()['applied_patch'] == {'title': 'Director of Operations'}
    contact.refresh_from_db()
    assert (contact.title, contact.department) == ('Director of Operations', '')


def test_plain_accept_does_not_take_edits(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    response = accept(session_client(person), proposal['id'], edits={'phone': '+66 2 999 9999'})
    assert response.status_code == 400
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'proposed'


def test_note_is_appended_not_replaced(agent, person, company):
    proposal = propose(token_client(agent), kind='note', target_collection='company', target_id=str(company.pk),
                       patch={'notes': 'Reception moves to the new wing in December.'},
                       evidence_quote='moving to the new wing in December').json()
    assert accept(session_client(person), proposal['id']).status_code == 200
    company.refresh_from_db()
    assert company.notes == 'Existing company note\n\nReception moves to the new wing in December.'


def test_new_contact_is_created_on_the_proposal_company(agent, person, company):
    from crm_app.models import Contact
    proposal = propose(token_client(agent), kind='new_contact', company_id=str(company.pk),
                       patch={'name': 'Kim Example', 'email': 'kim@riverside.example.com', 'title': 'Chief Engineer'},
                       evidence_quote='Kim is our new chief engineer').json()
    assert proposal['target_collection'] == 'contact' and proposal['target_id'] == ''
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 200, response.content
    created = Contact.objects.get(email='kim@riverside.example.com')
    assert created.company == company and created.title == 'Chief Engineer'
    assert response.json()['applied_record_id'] == str(created.pk)
    rows = _audit_for('Contact', created.pk)
    assert len(rows) == 1 and rows[0].action == 'CREATE' and rows[0].user == person
    assert rows[0].additional_data['change_proposal_id'] == proposal['id']
    assert rows[0].additional_data['applied_via'] == 'change_proposal'


def test_same_new_contact_email_is_one_proposal(agent, other_agent, company):
    first = propose(token_client(agent), kind='new_contact', company_id=str(company.pk),
                    patch={'name': 'Kim Example', 'email': 'kim@riverside.example.com'}, evidence_quote='Kim')
    second = propose(token_client(other_agent), kind='new_contact', company_id=str(company.pk),
                     patch={'name': 'Kim E.', 'email': 'KIM@riverside.example.com'}, evidence_quote='Kim')
    assert first.status_code == 201
    assert second.status_code == 409 and second.json()['code'] == 'duplicate_open'


def test_new_contact_with_an_existing_email_is_refused(agent, company, contact):
    response = propose(token_client(agent), kind='new_contact', company_id=str(company.pk),
                       patch={'name': 'Pat Again', 'email': contact.email}, evidence_quote='Pat')
    assert response.status_code == 422 and response.json()['code'] == 'invalid_value'


def test_task_is_created_with_the_reviewer_as_creator(agent, person, company, contact, other_company):
    from crm_app.models import Contact, Task
    body = dict(kind='task', company_id=str(company.pk),
                patch={'title': 'Call back about the new wing', 'priority': 'High',
                       'related_contact': str(contact.pk), 'due_date': '2026-12-01T09:00:00+07:00'},
                evidence_quote='please call me back next week')
    stranger = Contact.objects.create(company=other_company, name='Sam Example', email='sam@hilltop.example.com')
    wrong = propose(token_client(agent), **{**body, 'patch': {**body['patch'], 'related_contact': str(stranger.pk)}})
    assert wrong.status_code == 422 and wrong.json()['code'] == 'wrong_company'
    proposal = propose(token_client(agent), **body).json()
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 200, response.content
    task = Task.objects.get(pk=response.json()['applied_record_id'])
    assert (task.company, task.created_by, task.related_contact, task.priority) == (company, person, contact, 'High')
    assert task.status == 'To Do' and task.assigned_to is None


# ------------------------------------------------------------------ the record changed


def test_version_mismatch_applies_nothing_and_refreshes(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    company.city = 'Chiang Mai'
    company.save()
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 409
    assert response.json()['code'] == 'record_changed'
    row = ChangeProposal.objects.get(pk=proposal['id'])
    assert row.status == 'proposed'
    assert row.target_changed_at is not None
    assert row.expected_version != proposal['expected_version']
    assert response.json()['expected_version'] == row.expected_version
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'
    assert _audit_for('Company', company.pk) == []
    # A second, explicit click against the refreshed values applies it.
    again = accept(session_client(person), proposal['id'])
    assert again.status_code == 200, again.content
    company.refresh_from_db()
    assert company.phone == '+66 2 111 2222'


def test_changed_field_value_refreshes_current_values(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    company.phone = '+66 2 555 5555'
    company.save()
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 409
    assert response.json()['current_values'] == {'phone': '+66 2 555 5555'}


def test_record_already_holding_the_value_supersedes(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    company.phone = '+66 2 111 2222'
    company.save()
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 409 and response.json()['status'] == 'superseded'
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'superseded'


def test_deleted_target_marks_the_proposal_failed(agent, person, company, contact):
    proposal = propose(token_client(agent), kind='field_update', target_collection='contact',
                       target_id=str(contact.pk), patch={'title': 'Director'}, evidence_quote='Director').json()
    contact.delete()
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 409 and response.json()['code'] == 'target_missing'
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'failed'


def test_values_refused_at_apply_leave_the_proposal_open(agent, person, contact, company):
    from crm_app.models import Contact
    proposal = propose(token_client(agent), kind='field_update', target_collection='contact',
                       target_id=str(contact.pk), patch={'email': 'kim@riverside.example.com'},
                       evidence_quote='write to kim').json()
    Contact.objects.create(company=company, name='Kim Example', email='kim@riverside.example.com')
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 422 and response.json()['code'] == 'invalid_value'
    row = ChangeProposal.objects.get(pk=proposal['id'])
    assert row.status == 'proposed' and row.last_apply_error
    contact.refresh_from_db()
    assert contact.email == 'pat@riverside.example.com'


def test_apply_failure_rolls_back_the_target(agent, person, company, monkeypatch):
    from agent_inbox import proposals
    proposal = propose(token_client(agent), **phone_body(company)).json()

    def no_audit(*args, **kwargs):
        raise RuntimeError('audit tagging failed')

    monkeypatch.setattr(proposals, '_tag_audit', no_audit)
    with pytest.raises(RuntimeError):
        accept(session_client(person), proposal['id'])
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'proposed'


def test_allowlist_is_checked_again_at_accept(agent, person, company, monkeypatch):
    from agent_inbox import policy
    proposal = propose(token_client(agent), **phone_body(company)).json()
    narrowed = {**policy.PROPOSAL_ALLOWLIST, 'field_update': {'company': frozenset({'website'})}}
    monkeypatch.setattr(policy, 'PROPOSAL_ALLOWLIST', narrowed)
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 422 and response.json()['code'] == 'field_not_allowed'
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'


# ------------------------------------------------------------------ who may decide


@pytest.mark.parametrize('path', ['accept/', 'accept-with-edits/', 'reject/'])
def test_agent_accounts_cannot_decide(agent, other_agent, company, path):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    for client in (token_client(agent), session_client(other_agent), jwt_client(agent)):
        response = client.post(f"{PROPOSALS}{proposal['id']}/{path}",
                               {'reason': 'x', 'edits': {'phone': '+66 2 999 9999'}}, format='json')
        assert response.status_code in (403, 404), response.content
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'proposed'


def test_extra_agent_usernames_setting(person, company):
    from agent_inbox.tests.conftest import make_user
    robot = make_user('sheet-robot')
    proposal = propose(session_client(person), **phone_body(company)).json()
    with override_settings(AGENT_INBOX_AGENT_USERNAMES=['sheet-robot']):
        response = accept(session_client(robot), proposal['id'])
    assert response.status_code == 403 and response.json()['code'] == 'human_review_required'


def test_a_person_with_an_api_token_cannot_decide(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    response = accept(token_client(person), proposal['id'])
    assert response.status_code == 403
    assert response.json()['code'] == 'human_review_required'
    assert 'website sign-in' in response.json()['detail']


def test_agents_only_see_their_own_proposals(agent, other_agent, person, company, contact):
    propose(token_client(agent), **phone_body(company))
    propose(token_client(other_agent), kind='field_update', target_collection='contact',
            target_id=str(contact.pk), patch={'title': 'Director'}, evidence_quote='Director')
    assert token_client(agent).get(PROPOSALS).json()['count'] == 1
    assert token_client(other_agent).get(PROPOSALS).json()['count'] == 1
    assert session_client(person).get(PROPOSALS).json()['count'] == 2


# ------------------------------------------------------------------ reject, bulk reject, list


def test_reject_needs_a_reason_and_only_open_proposals(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    client = session_client(person)
    path = f"{PROPOSALS}{proposal['id']}/reject/"
    assert client.post(path, {}, format='json').status_code == 400
    response = client.post(path, {'reason': 'Number is for another branch'}, format='json')
    assert response.status_code == 200
    assert response.json()['status'] == 'rejected'
    assert response.json()['decision_note'] == 'Number is for another branch'
    again = client.post(path, {'reason': 'twice'}, format='json')
    assert again.status_code == 409 and again.json()['code'] == 'not_open'
    assert accept(client, proposal['id']).status_code == 409


def test_bulk_reject_by_batch_and_by_ids(agent, person, company, contact):
    client = token_client(agent)
    a = propose(client, **phone_body(company)).json()
    b = propose(client, kind='field_update', target_collection='contact', target_id=str(contact.pk),
                patch={'title': 'Director'}, evidence_quote='Director', batch_key='gmail:msg-0001').json()
    c = propose(client, kind='field_update', target_collection='contact', target_id=str(contact.pk),
                patch={'department': 'Ops'}, evidence_quote='Ops', batch_key='other-batch').json()
    reviewer = session_client(person)
    response = reviewer.post(f'{PROPOSALS}bulk-reject/', {'batch_key': 'gmail:msg-0001', 'reason': 'Spam'},
                             format='json')
    assert response.status_code == 200
    assert sorted(response.json()['rejected']) == sorted([a['id'], b['id']])
    missing = '00000000-0000-0000-0000-000000000009'
    response = reviewer.post(f'{PROPOSALS}bulk-reject/', {'ids': [a['id'], c['id'], missing], 'reason': 'No'},
                             format='json')
    assert response.json()['rejected'] == [c['id']]
    assert response.json()['skipped'] == [{'id': a['id'], 'status': 'rejected'}]
    assert response.json()['not_found'] == [missing]
    both = reviewer.post(f'{PROPOSALS}bulk-reject/', {'ids': [a['id']], 'batch_key': 'x', 'reason': 'No'},
                         format='json')
    assert both.status_code == 400
    assert token_client(agent).post(f'{PROPOSALS}bulk-reject/', {'batch_key': 'other-batch', 'reason': 'x'},
                                    format='json').status_code == 403


def test_list_filters(agent, person, company, contact):
    client = token_client(agent)
    propose(client, **phone_body(company))
    propose(client, kind='field_update', target_collection='contact', target_id=str(contact.pk),
            patch={'title': 'Director'}, evidence_quote='Director', batch_key='b-2')
    reader = session_client(person)
    assert reader.get(PROPOSALS, {'status': 'proposed'}).json()['count'] == 2
    assert reader.get(PROPOSALS, {'target_collection': 'contact'}).json()['count'] == 1
    assert reader.get(PROPOSALS, {'target_id': str(company.pk)}).json()['count'] == 1
    assert reader.get(PROPOSALS, {'proposer': 'THEO'}).json()['count'] == 2
    assert reader.get(PROPOSALS, {'batch_key': 'b-2'}).json()['count'] == 1
    assert reader.get(PROPOSALS, {'company': str(company.pk)}).json()['count'] == 2
    assert reader.get(PROPOSALS, {'page_size': 1}).json()['next']
    allowlist = reader.get(f'{PROPOSALS}allowlist/').json()
    assert allowlist['kinds']['field_update']['company'][0] == 'address_line1'
    assert allowlist['proposals_enabled'] is True


# ------------------------------------------------------------------ expiry


def test_expired_proposal_cannot_be_accepted(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    ChangeProposal.objects.filter(pk=proposal['id']).update(expires_at=timezone.now() - timedelta(seconds=1))
    response = accept(session_client(person), proposal['id'])
    assert response.status_code == 409 and response.json()['code'] == 'expired'
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'expired'
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'


def test_listing_and_the_command_expire_due_proposals(agent, person, company):
    from django.core.management import call_command
    from io import StringIO
    proposal = propose(token_client(agent), **phone_body(company)).json()
    ChangeProposal.objects.filter(pk=proposal['id']).update(expires_at=timezone.now() - timedelta(seconds=1))
    out = StringIO()
    call_command('expire_change_proposals', stdout=out)
    assert out.getvalue().strip() == 'expired=1'
    assert session_client(person).get(PROPOSALS, {'status': 'expired'}).json()['count'] == 1


# ------------------------------------------------------------------ switch


def test_switch_off_refuses_every_proposal_write_and_reads_work(agent, person, company):
    proposal = propose(token_client(agent), **phone_body(company)).json()
    with override_settings(CHANGE_PROPOSALS_ENABLED=False):
        created = propose(token_client(agent), **phone_body(company, patch={'phone': '+66 2 999 9999'}))
        accepted = accept(session_client(person), proposal['id'])
        rejected = session_client(person).post(f"{PROPOSALS}{proposal['id']}/reject/", {'reason': 'x'},
                                               format='json')
        listing = session_client(person).get(PROPOSALS)
    for response in (created, accepted, rejected):
        assert response.status_code == 403 and response.json()['code'] == 'not_enabled'
    assert listing.status_code == 200 and listing.json()['count'] == 1
    assert ChangeProposal.objects.get(pk=proposal['id']).status == 'proposed'


def test_nothing_in_the_app_sends_mail_or_calls_out(agent, person, company, monkeypatch):
    from django.core import mail
    import socket
    proposal = propose(token_client(agent), **phone_body(company)).json()

    def no_network(*args, **kwargs):
        raise AssertionError('network access attempted')

    monkeypatch.setattr(socket.socket, 'connect', no_network)
    assert accept(session_client(person), proposal['id']).status_code == 200
    assert mail.outbox == []
