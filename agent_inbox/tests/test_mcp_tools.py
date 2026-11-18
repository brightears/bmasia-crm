"""MCP tools end to end over /mcp/, and the query boundary for the two new collections."""
import json

import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from agent_inbox.models import Activity, ChangeProposal
from agent_inbox.tests.conftest import PROPOSALS, iso_ago, session_client
from crm_app.mcp_query_help import boundary_for, published_collections, unknown_field_message
from crm_app.models import AgentRequest

# Function tools run in the MCP transport's own thread and database connection,
# so these tests commit their fixtures instead of wrapping them in a transaction.
pytestmark = pytest.mark.django_db(transaction=True)

BODY = 'Hi team,\nplease note our new reception number is +66 2 111 2222.\nThanks, Pat'


def call(user, name, arguments):
    token, _ = Token.objects.get_or_create(user=user)
    response = APIClient().post(
        '/mcp/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}},
        format='json', HTTP_ACCEPT='application/json, text/event-stream', HTTP_AUTHORIZATION=f'Token {token.key}',
    )
    assert response.status_code == 200, response.content
    result = response.json()['result']
    return result


def tool(user, name, arguments):
    result = call(user, name, arguments)
    assert result['isError'] is False, result
    return json.loads(result['content'][0]['text'])


def log_args(company, **overrides):
    args = {
        'company_id': str(company.pk), 'kind': 'email', 'direction': 'inbound', 'occurred_at': iso_ago(hours=1),
        'summary': 'New reception number', 'idempotency_key': 'gmail:msg-0001', 'source_system': 'gmail',
        'body': BODY, 'source_ref': 'msg-0001',
        'participants_json': json.dumps([{'name': 'Pat Example', 'address': 'pat@riverside.example.com',
                                          'role': 'from'}]),
    }
    args.update(overrides)
    return args


def test_tools_are_listed_with_descriptions(agent):
    token, _ = Token.objects.get_or_create(user=agent)
    response = APIClient().post('/mcp/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}},
                                format='json', HTTP_ACCEPT='application/json, text/event-stream',
                                HTTP_AUTHORIZATION=f'Token {token.key}')
    tools = {item['name']: item for item in response.json()['result']['tools']}
    assert {'log_activity', 'propose_change', 'list_proposals'} <= set(tools)
    assert 'Never applied automatically' in tools['propose_change']['description']
    assert 'verbatim' in tools['propose_change']['description']
    assert 'idempotency_key' in tools['log_activity']['description']


def test_log_activity_is_idempotent_and_observed(agent, company):
    args = log_args(company)
    first = tool(agent, 'log_activity', args)
    assert first['ok'] is True and first['replayed'] is False
    again = tool(agent, 'log_activity', args)
    assert again['replayed'] is True and again['id'] == first['id']
    conflict = tool(agent, 'log_activity', {**args, 'summary': 'Changed'})
    assert (conflict['ok'], conflict['status'], conflict['code']) == (False, 409, 'idempotency_conflict')
    row = Activity.objects.get()
    assert (row.recorded_by, row.recorded_via) == (agent, 'mcp')
    assert row.participants[0]['role'] == 'from'
    observed = AgentRequest.objects.filter(tool='log_activity')
    assert observed.count() == 3
    assert {r.principal for r in observed} == {'theo'}


def test_log_activity_refuses_bad_input_and_switch_off(agent, company):
    bad = tool(agent, 'log_activity', log_args(company, participants_json='not json'))
    assert (bad['ok'], bad['status']) == (False, 400)
    with override_settings(AGENT_ACTIVITY_WRITES_ENABLED=False):
        off = tool(agent, 'log_activity', log_args(company))
    assert (off['ok'], off['code']) == (False, 'not_enabled')
    assert Activity.objects.count() == 0


def test_propose_review_and_learn_the_outcome(agent, person, company):
    activity = tool(agent, 'log_activity', log_args(company))
    proposed = tool(agent, 'propose_change', {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'phone': '+66 2 111 2222'}),
        'evidence_quote': 'our new reception number is +66 2 111 2222', 'activity_id': activity['id'],
        'rationale': 'Customer email', 'confidence': 0.9, 'batch_key': 'gmail:msg-0001',
    })
    assert proposed['ok'] is True and proposed['status'] == 'proposed' and proposed['evidence_verified'] is True
    assert 'Nothing has been changed' in proposed['note']
    company.refresh_from_db()
    assert company.phone == '+66 2 000 0000'
    retry = tool(agent, 'propose_change', {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'phone': '+66 2 111 2222'}),
        'evidence_quote': 'our new reception number is +66 2 111 2222', 'activity_id': activity['id'],
    })
    assert retry['replayed'] is True and retry['id'] == proposed['id']

    listed = tool(agent, 'list_proposals', {})
    assert listed['count'] == 1 and listed['proposals'][0]['status'] == 'proposed'
    assert listed['proposals'][0]['confidence'] == 0.9

    response = session_client(person).post(f"{PROPOSALS}{proposed['id']}/reject/",
                                           {'reason': 'That number belongs to the spa'}, format='json')
    assert response.status_code == 200
    outcome = tool(agent, 'list_proposals', {'status': 'rejected'})['proposals'][0]
    assert outcome['decision_note'] == 'That number belongs to the spa'
    assert outcome['reviewed_at']
    blocked = tool(agent, 'propose_change', {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'phone': '+66 2 111 2222'}), 'evidence_quote': 'new reception number',
    })
    assert (blocked['ok'], blocked['code']) == (False, 'previously_rejected')


def test_propose_change_refusals(agent, company, contract):
    not_verbatim = tool(agent, 'propose_change', {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'phone': '+66 2 111 2222'}),
        'evidence_quote': 'our phone changed', 'activity_id': tool(agent, 'log_activity', log_args(company))['id'],
    })
    assert not_verbatim['code'] == 'quote_not_verbatim'
    contract_change = tool(agent, 'propose_change', {
        'kind': 'field_update', 'target_collection': 'contract', 'target_id': str(contract.pk),
        'patch_json': json.dumps({'status': 'Cancelled'}), 'evidence_quote': 'we cancel',
    })
    assert contract_change['code'] == 'collection_not_allowed'
    no_quote = tool(agent, 'propose_change', {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'notes': 'Likes jazz'}),
    })
    assert no_quote['code'] == 'evidence_required'
    bad_json = tool(agent, 'propose_change', {'kind': 'note', 'patch_json': '{'})
    assert bad_json['status'] == 400
    with override_settings(CHANGE_PROPOSALS_ENABLED=False):
        off = tool(agent, 'propose_change', {
            'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
            'patch_json': json.dumps({'notes': 'Likes jazz'}), 'evidence_quote': 'jazz',
        })
    assert off['code'] == 'not_enabled'
    assert ChangeProposal.objects.count() == 0


def test_list_proposals_shows_only_the_callers_own(agent, other_agent, company, contact):
    tool(agent, 'propose_change', {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'notes': 'Likes jazz'}), 'evidence_quote': 'jazz',
    })
    assert tool(other_agent, 'list_proposals', {})['count'] == 0
    assert tool(agent, 'list_proposals', {'limit': 1})['count'] == 1
    assert tool(agent, 'list_proposals', {'status': 'nonsense'})['status'] == 400
    assert tool(agent, 'list_proposals', {'limit': 0})['status'] == 400


def test_unauthenticated_tool_call_is_refused(company):
    response = APIClient().post(
        '/mcp/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': 'list_proposals', 'arguments': {}}},
        format='json', HTTP_ACCEPT='application/json, text/event-stream',
    )
    assert response.status_code in (401, 403)


# ------------------------------------------------------------------ query boundary


def query(user, collection, pipeline):
    result = call(user, 'query_data_collections', {'collection': collection, 'search_pipeline': pipeline})
    return result


ACTIVITY_PUBLISHED = {
    'id', 'company', 'contact', 'contract', 'quote', 'opportunity', 'kind', 'direction', 'occurred_at',
    'summary', 'source_system', 'source_ref', 'recorded_by_username', 'recorded_via', 'is_void',
    'created_at', 'updated_at',
}
PROPOSAL_PUBLISHED = {
    'id', 'company', 'target_collection', 'target_id', 'kind', 'status', 'proposer_username',
    'proposer_kind', 'activity', 'evidence_verified', 'confidence', 'batch_key', 'reviewed_at',
    'expires_at', 'created_at', 'updated_at',
}


def test_published_fields_are_exactly_the_chosen_ones():
    boundary = boundary_for(published_collections())
    assert set(boundary.fields['activity']) == ACTIVITY_PUBLISHED
    assert set(boundary.fields['changeproposal']) == PROPOSAL_PUBLISHED


def test_query_returns_published_columns_only(agent, other_agent, company):
    tool(agent, 'log_activity', log_args(company))
    tool(agent, 'propose_change', {
        'kind': 'note', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch_json': json.dumps({'notes': 'Likes jazz'}), 'evidence_quote': 'jazz',
    })
    rows = json.loads(query(other_agent, 'activity', [])['content'][0]['text'])
    assert len(rows) == 1
    assert set(rows[0]) == {f + '_id' if f in {'company', 'contact', 'contract', 'quote', 'opportunity'} else f
                            for f in ACTIVITY_PUBLISHED}
    assert 'body' not in rows[0] and BODY not in json.dumps(rows)
    proposals = json.loads(query(other_agent, 'changeproposal', [])['content'][0]['text'])
    assert len(proposals) == 1
    assert 'patch' not in proposals[0] and 'Likes jazz' not in json.dumps(proposals)
    assert proposals[0]['status'] == 'proposed'
    found = json.loads(query(other_agent, 'activity', [{'$match': {'summary': {'$icontains': 'reception'}}},
                                                        {'$project': {'summary': 1}}])['content'][0]['text'])
    assert found == [{'summary': 'New reception number'}]


@pytest.mark.parametrize('collection, pipeline, name', [
    ('activity', [{'$project': {'body': 1}}], 'body'),
    ('activity', [{'$match': {'body': {'$icontains': 'reception'}}}], 'body'),
    ('activity', [{'$project': {'participants': 1}}], 'participants'),
    ('activity', [{'$sort': {'idempotency_key': 1}}], 'idempotency_key'),
    ('activity', [{'$group': {'_id': '$source_url'}}], 'source_url'),
    ('activity', [{'$project': {'x': '$recorded_by__username'}}], 'recorded_by'),
    ('activity', [{'$match': {'voided_by_id': 1}}], 'voided_by_id'),
    ('activity', [{'$match': {'payload_sha256': 'x'}}], 'payload_sha256'),
    ('changeproposal', [{'$project': {'patch': 1}}], 'patch'),
    ('changeproposal', [{'$project': {'evidence_quote': 1}}], 'evidence_quote'),
    ('changeproposal', [{'$match': {'rationale': {'$icontains': 'x'}}}], 'rationale'),
    ('changeproposal', [{'$project': {'decision_note': 1}}], 'decision_note'),
    ('changeproposal', [{'$project': {'current_values': 1}}], 'current_values'),
    ('changeproposal', [{'$project': {'x': '$reviewer__password'}}], 'reviewer'),
    ('changeproposal', [{'$project': {'x': '$activity__body'}}], 'body'),
])
def test_unpublished_fields_are_refused(agent, collection, pipeline, name):
    result = query(agent, collection, pipeline)
    assert result['isError'] is True
    on = 'activity' if name == 'body' else collection
    expected = unknown_field_message(name, on, boundary_for(published_collections()).fields[on])
    assert result['content'][0]['text'] == 'Error executing tool query_data_collections: ' + expected


def test_describe_collection_lists_the_new_collections(agent):
    described = tool(agent, 'describe_collection', {'name': 'changeproposal'})
    assert {field['name'] for field in described['fields']} == PROPOSAL_PUBLISHED
    described = tool(agent, 'describe_collection', {'name': 'activity'})
    assert 'body' not in {field['name'] for field in described['fields']}
