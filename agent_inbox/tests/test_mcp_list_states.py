"""The MCP list_proposals tool shows an agent the stored target state and reason, and writes nothing."""
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal
from crm_app.models import Contact

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures('inbox_mcp')]


def _list(user):
    token, _ = Token.objects.get_or_create(user=user)
    response = APIClient().post(
        '/mcp/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': 'list_proposals', 'arguments': {}}},
        format='json', HTTP_ACCEPT='application/json, text/event-stream', HTTP_AUTHORIZATION=f'Token {token.key}',
    )
    assert response.status_code == 200, response.content
    result = response.json()['result']
    assert result['isError'] is False, result
    return json.loads(result['content'][0]['text'])


def test_an_agent_sees_the_stored_state_and_reason_without_any_write(agent, contact):
    proposal = create_proposal(agent, {'kind': 'field_update', 'target_collection': 'contact',
                                       'target_id': str(contact.pk), 'patch': {'title': 'Director'},
                                       'evidence_quote': 'Director'}, via='mcp')[0]
    item = _list(agent)['proposals'][0]
    assert (item['target_state'], item['target_state_reason']) == ('present', '')
    # Made inactive: the agent's read shows what was stored last, and stores nothing itself.
    Contact.objects.filter(pk=contact.pk).update(is_active=False)
    with CaptureQueriesContext(connection) as queries:
        item = _list(agent)['proposals'][0]
    assert item['target_state'] == 'present'
    assert not [q for q in queries.captured_queries
                if q['sql'].lstrip().upper().startswith('UPDATE') and 'agent_inbox_changeproposal' in q['sql']]
    # Once stored (here as a reviewer's read would), the agent sees it with its reason.
    ChangeProposal.objects.filter(pk=proposal.pk).update(target_state='inactive')
    item = _list(agent)['proposals'][0]
    assert item['target_state'] == 'inactive'
    assert item['target_state_reason'].startswith('This contact is inactive')
