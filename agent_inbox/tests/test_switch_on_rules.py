"""Rules that must hold before proposals are switched on: who reviews, what a view binds to, citing."""
import pytest
from django.core.checks import run_checks
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from agent_inbox import policy
from agent_inbox.activities import record_activity
from agent_inbox.proposals import create_proposal, seen_version
from agent_inbox.tests.conftest import (
    PROPOSALS, activity_body, decide, jwt_client, make_user, seen_of, session_client, token_client,
)


def phone(company, value='+66 2 111 2222', **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'our number'}
    body.update(extra)
    return body


def staff_with_token(username='admin'):
    user = make_user(username, role='Admin')
    user.is_staff = user.is_superuser = True
    user.set_password('pw-staff-123456')
    user.save()
    Token.objects.get_or_create(user=user)
    return user


# ------------------------------------------------------------------ user management needs a website sign-in


def test_a_staff_token_cannot_create_change_or_delete_users(person):
    admin = staff_with_token()
    client = token_client(admin)
    created = client.post('/api/v1/users/', {'username': 'ops-helper', 'email': 'ops-helper@example.test',
                                             'password': 'pw-helper-123456', 'role': 'Admin'}, format='json')
    assert created.status_code == 403
    assert 'website sign-in' in created.json()['detail']
    for method, body in (('patch', {'password': 'pw-taken-123456'}), ('put', {'username': person.username}),
                         ('delete', None)):
        response = getattr(client, method)(f'/api/v1/users/{person.pk}/', body, format='json')
        assert response.status_code == 403, method
    person.refresh_from_db()
    assert not person.check_password('pw-taken-123456')


def test_reading_users_with_a_token_still_works():
    client = token_client(staff_with_token())
    assert client.get('/api/v1/users/').status_code == 200


def test_a_staff_person_on_the_website_manages_users(person):
    admin = make_user('site-admin', role='Admin')
    admin.is_staff = True
    admin.save()
    client = jwt_client(admin)
    created = client.post('/api/v1/users/', {'username': 'new-colleague', 'email': 'new@example.test',
                                             'password': 'pw-colleague-123', 'role': 'Sales'}, format='json')
    assert created.status_code == 201, created.content
    assert client.patch(f"/api/v1/users/{created.json()['id']}/", {'is_active': False},
                        format='json').status_code == 200
    assert session_client(admin).delete(f"/api/v1/users/{created.json()['id']}/").status_code == 204


def test_an_agent_named_account_cannot_manage_users_even_from_the_website():
    agent = make_user('cira', role='Admin')
    agent.is_staff = True
    agent.save()
    response = jwt_client(agent).post('/api/v1/users/', {'username': 'x', 'email': 'x@example.test',
                                                         'password': 'pw-x-12345678'}, format='json')
    assert response.status_code == 403


# ------------------------------------------------------------------ the reviewer list


def test_with_no_reviewer_list_nobody_reviews(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    with override_settings(CHANGE_PROPOSAL_REVIEWER_USERNAMES=[]):
        response = decide(session_client(person), proposal.pk, 'accept')
        status = session_client(person).get(f'{PROPOSALS}allowlist/').json()
    assert response.status_code == 403 and response.json()['code'] == 'review_not_configured'
    assert response.json()['detail'] == 'Reviewing is not set up yet.'  # no setting name for non-staff
    assert status['you_can_review'] is False and status['reviewing_configured'] is False


def test_a_person_not_on_the_list_cannot_review(agent, company):
    outsider = make_user('not-listed-person')
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    response = decide(session_client(outsider), proposal.pk, 'accept')
    assert response.status_code == 403 and response.json()['code'] == 'not_a_reviewer'


def test_a_freshly_created_account_cannot_review(agent, company):
    admin = make_user('site-admin', role='Admin')
    admin.is_staff = True
    admin.save()
    jwt_client(admin).post('/api/v1/users/', {'username': 'ops-helper', 'email': 'ops-helper@example.test',
                                              'password': 'pw-helper-123456', 'role': 'Admin'}, format='json')
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    login = APIClient().post('/api/v1/jwt/token/', {'username': 'ops-helper', 'password': 'pw-helper-123456'},
                             format='json')
    helper = APIClient()
    helper.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])
    response = helper.post(f'{PROPOSALS}{proposal.pk}/accept/', {'seen_version': seen_of(proposal.pk)},
                           format='json')
    assert response.status_code == 403 and response.json()['code'] == 'not_a_reviewer'
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'


def test_agent_names_on_the_reviewer_list_are_ignored_and_reported(agent, company):
    proposal, _ = create_proposal(make_user('second-person'), phone(company, evidence_quote=''), via='ui')
    with override_settings(CHANGE_PROPOSAL_REVIEWER_USERNAMES=['reviewer-person', 'Theo']):
        assert 'theo' not in policy.listed_reviewer_names()
        warnings = [m for m in run_checks() if m.id == 'agent_inbox.W001']
        assert len(warnings) == 1 and 'theo' in warnings[0].msg
        response = decide(jwt_client(agent), proposal.pk, 'accept')
    assert response.status_code == 403 and response.json()['code'] == 'human_review_required'
    assert not [m for m in run_checks() if m.id == 'agent_inbox.W001']


def test_a_listed_reviewer_keeps_review_rights_when_given_a_token(agent, person, company):
    Token.objects.create(user=person)
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    assert policy.is_agent_account(person) is False
    status = jwt_client(person).get(f'{PROPOSALS}allowlist/').json()
    assert status['you_can_review'] is True and status['treated_as_agent'] is False
    by_token = decide(token_client(person), proposal.pk, 'accept')
    assert by_token.status_code == 403 and 'website sign-in' in by_token.json()['detail']
    assert decide(jwt_client(person), proposal.pk, 'accept').status_code == 200


def test_an_unlisted_person_with_a_token_is_told_why(company):
    outsider = make_user('token-person')
    Token.objects.create(user=outsider)
    status = jwt_client(outsider).get(f'{PROPOSALS}allowlist/').json()
    assert status['treated_as_agent'] is True
    assert status['treated_as_agent_because'] == 'holds an API token and is not a listed reviewer'
    assert status['you_can_review'] is False and status['review_refusal']


# ------------------------------------------------------------------ what a view binds to


def test_a_read_refreshes_the_snapshot_when_the_target_changed(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    client = session_client(person)
    before = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    again = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert again['seen_version'] == before['seen_version']
    proposal.refresh_from_db()
    unchanged_at = proposal.updated_at
    company.phone = '+66 2 555 5555'
    company.save()
    after = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert after['current_values'] == {'phone': '+66 2 555 5555'}
    assert after['seen_version'] != before['seen_version'] and after['target_changed_at']
    listed = client.get(PROPOSALS).json()['results'][0]
    assert listed['seen_version'] == after['seen_version']
    stale = decide(client, proposal.pk, 'accept', seen_version=before['seen_version'])
    assert stale.status_code == 409 and stale.json()['code'] == 'stale_view'
    proposal.refresh_from_db()
    assert proposal.updated_at > unchanged_at
    assert decide(client, proposal.pk, 'accept', seen_version=after['seen_version']).status_code == 200


def test_reads_do_not_write_when_nothing_changed(agent, person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    proposal.refresh_from_db()
    stamp = proposal.updated_at
    session_client(person).get(PROPOSALS)
    session_client(person).get(f'{PROPOSALS}{proposal.pk}/')
    proposal.refresh_from_db()
    assert proposal.updated_at == stamp


def test_a_view_loaded_before_a_rejection_cannot_accept_after_a_reopen(agent, person, other_person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    loaded = seen_of(proposal.pk)
    decide(session_client(person), proposal.pk, 'reject', reason='Wrong number')
    decide(session_client(other_person), proposal.pk, 'reopen', note='Customer confirmed')
    assert seen_of(proposal.pk) != loaded
    response = session_client(make_user('third-person')).post(
        f'{PROPOSALS}{proposal.pk}/accept/', {'seen_version': loaded}, format='json')
    assert response.status_code == 409 and response.json()['code'] == 'stale_view'


@pytest.mark.parametrize('change', ['current_values', 'target_changed_at', 'status', 'history', 'patch',
                                    'target_state'])
def test_each_part_of_the_snapshot_changes_the_seen_version(agent, company, change):
    from django.utils import timezone
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    before = seen_version(proposal)
    if change == 'current_values':
        proposal.current_values = {'phone': 'other'}
    elif change == 'target_changed_at':
        proposal.target_changed_at = timezone.now()
    elif change == 'status':
        proposal.status = 'rejected'
    elif change == 'history':
        proposal.history = [{'action': 'rejected', 'by': 'x', 'at': 'now', 'note': ''}]
    elif change == 'patch':
        proposal.patch = {'phone': 'other'}
    else:
        proposal.target_state = 'missing'
    assert seen_version(proposal) != before


def test_the_record_version_alone_does_not_change_the_seen_version(agent, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    before = seen_version(proposal)
    proposal.expected_version = '2000-01-01T00:00:00Z'
    assert seen_version(proposal) == before


def test_reopen_when_the_same_change_is_open_again_is_a_clean_409(agent, person, other_person, company):
    proposal, _ = create_proposal(agent, phone(company), via='rest')
    decide(session_client(person), proposal.pk, 'reject', reason='no')
    create_proposal(make_user('fourth-person'), phone(company, evidence_quote=''), via='ui')
    response = decide(session_client(other_person), proposal.pk, 'reopen', note='again')
    assert response.status_code == 409 and response.json()['code'] == 'duplicate_open'
    proposal.refresh_from_db()
    assert proposal.status == 'rejected'


# ------------------------------------------------------------------ citing captured activities


def test_an_agent_cites_a_captured_activity_and_the_evidence_is_captured(agent, company):
    capture = make_user('capture-job')
    activity, _ = record_activity(capture, activity_body(company), via='job')
    detail = token_client(agent).get(f'/api/v1/activities/{activity.pk}/').json()
    assert 'body' in detail
    response = token_client(agent).post(PROPOSALS, phone(company, evidence_quote='new reception number',
                                                         activity_id=str(activity.pk)), format='json')
    assert response.status_code == 201, response.content
    assert response.json()['evidence'] == 'verified_captured'
    wrong = token_client(agent).post(PROPOSALS, phone(company, value='+66 2 999 9999', evidence_quote='not there',
                                                      activity_id=str(activity.pk)), format='json')
    assert wrong.status_code == 422 and wrong.json()['code'] == 'quote_not_verbatim'


def test_restricted_and_other_agents_activities_still_get_one_answer(agent, other_agent, company):
    capture = make_user('capture-job')
    restricted, _ = record_activity(capture, activity_body(company, restricted=True), via='job')
    theirs, _ = record_activity(other_agent, activity_body(company, idempotency_key='test:other-0001',
                                                           source_ref=''), via='rest')
    answers = set()
    for activity_id in (restricted.pk, theirs.pk, '00000000-0000-0000-0000-00000000abcd'):
        for quote in ('new reception number', 'nothing like it'):
            response = token_client(agent).post(PROPOSALS, phone(company, evidence_quote=quote,
                                                                 activity_id=str(activity_id)), format='json')
            answers.add((response.status_code, response.json()['code'], response.json()['detail']))
    assert len(answers) == 1 and answers.pop()[1] == 'activity_not_usable'
    detail = token_client(agent).get(f'/api/v1/activities/{restricted.pk}/').json()
    assert 'body' not in detail


# ------------------------------------------------------------------ text warnings


@pytest.mark.parametrize('value, warned', [
    ('Pat Example', False), ('Café Zoë', False), ('ถนนสุขุมวิท Soi 11', False),
    ('Pаt Example', True), ('Shalom שלום', True), ('Αlpha Hotel', True),
])
def test_mixed_scripts_are_flagged_for_the_reviewer(agent, person, contact, value, warned):
    response = token_client(agent).post(PROPOSALS, {
        'kind': 'field_update', 'target_collection': 'contact', 'target_id': str(contact.pk),
        'patch': {'title': value}, 'evidence_quote': 'q',
    }, format='json')
    assert response.status_code == 201, response.content
    codes = [w['code'] for w in session_client(person).get(f"{PROPOSALS}{response.json()['id']}/").json()['warnings']]
    assert codes == (['mixed_script'] if warned else [])
