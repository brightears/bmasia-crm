"""Evidence and provenance: which activities a proposal may cite, and who wrote what."""
import pytest
from django.test import override_settings

from agent_inbox.activities import record_activity
from agent_inbox.models import Activity, ChangeProposal, ProposalRefusal
from agent_inbox.proposals import create_proposal
from agent_inbox.tests.conftest import (
    ACTIVITIES, PROPOSALS, activity_body, jwt_client, make_user, session_client, token_client,
)

SECRET = 'Private: the renewal discount we can offer is 17 percent.'


def phone(company, value='+66 2 111 2222', **extra):
    body = {'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch': {'phone': value}, 'evidence_quote': 'our number'}
    body.update(extra)
    return body


# ------------------------------------------------------------------ which activities a proposal may cite


def test_an_agent_cites_only_activities_it_recorded(agent, other_agent, company):
    theirs, _ = record_activity(agent, activity_body(company, body=SECRET), via='rest')
    client = token_client(other_agent)
    codes = set()
    for quote in ('discount we can offer is 12', 'discount we can offer is 17'):
        for value in (company.phone, '+66 2 999 9999'):
            response = client.post(PROPOSALS, phone(company, value=value, evidence_quote=quote,
                                                    activity_id=str(theirs.pk)), format='json')
            codes.add((response.status_code, response.json()['code'], response.json()['detail']))
    assert len(codes) == 1
    status, code, _ = codes.pop()
    assert (status, code) == (422, 'activity_not_usable')
    assert ChangeProposal.objects.count() == 0


def test_unusable_activities_all_get_the_same_answer(agent, other_agent, company, other_company):
    own_void, _ = record_activity(other_agent, activity_body(company, idempotency_key='test:void-0001',
                                                             source_ref=''), via='rest')
    own_void.is_void = True
    own_void.save()
    other_company_row, _ = record_activity(other_agent, activity_body(other_company, source_ref=''), via='rest')
    foreign, _ = record_activity(agent, activity_body(company, idempotency_key='test:foreign-01', source_ref=''),
                                 via='rest')
    answers = set()
    for activity_id in (own_void.pk, other_company_row.pk, foreign.pk, '00000000-0000-0000-0000-00000000abcd'):
        response = token_client(other_agent).post(PROPOSALS, phone(company, activity_id=str(activity_id)),
                                                  format='json')
        answers.add((response.status_code, response.json()['code'], response.json()['detail']))
    assert len(answers) == 1 and answers.pop()[1] == 'activity_not_usable'


def test_refused_attempts_count_towards_the_daily_cap(agent, other_agent, company):
    theirs, _ = record_activity(agent, activity_body(company, body=SECRET), via='rest')
    client = token_client(other_agent)
    with override_settings(CHANGE_PROPOSALS_DAILY_CAP=3):
        codes = [client.post(PROPOSALS, phone(company, evidence_quote=f'guess {i}', activity_id=str(theirs.pk)),
                             format='json').json()['code'] for i in range(4)]
        allowed = client.post(PROPOSALS, phone(company), format='json')
    assert codes == ['activity_not_usable'] * 3 + ['daily_cap']
    assert allowed.status_code == 429
    assert ProposalRefusal.objects.filter(proposer=other_agent).count() == 3


def test_a_person_may_cite_any_activity_and_quotes_are_checked(agent, person, company):
    theirs, _ = record_activity(agent, activity_body(company), via='rest')
    wrong = session_client(person).post(PROPOSALS, phone(company, evidence_quote='not in the text',
                                                         activity_id=str(theirs.pk)), format='json')
    assert wrong.status_code == 422 and wrong.json()['code'] == 'quote_not_verbatim'
    right = session_client(person).post(PROPOSALS, phone(company, evidence_quote='new reception number',
                                                         activity_id=str(theirs.pk)), format='json')
    assert right.status_code == 201 and right.json()['evidence_verified'] is True


def test_no_quote_means_not_verified(person, company):
    activity, _ = record_activity(make_user('capture-job'), activity_body(company), via='job')
    response = session_client(person).post(PROPOSALS, phone(company, evidence_quote='',
                                                            activity_id=str(activity.pk)), format='json')
    assert response.status_code == 201
    assert response.json()['evidence_verified'] is False and response.json()['evidence'] == 'unverified'


# ------------------------------------------------------------------ provenance comes from the server


def test_recorded_via_follows_the_route(agent, person, company):
    by_token = token_client(agent).post(ACTIVITIES, activity_body(company), format='json').json()
    by_website = jwt_client(person).post(ACTIVITIES, activity_body(company, idempotency_key='test:web-0001',
                                                                     source_ref=''), format='json').json()
    by_job, _ = record_activity(make_user('capture-job'), activity_body(company, source_ref='',
                                                                         idempotency_key='test:job-0001'), via='job')
    assert (by_token['recorded_via'], by_website['recorded_via'], by_job.recorded_via) == ('rest', 'ui', 'job')
    refused = token_client(agent).post(ACTIVITIES, activity_body(company, recorded_via='ui',
                                                                 idempotency_key='test:claim-01'), format='json')
    assert refused.status_code == 400 and 'recorded_via' in refused.json()['detail']


@pytest.mark.parametrize('system', ['manual', 'crm'])
def test_agents_cannot_claim_a_person_wrote_the_text(agent, person, company, system):
    refused = token_client(agent).post(ACTIVITIES, activity_body(company, source_system=system, source_ref=''),
                                       format='json')
    assert refused.status_code == 422 and refused.json()['code'] == 'source_not_allowed'
    allowed = jwt_client(person).post(ACTIVITIES, activity_body(company, source_system=system, source_ref=''),
                                      format='json')
    assert allowed.status_code == 201


def test_evidence_source_must_match_the_linked_activity(agent, company):
    activity, _ = record_activity(agent, activity_body(company, source_system='agent', source_ref='',
                                                       body='phone is +66 2 111 2222'), via='rest')
    for extra in ({'evidence_source_system': 'gmail'}, {'evidence_source_ref': 'other-ref'},
                  {'evidence_source_url': 'https://mail.example.com/x'},
                  {'evidence_occurred_at': '2026-01-01T00:00:00+00:00'}):
        response = token_client(agent).post(PROPOSALS, phone(company, evidence_quote='phone is +66 2 111 2222',
                                                             activity_id=str(activity.pk), **extra), format='json')
        assert response.status_code == 422 and response.json()['code'] == 'evidence_source_mismatch', extra
    same = token_client(agent).post(PROPOSALS, phone(company, evidence_quote='phone is +66 2 111 2222',
                                                     activity_id=str(activity.pk), evidence_source_system='agent'),
                                    format='json')
    assert same.status_code == 201
    assert same.json()['evidence_source_system'] == 'agent'


def test_the_proposal_says_who_recorded_the_evidence(agent, person, company):
    own, _ = record_activity(agent, activity_body(company), via='rest')
    by_agent = token_client(agent).post(PROPOSALS, phone(company, evidence_quote='new reception number',
                                                         activity_id=str(own.pk)), format='json').json()
    captured, _ = record_activity(make_user('capture-job'), activity_body(
        company, idempotency_key='test:capture-01', source_ref='msg-0002@mail.example.com'), via='job')
    by_person = session_client(person).post(PROPOSALS, phone(company, value='+66 2 333 4444',
                                                             evidence_quote='new reception number',
                                                             activity_id=str(captured.pk)), format='json').json()
    unverified = token_client(agent).post(PROPOSALS, phone(company, value='+66 2 555 5555'), format='json').json()
    reader = session_client(make_user('third-person'))
    a = reader.get(f"{PROPOSALS}{by_agent['id']}/").json()
    b = reader.get(f"{PROPOSALS}{by_person['id']}/").json()
    c = reader.get(f"{PROPOSALS}{unverified['id']}/").json()
    assert (a['evidence'], a['evidence_recorded_by'], a['evidence_recorded_via'], a['evidence_recorder_is_agent']) \
        == ('verified_agent_recorded', 'theo', 'rest', True)
    assert (b['evidence'], b['evidence_recorded_by'], b['evidence_recorded_via'], b['evidence_recorder_is_agent']) \
        == ('verified_captured', 'capture-job', 'job', False)
    assert (c['evidence'], c['evidence_recorded_by']) == ('unverified', None)
    # A voided activity no longer counts as verified evidence.
    Activity.objects.filter(pk=own.pk).update(is_void=True)
    assert reader.get(f"{PROPOSALS}{by_agent['id']}/").json()['evidence'] == 'unverified'


# ------------------------------------------------------------------ the same source recorded twice


def test_a_capture_replaces_an_agents_earlier_record_of_the_same_message(agent, company):
    agent_row, _ = record_activity(agent, activity_body(company, body='typed by an agent'), via='rest')
    captured, replayed = record_activity(make_user('capture-job'), activity_body(
        company, idempotency_key='test:capture-01', body='captured text'), via='job')
    assert replayed is False
    agent_row.refresh_from_db()
    assert agent_row.is_void and agent_row.duplicate_of_id == captured.pk
    assert Activity.objects.filter(source_ref=captured.source_ref, is_void=False).get() == captured


def test_an_agent_cannot_displace_a_captured_record(agent, company):
    record_activity(make_user('capture-job'), activity_body(company), via='job')
    response = token_client(agent).post(ACTIVITIES, activity_body(company, idempotency_key='test:late-0001'),
                                        format='json')
    assert response.status_code == 409 and response.json()['code'] == 'source_already_recorded'


def test_two_agents_still_cannot_record_the_same_message(agent, other_agent, company):
    record_activity(agent, activity_body(company), via='rest')
    response = token_client(other_agent).post(ACTIVITIES, activity_body(company), format='json')
    assert response.status_code == 409


# ------------------------------------------------------------------ gmail references are Message-IDs


@pytest.mark.parametrize('given, stored', [
    ('<CAB123.456@mail.example.com>', 'CAB123.456@mail.example.com'),
    ('  <CAB123.456@mail.example.com>  ', 'CAB123.456@mail.example.com'),
    ('CAB123.456@Mail.Example.com', 'CAB123.456@Mail.Example.com'),
    ('<a@b> (comment)', 'a@b'),
])
def test_gmail_refs_are_stored_in_the_shared_canonical_form(agent, company, given, stored):
    response = token_client(agent).post(ACTIVITIES, activity_body(company, source_ref=given), format='json')
    assert response.status_code == 201, response.content
    assert response.json()['source_ref'] == stored


@pytest.mark.parametrize('given', ['18c2a4f0b1d2e3f4', 'synthetic:' + 'a' * 64])
def test_gmail_api_ids_and_capture_internal_keys_are_refused(agent, company, given):
    response = token_client(agent).post(ACTIVITIES, activity_body(company, source_ref=given), format='json')
    assert response.status_code == 400 and 'Message-ID' in response.json()['detail']


def test_message_id_comparison_is_case_sensitive(agent, other_agent, company):
    record_activity(agent, activity_body(company, source_ref='<Abc@mail.example.com>'), via='rest')
    response = token_client(other_agent).post(ACTIVITIES, activity_body(company, source_ref='abc@mail.example.com'),
                                              format='json')
    assert response.status_code == 201


def test_proposal_evidence_refs_follow_the_same_rule(agent, company):
    bad = token_client(agent).post(PROPOSALS, phone(company, evidence_source_system='gmail',
                                                    evidence_source_ref='18c2a4f0b1d2e3f4'), format='json')
    assert bad.status_code == 400
    good = token_client(agent).post(PROPOSALS, phone(company, evidence_source_system='gmail',
                                                     evidence_source_ref='<m1@mail.example.com>'), format='json')
    assert good.status_code == 201 and good.json()['evidence_source_ref'] == 'm1@mail.example.com'
