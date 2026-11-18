"""Who decides, what a decision is bound to, superseding, conflicts, fingerprints and reopening."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from agent_inbox import policy
from agent_inbox.activities import record_activity
from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import (
    PROPOSALS, activity_body, decide, iso_ago, jwt_client, make_user, seen_of, session_client, token_client,
)


def phone(company, value='+66 2 111 2222', **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'our number'}
    body.update(extra)
    return body


# ------------------------------------------------------------------ who counts as an agent account


@pytest.mark.parametrize('username', ['theo', 'Theo', ' THEO ', 'Cira'])
def test_agent_usernames_are_matched_without_regard_to_case_or_spaces(username):
    assert policy.is_agent_account(make_user(username)) is True


def test_extra_agent_usernames_are_matched_without_regard_to_case():
    user = make_user('Sheet-Robot')
    with override_settings(AGENT_INBOX_AGENT_USERNAMES=['sheet-robot']):
        assert policy.is_agent_account(user) is True
    assert policy.is_agent_account(user) is False


@pytest.mark.parametrize('username', ['admin', 'funnel-desk', 'cіra'])
def test_any_account_holding_an_api_token_is_an_agent_account(username):
    from rest_framework.authtoken.models import Token
    user = make_user(username, role='Admin')
    assert policy.is_agent_account(user) is False
    Token.objects.create(user=user)
    assert policy.is_agent_account(user) is True


def test_a_token_account_cannot_propose_as_a_person_or_without_evidence(company):
    holder = make_user('admin', role='Admin')
    client = token_client(holder)
    as_human = client.post(PROPOSALS, phone(company, proposer_kind='human'), format='json')
    assert as_human.status_code == 403 and as_human.json()['code'] == 'proposer_kind_not_allowed'
    no_quote = client.post(PROPOSALS, phone(company, evidence_quote=''), format='json')
    assert no_quote.status_code == 422 and no_quote.json()['code'] == 'evidence_required'
    stored = client.post(PROPOSALS, phone(company), format='json')
    assert stored.status_code == 201 and stored.json()['proposer_kind'] == 'agent'


def test_a_token_account_gets_the_agent_read_rules(person, company):
    holder = make_user('admin', role='Admin')
    activity, _ = record_activity(person, activity_body(company), via='ui')
    create_proposal(person, phone(company, evidence_quote=''), via='ui')
    client = token_client(holder)
    detail = client.get(f'/api/v1/activities/{activity.pk}/').json()
    assert 'body' not in detail and 'source_url' not in detail
    assert client.get(PROPOSALS).json()['count'] == 0
    refused = client.post(f'/api/v1/activities/{activity.pk}/void/', {'reason': 'x'}, format='json')
    assert refused.status_code == 403


# ------------------------------------------------------------------ a reviewer is not a party


def test_a_reviewer_must_be_a_different_person_from_the_proposer(person, other_person, company):
    proposal, _ = create_proposal(person, phone(company, evidence_quote=''), via='ui')
    for action, body in (('accept', {}), ('reject', {'reason': 'x'})):
        refused = decide(jwt_client(person), proposal.pk, action, **body)
        assert refused.status_code == 403 and refused.json()['code'] == 'reviewer_is_party'
        assert 'different person from the proposer' in refused.json()['detail']
    assert decide(jwt_client(other_person), proposal.pk, 'accept').status_code == 200


def test_a_reviewer_must_not_have_recorded_the_evidence(agent, person, other_person, company):
    activity, _ = record_activity(person, activity_body(company), via='ui')
    proposal, _ = create_proposal(other_person, phone(company, evidence_quote='new reception number',
                                                      activity_id=str(activity.pk)), via='ui')
    refused = decide(jwt_client(person), proposal.pk, 'accept')
    assert refused.status_code == 403 and refused.json()['code'] == 'reviewer_is_party'
    third = make_user('third-person')
    assert decide(jwt_client(third), proposal.pk, 'accept').status_code == 200


def test_bulk_reject_skips_proposals_the_reviewer_is_party_to(person, other_person, company):
    own, _ = create_proposal(person, phone(company, evidence_quote=''), via='ui')
    response = session_client(person).post(f'{PROPOSALS}bulk-reject/', {
        'items': [{'id': str(own.pk), 'seen_version': seen_of(own.pk)}], 'reason': 'x'}, format='json')
    assert response.json()['skipped'] == [{'id': str(own.pk), 'status': 'proposed', 'code': 'reviewer_is_party'}]


# ------------------------------------------------------------------ decisions carry what was seen


@pytest.mark.parametrize('action, body', [
    ('accept', {}), ('accept-with-edits', {'edits': {'phone': '+66 2 999 9999'}}), ('reject', {'reason': 'x'}),
])
def test_every_decision_needs_the_seen_version(agent, person, company, action, body):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    client = session_client(person)
    missing = client.post(f'{PROPOSALS}{proposal.pk}/{action}/', body, format='json')
    assert missing.status_code == 400
    stale = client.post(f'{PROPOSALS}{proposal.pk}/{action}/', {**body, 'seen_version': 'something-else'},
                        format='json')
    assert stale.status_code == 409 and stale.json()['code'] == 'stale_view'
    assert stale.json()['proposal']['seen_version'] == seen_of(proposal.pk)
    proposal.refresh_from_db()
    assert proposal.status == 'proposed'
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'


def test_the_seen_version_is_returned_with_every_read(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    client = session_client(person)
    assert client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version'] == seen_of(proposal.pk)
    assert client.get(PROPOSALS).json()['results'][0]['seen_version'] == seen_of(proposal.pk)


def test_a_double_click_applies_once(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    client = session_client(person)
    seen = seen_of(proposal.pk)
    first = client.post(f'{PROPOSALS}{proposal.pk}/accept/', {'seen_version': seen}, format='json')
    second = client.post(f'{PROPOSALS}{proposal.pk}/accept/', {'seen_version': seen}, format='json')
    assert first.status_code == 200
    assert second.status_code == 409 and second.json()['code'] == 'not_open'


# ------------------------------------------------------------------ superseding and conflicts


def test_another_proposers_value_does_not_supersede_and_both_show_as_conflicting(agent, other_agent, person,
                                                                                 company):
    first, _ = create_proposal(agent, phone(company), via='rest')
    second, _ = create_proposal(other_agent, phone(company, value='+66 2 666 6666'), via='rest')
    first.refresh_from_db()
    assert first.status == 'proposed' and second.status == 'proposed'
    listing = session_client(person).get(PROPOSALS, {'status': 'proposed'}).json()['results']
    by_id = {row['id']: row for row in listing}
    assert [c['id'] for c in by_id[str(first.pk)]['conflicts_with']] == [str(second.pk)]
    assert by_id[str(first.pk)]['conflicts_with'][0]['patch'] == {'phone': '+66 2 666 6666'}
    assert [c['id'] for c in by_id[str(second.pk)]['conflicts_with']] == [str(first.pk)]
    detail = session_client(person).get(f'{PROPOSALS}{first.pk}/').json()
    assert [c['id'] for c in detail['conflicts_with']] == [str(second.pk)]
    # An agent sees only its own proposals, so no conflict with someone else's is listed.
    own = token_client(agent).get(f'{PROPOSALS}{first.pk}/').json()
    assert own['conflicts_with'] == []


def test_the_same_proposers_newer_evidence_supersedes(agent, company):
    older, _ = create_proposal(agent, phone(company, evidence_occurred_at=iso_ago(days=3)), via='rest')
    newer, _ = create_proposal(agent, phone(company, value='+66 2 333 4444', evidence_occurred_at=iso_ago(days=1)),
                               via='rest')
    older.refresh_from_db()
    assert older.status == 'superseded' and older.superseded_by_id == newer.pk


def test_older_evidence_never_supersedes_newer(agent, company):
    newer, _ = create_proposal(agent, phone(company, evidence_occurred_at=iso_ago(days=1)), via='rest')
    older, _ = create_proposal(agent, phone(company, value='+66 2 333 4444', evidence_occurred_at=iso_ago(days=5)),
                               via='rest')
    newer.refresh_from_db()
    assert newer.status == 'proposed' and older.status == 'proposed'
    unknown, _ = create_proposal(agent, phone(company, value='+66 2 555 5555'), via='rest')
    newer.refresh_from_db()
    assert newer.status == 'proposed'


def test_evidence_time_comes_from_the_linked_activity(agent, company):
    activity, _ = record_activity(agent, activity_body(company, occurred_at='2026-11-01T09:00:00+07:00'), via='rest')
    proposal, _ = create_proposal(agent, phone(company, evidence_quote='new reception number',
                                               activity_id=str(activity.pk)), via='rest')
    assert proposal.evidence_occurred_at == activity.occurred_at


# ------------------------------------------------------------------ fingerprints and reopening


@pytest.mark.parametrize('first, second', [
    ({'phone': '+66 2 111 2222'}, {'phone': '+66  2 111 2222'}),
    ({'phone': '+66 2 111 2222'}, {'phone': '+66-2-111-2222'}),
    ({'email': 'desk@riverside.example.com'}, {'email': 'Desk@Riverside.Example.com'}),
    ({'website': 'https://riverside.example.com/'}, {'website': 'HTTPS://Riverside.Example.com'}),
    ({'city': 'Chiang  Mai'}, {'city': 'Chiang Mai'}),
])
def test_meaningless_spacing_and_case_do_not_make_a_new_proposal(agent, other_agent, company, first, second):
    create_proposal(agent, phone(company, patch=first), via='rest')
    response = token_client(other_agent).post(PROPOSALS, phone(company, patch=second), format='json')
    assert response.status_code == 409 and response.json()['code'] == 'duplicate_open'


def test_case_in_a_city_name_still_counts(agent, other_agent, company):
    create_proposal(agent, phone(company, patch={'city': 'chiang mai'}), via='rest')
    response = token_client(other_agent).post(PROPOSALS, phone(company, patch={'city': 'Chiang Mai'}), format='json')
    assert response.status_code == 201


def test_a_person_reopens_a_rejected_proposal(agent, person, other_person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    assert decide(session_client(person), proposal.pk, 'reject', reason='Looked wrong').status_code == 200
    refused = decide(token_client(agent), proposal.pk, 'reopen', note='please')
    assert refused.status_code == 403
    assert decide(session_client(other_person), proposal.pk, 'reopen').status_code == 400
    reopened = decide(session_client(other_person), proposal.pk, 'reopen', note='Customer confirmed by phone')
    assert reopened.status_code == 200, reopened.content
    data = reopened.json()
    assert data['status'] == 'proposed' and data['reviewer_username'] == '' and data['decision_note'] == ''
    assert [entry['action'] for entry in data['history']] == ['rejected', 'reopened']
    assert data['history'][0]['note'] == 'Looked wrong'
    assert decide(session_client(person), proposal.pk, 'accept').status_code == 200
    again = decide(session_client(person), proposal.pk, 'reopen', note='x')
    assert again.status_code == 409 and again.json()['code'] == 'not_rejected'


def test_reopen_needs_the_seen_version(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    decide(session_client(person), proposal.pk, 'reject', reason='no')
    stale = session_client(person).post(f'{PROPOSALS}{proposal.pk}/reopen/', {'note': 'x', 'seen_version': 'old'},
                                        format='json')
    assert stale.status_code == 409 and stale.json()['code'] == 'stale_view'


# ------------------------------------------------------------------ task relations at accept


def test_task_relations_are_checked_again_at_accept(agent, person, company, other_company, contact):
    from crm_app.models import Contact, Task
    foreign = Contact.objects.create(company=other_company, name='Sam Example', email='sam@hilltop.example.com')
    proposal, _ = create_proposal(agent, {'kind': 'task', 'company_id': str(company.pk),
                                          'patch': {'title': 'Call back', 'related_contact': str(contact.pk)},
                                          'evidence_quote': 'call me'}, via='rest')
    edited = decide(session_client(person), proposal.pk, 'accept-with-edits',
                    edits={'related_contact': str(foreign.pk)})
    assert edited.status_code == 422 and edited.json()['code'] == 'wrong_company'
    Contact.objects.filter(pk=contact.pk).update(company=other_company)
    moved = decide(session_client(person), proposal.pk, 'accept')
    assert moved.status_code == 422 and moved.json()['code'] == 'wrong_company'
    proposal.refresh_from_db()
    assert proposal.status == 'proposed' and proposal.last_apply_error
    assert not Task.objects.filter(title='Call back').exists()


def test_expiry_resets_on_reopen(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    decide(session_client(person), proposal.pk, 'reject', reason='no')
    ChangeProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(days=1))
    decide(session_client(make_user('third-person')), proposal.pk, 'reopen', note='again')
    proposal.refresh_from_db()
    assert proposal.expires_at > timezone.now() + timedelta(days=20)
