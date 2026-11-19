"""A caller's mistake in query_data_collections is answered as before and logged as one line.

django-mcp-server logs every exception a toolset tool raises with a full traceback at
ERROR ("Error in tool invocation"), so an agent asking for an unpublished field left a
traceback in the server log although nothing was wrong with the server. The boundary
wrapper (crm_app/mcp_query_help.py) now answers a caller mistake itself, with exactly the
reply the MCP SDK builds from the exception, and logs one WARNING line (principal,
collection, kind, the unknown name), without traceback or payload. A genuine fault still
reaches the library and is logged with its traceback.

The expected replies in golden/mcp_caller_mistakes.json were produced by the code before
this change (main 78349d1) with the dataset below. Regenerate them only from the code
before an intended change to these texts (REGENERATE_MCP_MISTAKE_GOLDENS=1, in a second
worktree of that code; never with git stash).
"""
import json
import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from crm_app.models import Company, Contract

pytestmark = pytest.mark.django_db

GOLDEN = Path(__file__).parent / 'golden' / 'mcp_caller_mistakes.json'
KEY = 'mistakeskey' + '0' * 29  # 40 characters, not a real credential

# name -> (collection, search_pipeline). Every kind of caller mistake the tool can meet.
MISTAKES = {
    'unknown_field_in_project': ('contract', [{'$project': {'zone_total': 1}}]),
    'unknown_field_with_alias': ('company', [{'$match': {'legal_name': 'x'}}]),
    'unknown_field_in_sort': ('quote', [{'$sort': {'sent_on': 1}}]),
    'unknown_field_in_sort_desc': ('contact', [{'$sort': {'-first_name': 1}}]),
    'unknown_field_in_group': ('contract', [{'$group': {'_id': '$quote_ref', 'n': {'$sum': 1}}}]),
    'unknown_field_in_path': ('contract', [{'$match': {'company__nonexistent': 1}}]),
    'unpublished_relation': ('task', [{'$project': {'assigned_to': 1}}]),
    'unsupported_lookup': ('company', [{'$match': {'name__nolookup': 'x'}}]),
    'unknown_collection_close': ('contracts', []),
    'unknown_collection_far': ('xyzzy', []),
    'unknown_operator': ('company', [{'$match': {'name': {'$foo': 1}}}]),
    'unsupported_stage': ('company', [{'$unwind': '$name'}]),
    'unknown_lookup_alias': ('contract', [{'$match': {'nope.name': 'x'}}]),
    'unknown_accumulator': ('contract', [{'$group': {'_id': '$status', 'n': {'$median': '$value'}}}]),
    'search_path_not_allowed': ('company', [{'$search': {'text': {'query': 'x', 'path': 'it_notes'}}}]),
    'match_not_an_object': ('company', [{'$match': 'name'}]),
    'project_not_an_object': ('company', [{'$project': 'name'}]),
    'sort_not_an_object': ('company', [{'$sort': 'name'}]),
    'limit_not_a_number': ('company', [{'$limit': 'ten'}]),
    'limit_negative': ('company', [{'$limit': -1}]),
    'skip_not_a_number': ('company', [{'$skip': 'x'}, {'$limit': 1}]),
    'skip_negative': ('company', [{'$skip': -2}]),
    'value_not_a_uuid': ('company', [{'$match': {'id': 'abc'}}]),
    'value_not_a_number': ('company', [{'$match': {'contracted_zone_count': 'many'}}]),
    'value_not_a_date': ('contract', [{'$match': {'start_date': 'yesterday'}}]),
    'value_not_a_decimal': ('contract', [{'$match': {'value': 'lots'}}]),
    'value_not_a_boolean': ('company', [{'$match': {'is_active': 'maybe'}}]),
    'in_without_a_list': ('company', [{'$match': {'name': {'$in': 5}}}]),
}


@pytest.fixture
def client():
    user = get_user_model().objects.create_user(
        username='mistakes-agent', email='mistakes@example.test', password='placeholder-not-a-secret', role='Admin')
    Token.objects.create(user=user, key=KEY)
    company = Company.objects.create(name='Mistakes Hotel', billing_entity='BMAsia Limited')
    Contract.objects.create(company=company, contract_number='HK-CT0001', status='Active',
                            start_date=date(2026, 1, 1), value=Decimal('1.00'))
    return APIClient()


def call(client, collection, pipeline):
    return client.post('/mcp/', {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                                 'params': {'name': 'query_data_collections',
                                            'arguments': {'collection': collection, 'search_pipeline': pipeline}}},
                       format='json', HTTP_ACCEPT='application/json, text/event-stream',
                       HTTP_AUTHORIZATION=f'Token {KEY}')


class Records(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def records():
    handler = Records()
    root = logging.getLogger()
    level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    yield handler.records
    root.removeHandler(handler)
    root.setLevel(level)


def test_caller_mistakes_get_the_same_reply_and_one_warning_line(client, records):
    replies, logged = {}, {}
    for name, (collection, pipeline) in MISTAKES.items():
        records.clear()
        response = call(client, collection, pipeline)
        assert response.status_code == 200, name
        replies[name] = response.content.decode('utf-8')
        logged[name] = list(records)
    if os.environ.get('REGENERATE_MCP_MISTAKE_GOLDENS') == '1':
        GOLDEN.write_text(json.dumps(replies, indent=1, sort_keys=True, ensure_ascii=False) + '\n',
                          encoding='utf-8')
        pytest.skip('replies regenerated; review the diff')
    for name, (collection, _) in MISTAKES.items():
        assert not [r for r in logged[name] if r.exc_info or r.levelno >= logging.ERROR], name
        warnings = [r for r in logged[name] if r.name == 'crm_app.mcp_query_help']
        assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING, name
        line = warnings[0].getMessage()
        assert '\n' not in line and 'mistakes-agent' in line and repr(collection) in line, name
    expected = json.loads(GOLDEN.read_text(encoding='utf-8'))
    for name, body in replies.items():
        assert json.loads(body) == json.loads(expected[name]), name
        assert body == expected[name], name
        assert json.loads(body)['result']['isError'] is True, name


def test_the_log_line_names_the_unknown_field_and_no_value(client, records):
    call(client, 'contract', [{'$match': {'number_of_zones': 'secret-looking-value'}}])
    (line,) = [r.getMessage() for r in records if r.name == 'crm_app.mcp_query_help']
    assert line == ("query_data_collections refused a query: unknown_field by mistakes-agent "
                    "on collection 'contract' (number_of_zones)")
    call(client, 'company', [{'$match': {'id': 'secret-looking-value'}}])
    line = [r.getMessage() for r in records if r.name == 'crm_app.mcp_query_help'][-1]
    assert 'secret-looking-value' not in line and line.endswith('(ValidationError)')


def test_a_fault_inside_the_tool_still_logs_its_traceback(client, records, monkeypatch):
    from mcp_server import query_tool

    def broken(*args, **kwargs):
        raise RuntimeError('database went away')

    monkeypatch.setattr(query_tool, 'apply_json_mango_query', broken)
    response = call(client, 'company', [])
    assert response.json()['result'] == {
        'content': [{'type': 'text', 'text': 'Error executing tool query_data_collections: database went away'}],
        'isError': True}
    errors = [r for r in records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info and isinstance(errors[0].exc_info[1], RuntimeError)
    assert not [r for r in records if r.name == 'crm_app.mcp_query_help']


def test_a_value_error_from_our_own_code_is_still_a_fault(client, records, monkeypatch):
    from crm_app import mcp_query_help

    def broken(self, collection, pipeline):
        raise ValueError('a bug, not a caller mistake')

    monkeypatch.setattr(mcp_query_help.Boundary, 'restrict_output', broken)
    response = call(client, 'company', [])
    assert response.json()['result']['content'][0]['text'] == (
        'Error executing tool query_data_collections: a bug, not a caller mistake')
    errors = [r for r in records if r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info


def test_in_process_callers_still_get_the_exception():
    from mcp_server.query_tool import _QueryExecutor

    from crm_app.mcp_query_help import QueryInputError, published_collections

    with pytest.raises(QueryInputError) as caught:
        _QueryExecutor(published_collections(), context=None, request=None).query(
            'contract', [{'$project': {'zone_total': 1}}])
    assert isinstance(caught.value, ValueError)
    assert str(caught.value).startswith("Unknown field 'zone_total' on collection 'contract'.")


# Hints added with this change for names agents asked for (production logs, 18-19 Nov).
NEW_HINTS = {
    ('contract', 'number_of_zones'): 'count contractservicelocation rows by contract (one per zone) or zone rows '
                                     'by company; company.contracted_zone_count is the contracted count',
    ('company', 'currency'): 'currency is set on each contract, quote and invoice; a company has billing_entity',
    ('company', 'primary_contact'): 'query contact with this company and is_primary true',
    ('contract', 'contract_documents'): 'no stored PDF link; call generate_contract_pdf / generate_quote_pdf / '
                                        'generate_invoice_pdf',
    ('contract', 'quote'): "a contract's source quote is not published; query quote by company",
    ('contract', 'source_quote'): "a contract's source quote is not published; query quote by company",
    ('quote', 'sent_date'): 'quote send dates are not published; status shows whether it was sent',
    ('invoice', 'payment_method'): 'payment method is not published; use status and paid_date on invoice',
}


@pytest.mark.parametrize('collection, name', sorted(NEW_HINTS))
def test_new_hints_for_names_agents_ask_for(client, collection, name):
    from crm_app.mcp_query_help import boundary_for, published_collections

    text = call(client, collection, [{'$project': {name: 1}}]).json()['result']['content'][0]['text']
    published = ', '.join(boundary_for(published_collections()).fields[collection])
    assert text == (f"Error executing tool query_data_collections: Unknown field '{name}' on collection "
                    f"'{collection}'. Hint: {NEW_HINTS[(collection, name)]}. Published fields: {published}")
