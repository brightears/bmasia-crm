"""query_data_collections publishes contract-document METADATA: never the file, never a write.

Agents need to know whether a contract has a signed copy. The REST endpoint
/contract-documents/ already serves this to any token; the query tool now offers the same
metadata as the read-only `contractdocument` collection. Invented data only.
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from crm_app.agent_policy import CREATE, DELETE, PRINCIPALS, UPDATE, evaluate
from crm_app.mcp_query_help import boundary_for, published_collections
from crm_app.models import Company, Contract, ContractDocument

pytestmark = pytest.mark.django_db

PUBLISHED = ['id', 'contract', 'document_type', 'title', 'is_official', 'is_signed', 'signed_date', 'uploaded_at']
NEVER = ['file', 'uploaded_by', 'notes']


def _token(username, role='Admin'):
    user = get_user_model().objects.create_user(
        username=username, email=f'{username}@example.test', password='placeholder-not-a-secret', role=role)
    key = (username + '0' * 40)[:40]
    Token.objects.create(user=user, key=key)
    return key


@pytest.fixture
def data():
    company = Company.objects.create(name='Documents Hotel', billing_entity='BMAsia Limited')
    first = Contract.objects.create(company=company, contract_number='HK-CT0101', status='Active',
                                    start_date=date(2026, 1, 1), value=Decimal('1.00'))
    second = Contract.objects.create(company=company, contract_number='HK-CT0102', status='Draft',
                                     start_date=date(2026, 2, 1), value=Decimal('1.00'))
    signed = ContractDocument.objects.create(
        contract=first, document_type='principal_terms', title='Signed agreement', is_official=True,
        is_signed=True, signed_date=date(2026, 1, 5), file='contract_documents/2026/01/secret-path-signed.pdf',
        notes='internal note')
    draft = ContractDocument.objects.create(
        contract=first, document_type='generated', title='Generated draft',
        file='contract_documents/2026/01/secret-path-draft.pdf')
    other = ContractDocument.objects.create(
        contract=second, document_type='other', title='Other contract file',
        file='contract_documents/2026/02/secret-path-other.pdf')
    return {'first': first, 'second': second, 'signed': signed, 'draft': draft, 'other': other}


def call(key, name, arguments):
    response = APIClient().post('/mcp/', {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                                          'params': {'name': name, 'arguments': arguments}},
                                format='json', HTTP_ACCEPT='application/json, text/event-stream',
                                HTTP_AUTHORIZATION=f'Token {key}')
    assert response.status_code == 200
    return response.json()['result']


def query(key, pipeline, collection='contractdocument'):
    result = call(key, 'query_data_collections', {'collection': collection, 'search_pipeline': pipeline})
    text = result['content'][0]['text'] if result['content'] else '[]'
    return result['isError'], (text if result['isError'] else json.loads(text))


def test_the_collection_publishes_metadata_only():
    fields = boundary_for(published_collections()).fields['contractdocument']
    assert fields == PUBLISHED
    assert not set(NEVER) & set(fields)


def test_reads_return_only_published_fields_and_never_the_file(data):
    key = _token('theo', role='Sales')
    error, rows = query(key, [])
    assert not error and len(rows) == 3
    for row in rows:
        assert set(row) == {'id', 'contract_id', 'document_type', 'title', 'is_official', 'is_signed',
                            'signed_date', 'uploaded_at'}
    assert 'secret-path' not in json.dumps(rows) and 'internal note' not in json.dumps(rows)


@pytest.mark.parametrize('name', NEVER)
@pytest.mark.parametrize('stage', ['project', 'match', 'sort', 'group'])
def test_unpublished_fields_cannot_be_read_filtered_sorted_or_grouped(data, name, stage):
    key = _token('vera')
    pipeline = {
        'project': [{'$project': {name: 1}}],
        'match': [{'$match': {f'{name}__icontains': 'secret'}}],
        'sort': [{'$sort': {name: 1}}],
        'group': [{'$group': {'_id': f'${name}', 'n': {'$sum': 1}}}],
    }[stage]
    error, text = query(key, pipeline)
    assert error and f"Unknown field '{name}' on collection 'contractdocument'" in text
    assert 'secret-path' not in text


def test_filter_by_contract_and_through_the_contract(data):
    key = _token('lyra')
    error, rows = query(key, [{'$match': {'contract': str(data['first'].pk)}},
                              {'$project': {'title': 1, 'is_signed': 1}}])
    assert not error
    assert sorted(rows, key=lambda r: r['title']) == [
        {'title': 'Generated draft', 'is_signed': False}, {'title': 'Signed agreement', 'is_signed': True}]
    error, rows = query(key, [{'$match': {'contract__contract_number': 'HK-CT0101', 'is_signed': True}},
                              {'$project': {'title': 1, 'signed_date': 1}}])
    assert not error and rows == [{'title': 'Signed agreement', 'signed_date': '2026-01-05'}]


def test_a_retired_principal_reads_nothing(data):
    assert PRINCIPALS['ruby'].retired
    error, rows = query(_token('ruby'), [])
    assert not error and rows == []
    error, rows = query(_token('cira'), [])
    assert not error and len(rows) == 3


@pytest.mark.parametrize('username', sorted(PRINCIPALS) + ['a-person'])
def test_no_tool_writes_contract_documents(data, username):
    key = _token(username)
    before = list(ContractDocument.objects.order_by('pk').values())
    pk = str(data['draft'].pk)
    for name, arguments in [
        ('create_record', {'collection': 'contractdocument',
                           'data': json.dumps({'contract': str(data['first'].pk), 'title': 'x',
                                               'document_type': 'other'})}),
        ('update_record', {'collection': 'contractdocument', 'id': pk, 'data': json.dumps({'is_signed': True})}),
        ('delete_record', {'collection': 'contractdocument', 'id': pk}),
    ]:
        result = call(key, name, arguments)
        assert "Unknown collection 'contractdocument'" in result['content'][0]['text'], (username, name)
    assert list(ContractDocument.objects.order_by('pk').values()) == before


@pytest.mark.parametrize('username', sorted(PRINCIPALS))
def test_the_agent_gate_denies_every_write_for_every_principal(username):
    for verb in (CREATE, UPDATE, DELETE):
        reasons, _ = evaluate(PRINCIPALS[username], verb, 'contractdocument', ['is_signed'])
        assert reasons, (username, verb)


DOCUMENTS_HINT = "Contract documents are a separate collection: query contractdocument with contract = the contract's id"


@pytest.mark.parametrize('name', ['contract_documents', 'documents'])
def test_asking_for_documents_on_contract_points_to_the_collection(data, name):
    error, text = query(_token('theo'), [{'$project': {name: 1}}], collection='contract')
    assert error and f"Unknown field '{name}' on collection 'contract'. Hint: {DOCUMENTS_HINT}." in text


@pytest.mark.parametrize('name', ['contract_documents', 'contractdocuments', 'documents', 'document',
                                  'ContractDocuments'])
def test_asking_for_a_documents_collection_suggests_contractdocument(data, name):
    error, text = query(_token('theo'), [], collection=name)
    assert error and f"Unknown collection '{name}'. Did you mean 'contractdocument'?" in text


def test_the_query_tool_lists_the_collection_and_its_instructions():
    from mcp_server.djangomcp import global_mcp_server as server

    description = server._tool_manager.get_tool('query_data_collections').description
    assert "### 'contractdocument' collection" in description
    assert 'never the file' in description
    section = description.split("### 'contractdocument' collection", 1)[1].split('###', 1)[0]
    for name in NEVER:
        assert f'"{name}"' not in section


def test_the_document_alias_wins_over_a_closer_spelling():
    """The alias, not a lucky close match, sends 'document(s)' to contractdocument."""
    from crm_app.mcp_query_help import COLLECTION_ALIASES, suggest_collection

    assert COLLECTION_ALIASES['document'] == 'contractdocument'
    for name in ('document', 'documents', 'Documents'):
        assert suggest_collection(name, ['documentz', 'contractdocument']) == 'contractdocument', name
