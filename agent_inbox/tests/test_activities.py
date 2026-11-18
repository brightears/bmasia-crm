"""Activities over REST: idempotency, validation and caps, voiding, reading, switch off."""
import pytest
from django.test import override_settings

from agent_inbox.models import BODY_MAX, PARTICIPANTS_MAX, SUMMARY_MAX, Activity
from agent_inbox.tests.conftest import (
    ACTIVITIES, activity_body, iso_ago, session_client, token_client,
)


def post(client, body):
    return client.post(ACTIVITIES, body, format='json')


# ------------------------------------------------------------------ idempotency


def test_create_returns_201_and_stores_every_field(agent, company, contact, contract):
    response = post(token_client(agent), activity_body(
        company, contact_id=str(contact.pk), contract_id=str(contract.pk),
        source_url='https://mail.example.com/thread/1',
    ))
    assert response.status_code == 201, response.content
    data = response.json()
    assert data['replayed'] is False
    row = Activity.objects.get(pk=data['id'])
    assert (row.company, row.contact, row.contract) == (company, contact, contract)
    assert row.recorded_by == agent and row.recorded_by_username == 'theo'
    assert row.recorded_via == 'rest'
    assert row.kind == 'email' and row.direction == 'inbound'
    assert row.participants == [{'name': 'Pat Example', 'address': 'pat@riverside.example.com', 'role': 'from'}]
    assert len(row.payload_sha256) == 64


def test_same_key_same_payload_returns_the_stored_row(agent, company):
    client = token_client(agent)
    body = activity_body(company)
    first = post(client, body)
    second = post(client, body)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()['replayed'] is True
    assert second.json()['id'] == first.json()['id']
    assert Activity.objects.count() == 1


def test_same_key_different_payload_is_409(agent, company):
    client = token_client(agent)
    post(client, activity_body(company))
    response = post(client, activity_body(company, summary='Something else entirely'))
    assert response.status_code == 409
    assert response.json()['code'] == 'idempotency_conflict'
    assert 'different activity' in response.json()['detail']
    assert Activity.objects.count() == 1


def test_keys_are_namespaced_per_recorder(agent, other_agent, company):
    post(token_client(agent), activity_body(company, source_ref=''))
    response = post(token_client(other_agent), activity_body(company, source_ref='', summary='Other agent'))
    assert response.status_code == 201
    assert Activity.objects.count() == 2


def test_same_source_ref_on_the_same_company_is_409(agent, other_agent, company):
    post(token_client(agent), activity_body(company))
    response = post(token_client(other_agent), activity_body(company, idempotency_key='test:other-key-1'))
    assert response.status_code == 409
    assert response.json()['code'] == 'source_already_recorded'


def test_voided_source_ref_can_be_recorded_again(agent, company):
    client = token_client(agent)
    first = post(client, activity_body(company)).json()
    assert client.post(f"{ACTIVITIES}{first['id']}/void/", {'reason': 'Logged on the wrong company'},
                       format='json').status_code == 200
    again = post(client, activity_body(company, idempotency_key='test:activity-0002'))
    assert again.status_code == 201


# ------------------------------------------------------------------ validation and caps


@pytest.mark.parametrize('overrides, message', [
    ({'summary': 'x' * (SUMMARY_MAX + 1)}, 'summary must be at most'),
    ({'summary': 'two\nlines'}, 'single line'),
    ({'summary': ''}, 'Missing keys: summary'),
    ({'body': 'x' * (BODY_MAX + 1)}, 'body must be at most'),
    ({'body': 'bell\x07'}, 'control or invisible characters'),
    ({'kind': 'fax'}, 'kind must be one of'),
    ({'direction': 'sideways'}, 'direction must be one of'),
    ({'source_system': 'carrier-pigeon'}, 'source_system must be one of'),
    ({'occurred_at': '2026-11-18T10:00:00'}, 'timezone'),
    ({'occurred_at': iso_ago(days=-2)}, 'in the future'),
    ({'occurred_at': '1999-12-31T00:00:00+00:00'}, 'before 2000'),
    ({'idempotency_key': 'short'}, 'idempotency_key must be'),
    ({'idempotency_key': 'has space in it'}, 'idempotency_key must be'),
    ({'source_ref': 'with space', 'source_system': 'phone'}, 'whitespace'),
    ({'source_ref': '18c2a4f0b1d2e3f4'}, 'RFC 822 Message-ID'),
    ({'source_ref': 'x' * 501, 'source_system': 'phone'}, 'source_ref must be at most'),
    ({'source_url': 'javascript:alert(1)'}, 'http or https'),
    ({'source_url': 'https://example.com/' + 'x' * 500}, 'source_url must be at most'),
    ({'participants': 'pat@example.com'}, 'participants must be a list'),
    ({'participants': [{'name': 'A', 'phone': '1'}]}, 'only name, address and role'),
    ({'participants': [{'name': 'A', 'role': 'boss'}]}, 'role must be one of'),
    ({'participants': [{'role': 'to'}]}, 'needs a name or an address'),
    ({'participants': [{'name': 'x' * 201}]}, 'name must be at most'),
    ({'participants': [{'name': f'P{i}'} for i in range(PARTICIPANTS_MAX + 1)]}, 'at most'),
    ({'recorded_via': 'ui'}, 'Unknown keys: recorded_via'),
    ({'unexpected': 1}, 'Unknown keys: unexpected'),
    ({'company_id': 'not-a-uuid'}, 'company_id must be a UUID'),
])
def test_invalid_input_is_400(agent, company, overrides, message):
    response = post(token_client(agent), activity_body(company, **overrides))
    assert response.status_code == 400, response.content
    assert message in response.json()['detail']
    assert Activity.objects.count() == 0


def test_unknown_company_and_foreign_contact_are_422(agent, company, other_company):
    from crm_app.models import Contact
    stranger = Contact.objects.create(company=other_company, name='Sam Example', email='sam@hilltop.example.com')
    client = token_client(agent)
    missing = post(client, activity_body(company, company_id='00000000-0000-0000-0000-000000000001'))
    assert (missing.status_code, missing.json()['code']) == (422, 'unknown_record')
    foreign = post(client, activity_body(company, contact_id=str(stranger.pk)))
    assert (foreign.status_code, foreign.json()['code']) == (422, 'wrong_company')
    assert Activity.objects.count() == 0


def test_body_is_stored_as_plain_text(agent, company):
    text = '<script>alert(1)</script>\n<b>bold</b>'
    response = post(token_client(agent), activity_body(company, body=text))
    assert response.status_code == 201
    assert Activity.objects.get().body == text


def test_daily_cap_per_recorder(agent, company):
    client = token_client(agent)
    with override_settings(AGENT_ACTIVITY_DAILY_CAP=2):
        for index in range(2):
            assert post(client, activity_body(company, idempotency_key=f'test:cap-{index:04}',
                                              source_ref=f'cap-{index}@mail.example.com')).status_code == 201
        refused = post(client, activity_body(company, idempotency_key='test:cap-0009',
                                             source_ref='cap-9@mail.example.com'))
    assert refused.status_code == 429
    assert refused.json()['code'] == 'daily_cap'


# ------------------------------------------------------------------ void


def test_void_needs_reason_and_is_once(agent, company):
    client = token_client(agent)
    activity_id = post(client, activity_body(company)).json()['id']
    path = f'{ACTIVITIES}{activity_id}/void/'
    assert client.post(path, {}, format='json').status_code == 400
    voided = client.post(path, {'reason': 'Duplicate entry'}, format='json')
    assert voided.status_code == 200
    assert voided.json()['is_void'] is True
    row = Activity.objects.get(pk=activity_id)
    assert (row.void_reason, row.voided_by) == ('Duplicate entry', agent)
    again = client.post(path, {'reason': 'Again'}, format='json')
    assert (again.status_code, again.json()['code']) == (409, 'already_void')


def test_agent_cannot_void_another_recorders_activity_but_a_person_can(agent, other_agent, person, company):
    activity_id = post(token_client(agent), activity_body(company)).json()['id']
    path = f'{ACTIVITIES}{activity_id}/void/'
    refused = token_client(other_agent).post(path, {'reason': 'Not mine'}, format='json')
    assert refused.status_code == 403
    assert session_client(person).post(path, {'reason': 'Wrong customer'}, format='json').status_code == 200


def test_there_is_no_hard_delete_or_update(agent, company):
    client = token_client(agent)
    activity_id = post(client, activity_body(company)).json()['id']
    assert client.delete(f'{ACTIVITIES}{activity_id}/').status_code == 405
    assert client.patch(f'{ACTIVITIES}{activity_id}/', {'summary': 'x'}, format='json').status_code == 405
    assert Activity.objects.filter(pk=activity_id).exists()


# ------------------------------------------------------------------ reading


def test_list_filters_and_hides_void_by_default(agent, person, company, other_company, contact):
    client = token_client(agent)
    first = post(client, activity_body(company, contact_id=str(contact.pk))).json()
    post(client, activity_body(company, idempotency_key='test:activity-call', kind='call', source_ref='',
                               occurred_at=iso_ago(days=10)))
    post(client, activity_body(other_company, idempotency_key='test:activity-other', source_ref=''))
    reader = session_client(person)
    assert reader.get(ACTIVITIES).json()['count'] == 3
    assert reader.get(ACTIVITIES, {'company': str(company.pk)}).json()['count'] == 2
    assert reader.get(ACTIVITIES, {'contact': str(contact.pk)}).json()['count'] == 1
    assert reader.get(ACTIVITIES, {'kind': 'call'}).json()['count'] == 1
    assert reader.get(ACTIVITIES, {'occurred_after': iso_ago(days=5)}).json()['count'] == 2
    page = reader.get(ACTIVITIES, {'page_size': 1}).json()
    assert len(page['results']) == 1 and page['next']
    client.post(f"{ACTIVITIES}{first['id']}/void/", {'reason': 'test'}, format='json')
    assert reader.get(ACTIVITIES).json()['count'] == 2
    assert reader.get(ACTIVITIES, {'include_void': 'true'}).json()['count'] == 3


def test_agents_do_not_see_other_recorders_bodies(agent, other_agent, person, company):
    activity_id = post(token_client(agent), activity_body(company)).json()['id']
    own = token_client(agent).get(f'{ACTIVITIES}{activity_id}/').json()
    other = token_client(other_agent).get(f'{ACTIVITIES}{activity_id}/').json()
    human = session_client(person).get(f'{ACTIVITIES}{activity_id}/').json()
    assert 'body' in own and 'participants' in own
    assert 'body' not in other and 'participants' not in other and 'idempotency_key' not in other
    assert other['summary'] == own['summary']
    assert human['body'] == own['body']


def test_anonymous_callers_are_refused():
    from rest_framework.test import APIClient
    assert APIClient().get(ACTIVITIES).status_code == 401


# ------------------------------------------------------------------ switch


def test_switch_off_refuses_writes_and_reads_still_work(agent, person, company):
    with override_settings(AGENT_ACTIVITY_WRITES_ENABLED=False):
        response = post(token_client(agent), activity_body(company))
        listing = session_client(person).get(ACTIVITIES)
    assert response.status_code == 403
    assert response.json()['code'] == 'not_enabled'
    assert 'not enabled' in response.json()['detail']
    assert listing.status_code == 200 and listing.json()['count'] == 0
    assert Activity.objects.count() == 0


def test_switch_must_be_a_real_true(agent, company):
    with override_settings(AGENT_ACTIVITY_WRITES_ENABLED='true'):
        assert post(token_client(agent), activity_body(company)).status_code == 403
