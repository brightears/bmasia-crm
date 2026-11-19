"""Inactive targets need an explicit acknowledgement; refusals leave the watched state alone; agents' reads."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal, seen_version
from agent_inbox.tests.conftest import PROPOSALS, decide, jwt_client, seen_of, token_client
from agent_inbox.validation import url_warnings
from crm_app.models import Company, Contact

CONTACT_REASON = ('This contact is inactive: nothing is emailed to it until someone activates it. '
                  'Applying the change keeps it inactive.')
COMPANY_REASON = 'This company is marked inactive. Applying the change keeps it inactive.'


def _field(target, collection, field, value):
    return {'kind': 'field_update', 'target_collection': collection, 'target_id': str(target.pk),
            'patch': {field: value}, 'evidence_quote': 'as written'}


def _note(target, collection, text='Prefers calls in the afternoon'):
    return {'kind': 'note', 'target_collection': collection, 'target_id': str(target.pk),
            'patch': {'notes': text}, 'evidence_quote': 'as written'}


def _row(proposal):
    return ChangeProposal.objects.get(pk=proposal.pk)


# ------------------------------------------------------------------ inactive: acknowledge, never activate


@pytest.mark.parametrize('collection', ['company', 'contact'])
@pytest.mark.parametrize('route', ['accept', 'accept-with-edits'])
def test_an_inactive_record_needs_the_acknowledgement_and_stays_inactive(agent, person, company, contact,
                                                                        collection, route):
    target = company if collection == 'company' else contact
    field, value = ('city', 'Chiang Mai') if collection == 'company' else ('title', 'Director')
    proposal = create_proposal(agent, _field(target, collection, field, value), via='rest')[0]
    type(target).objects.filter(pk=target.pk).update(is_active=False)
    client = jwt_client(person)
    shown = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    reason = COMPANY_REASON if collection == 'company' else CONTACT_REASON
    assert (shown['target_state'], shown['target_state_reason']) == ('inactive', reason)
    before = _row(proposal)
    extra = {'edits': {field: value}} if route == 'accept-with-edits' else {}
    refused = decide(client, proposal.pk, route, seen_version=shown['seen_version'], **extra)
    body = refused.json()
    assert (refused.status_code, body['code'], body['acknowledge']) == (409, 'needs_acknowledgement',
                                                                        'acknowledge_inactive')
    assert body['detail'].startswith(reason) and body['target_state_reason'] == reason
    after = _row(proposal)
    assert (after.status, after.target_state, after.target_changed_at, after.last_apply_error) == (
        before.status, before.target_state, before.target_changed_at, before.last_apply_error)
    assert seen_of(proposal.pk) == shown['seen_version']
    applied = decide(client, proposal.pk, route, seen_version=shown['seen_version'], acknowledge_inactive=True,
                     **extra)
    assert applied.status_code == 200, applied.content
    target.refresh_from_db()
    assert getattr(target, field) == value and target.is_active is False


def test_a_note_on_an_inactive_contact_with_the_acknowledgement(agent, person, contact):
    proposal = create_proposal(agent, _note(contact, 'contact'), via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    assert decide(client, proposal.pk, 'accept', seen_version=seen).json()['code'] == 'needs_acknowledgement'
    assert decide(client, proposal.pk, 'accept', seen_version=seen, acknowledge_inactive=True).status_code == 200
    contact.refresh_from_db()
    assert contact.notes.endswith('Prefers calls in the afternoon') and contact.is_active is False


def test_a_contact_created_from_a_suggestion_can_be_corrected_while_inactive(agent, other_agent, person, company):
    client = jwt_client(person)
    new = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                  'patch': {'name': 'Dana Newcomer', 'email': 'dana@riverside.example.com'},
                                  'evidence_quote': 'please add dana@riverside.example.com'}, via='rest')[0]
    created_id = decide(client, new.pk, 'accept').json()['created_contact_id']
    created = Contact.objects.get(pk=created_id)
    assert created.is_active is False
    fix = create_proposal(other_agent, _field(created, 'contact', 'email', 'dana.n@riverside.example.com'),
                          via='rest')[0]
    assert fix.target_state == 'inactive'
    seen = client.get(f'{PROPOSALS}{fix.pk}/').json()['seen_version']
    assert decide(client, fix.pk, 'accept', seen_version=seen).json()['code'] == 'needs_acknowledgement'
    assert decide(client, fix.pk, 'accept', seen_version=seen, acknowledge_inactive=True).status_code == 200
    created.refresh_from_db()
    assert created.email == 'dana.n@riverside.example.com'
    assert created.is_active is False and created.is_primary is False
    assert not any(getattr(created, f.name) for f in Contact._meta.concrete_fields if f.name.startswith('receives_'))


def test_the_acknowledgement_must_be_true_or_false(agent, person, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    response = decide(jwt_client(person), proposal.pk, 'accept', acknowledge_inactive='yes')
    assert (response.status_code, response.json()['code']) == (400, 'invalid')


def test_the_acknowledgement_does_not_open_a_never_acceptable_state(agent, person, other_company, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(company=other_company, is_active=False)
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    response = decide(client, proposal.pk, 'accept', seen_version=seen, acknowledge_inactive=True)
    assert (response.status_code, response.json()['code']) == (409, 'not_acceptable')
    assert _row(proposal).last_apply_error == 'This contact now belongs to another company.'


def test_bulk_routes_never_acknowledge(agent, person, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    assert client.post(f'{PROPOSALS}bulk-accept/', {}, format='json').status_code in (404, 405)
    refused = client.post(f'{PROPOSALS}bulk-reject/', {'items': [{'id': str(proposal.pk), 'seen_version': seen}],
                                                       'reason': 'no', 'acknowledge_inactive': True}, format='json')
    assert refused.status_code == 400
    contact.refresh_from_db()
    assert contact.title == 'Manager'


# ------------------------------------------------------------------ refusals leave the watched state alone


def test_colliding_edits_on_a_new_contact_keep_the_state_the_reviewer_saw(agent, person, company, contact):
    proposal = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                       'patch': {'name': 'Lee Unique', 'email': 'lee@riverside.example.com'},
                                       'evidence_quote': 'please add lee@riverside.example.com'}, via='rest')[0]
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    response = decide(client, proposal.pk, 'accept-with-edits', seen_version=seen,
                      edits={'email': 'PAT@riverside.example.com'})
    assert (response.status_code, response.json()['code']) == (409, 'not_acceptable')
    assert 'edited contact already exists' in response.json()['detail']
    row = _row(proposal)
    assert (row.target_state, row.target_changed_at) == ('no_duplicate', None)
    assert row.last_apply_error.startswith('The edited contact already exists')
    after = client.get(f'{PROPOSALS}{proposal.pk}/').json()
    assert (after['target_state'], after['target_changed_at'], after['seen_version']) == ('no_duplicate', None, seen)
    assert decide(client, proposal.pk, 'accept', seen_version=seen).status_code == 200


def test_a_refusal_stores_its_reason_for_the_page(agent, person, other_company, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(company=other_company)
    client = jwt_client(person)
    seen = client.get(f'{PROPOSALS}{proposal.pk}/').json()['seen_version']
    decide(client, proposal.pk, 'accept', seen_version=seen)
    assert client.get(f'{PROPOSALS}{proposal.pk}/').json()['last_apply_error'] == \
        'This contact now belongs to another company.'


def test_a_missing_target_stores_missing_with_its_reason(agent, person, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    seen = seen_of(proposal.pk)
    Contact.objects.filter(pk=contact.pk).delete()
    response = decide(jwt_client(person), proposal.pk, 'accept', seen_version=seen)
    assert (response.status_code, response.json()['code']) == (409, 'target_missing')
    assert response.json()['target_state_reason'] == 'This record no longer exists.'
    row = _row(proposal)
    assert (row.status, row.target_state) == ('failed', 'missing')
    shown = jwt_client(person).get(f'{PROPOSALS}{proposal.pk}/').json()
    assert (shown['target_state'], shown['target_state_reason']) == ('missing', 'This record no longer exists.')


@pytest.mark.parametrize('when', ['read', 'accept'])
def test_a_state_change_keeps_a_notes_context(agent, person, contact, when):
    note = create_proposal(agent, _note(contact, 'contact'), via='rest')[0]
    assert note.current_values == {'notes': 'Prefers email'}
    seen = seen_of(note.pk)
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    if when == 'read':
        jwt_client(person).get(PROPOSALS)
    else:
        assert decide(jwt_client(person), note.pk, 'accept', seen_version=seen).json()['code'] == 'record_changed'
    row = _row(note)
    assert row.target_state == 'inactive' and row.current_values == {'notes': 'Prefers email'}


# ------------------------------------------------------------------ an agent's REST read changes nothing


def test_an_agents_rest_read_neither_advances_nor_flags(agent, person, company):
    proposal = create_proposal(agent, _field(company, 'company', 'phone', '+66 2 111 2222'), via='rest')[0]
    before = _row(proposal)
    company.refresh_from_db()
    company.phone = '+66 2 999 9999'
    company.save()
    with CaptureQueriesContext(connection) as queries:
        listed = token_client(agent).get(PROPOSALS).json()['results'][0]
        token_client(agent).get(f'{PROPOSALS}{proposal.pk}/')
    assert not [q for q in queries.captured_queries
                if q['sql'].lstrip().upper().startswith('UPDATE') and 'agent_inbox_changeproposal' in q['sql']]
    after = _row(proposal)
    assert (after.expected_version, after.target_changed_at, after.current_values) == (
        before.expected_version, None, before.current_values)
    assert listed['target_state'] == 'present'
    # A person's read then does the comparison and flags it.
    jwt_client(person).get(PROPOSALS)
    assert _row(proposal).target_changed_at is not None


# ------------------------------------------------------------------ look-alike: Google's own country domains


@pytest.mark.parametrize('url', ['https://docs.google.co.th/x', 'https://www.google.com.hk/x',
                                 'https://www.google.com.vn/x', 'https://www.google.com/x'])
def test_googles_own_domains_for_our_markets_carry_no_warning(url):
    assert url_warnings('source_url', url, 'other') == []


@pytest.mark.parametrize('url', ['https://google.com.de/x', 'https://google.com.se/x', 'https://google.co.no/x',
                                 'https://google.shop/x', 'https://google.zz/x', 'https://www.google.de/x'])
def test_other_google_named_domains_warn(url):
    assert [w['code'] for w in url_warnings('source_url', url, 'other')] == ['url_lookalike_host']


def test_seen_version_is_unchanged_by_a_needs_acknowledgement_refusal(agent, person, contact):
    proposal = create_proposal(agent, _field(contact, 'contact', 'title', 'Director'), via='rest')[0]
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    jwt_client(person).get(PROPOSALS)
    digest = seen_version(_row(proposal))
    decide(jwt_client(person), proposal.pk, 'accept', seen_version=digest)
    assert seen_version(_row(proposal)) == digest


def test_a_duplicate_new_contact_is_refused_with_the_duplicate_reason(agent, person, company, contact):
    proposal = create_proposal(agent, {'kind': 'new_contact', 'company_id': str(company.pk),
                                       'patch': {'name': 'Pat Example', 'email': 'pat.second@riverside.example.com'},
                                       'evidence_quote': 'please add pat.second@riverside.example.com'},
                               via='rest')[0]
    assert proposal.target_state == 'duplicate'
    response = decide(jwt_client(person), proposal.pk, 'accept', acknowledge_inactive=True)
    assert (response.status_code, response.json()['code']) == (409, 'not_acceptable')
    assert response.json()['detail'] == 'A contact with this email or name already exists at the company.'
