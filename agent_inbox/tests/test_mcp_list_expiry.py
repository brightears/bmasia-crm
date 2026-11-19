"""The MCP list_proposals tool shows and filters by the effective status, as the REST list does."""
import json
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from agent_inbox.models import ChangeProposal
from agent_inbox.proposals import create_proposal

# Function tools run in the MCP transport's own thread and database connection.
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.usefixtures('inbox_mcp')]


def _list(user, **arguments):
    token, _ = Token.objects.get_or_create(user=user)
    response = APIClient().post(
        '/mcp/', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': 'list_proposals', 'arguments': arguments}},
        format='json', HTTP_ACCEPT='application/json, text/event-stream', HTTP_AUTHORIZATION=f'Token {token.key}',
    )
    assert response.status_code == 200, response.content
    result = response.json()['result']
    assert result['isError'] is False, result
    return json.loads(result['content'][0]['text'])


def test_a_due_proposal_is_listed_and_filtered_as_expired(agent, company):
    due, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'phone': '+66 2 111 2222'}, 'evidence_quote': 'new number'}, via='mcp')
    fresh, _ = create_proposal(agent, {
        'kind': 'field_update', 'target_collection': 'company', 'target_id': str(company.pk),
        'patch': {'email': 'desk@riverside.example.com'}, 'evidence_quote': 'new address'}, via='mcp')
    ChangeProposal.objects.filter(pk=due.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

    shown = {row['id']: row['status'] for row in _list(agent)['proposals']}
    assert shown == {str(due.pk): 'expired', str(fresh.pk): 'proposed'}
    assert [row['id'] for row in _list(agent, status='expired')['proposals']] == [str(due.pk)]
    assert [row['id'] for row in _list(agent, status='proposed')['proposals']] == [str(fresh.pk)]
    due.refresh_from_db()
    assert due.status == 'proposed'  # listing writes nothing
