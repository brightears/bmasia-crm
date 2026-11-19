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


def _warnings(records):
    return [r.getMessage() for r in records if r.name == 'crm_app.mcp_query_help']


def test_the_log_line_names_the_unknown_field_and_no_value(client, records):
    call(client, 'contract', [{'$match': {'number_of_zones': 'secret-looking-value'}}])
    (line,) = _warnings(records)
    assert line == ("query_data_collections refused a query: kind=unknown_field principal='mistakes-agent' "
                    "collection='contract' name='number_of_zones'")


def test_a_mistake_recognised_by_type_carries_the_type_and_the_site(client, records):
    from crm_app.mcp_query_help import _VALIDATION_SITES

    call(client, 'company', [{'$match': {'id': 'secret-looking-value'}}])
    (line,) = _warnings(records)
    assert 'secret-looking-value' not in line
    prefix = ("query_data_collections refused a query: kind=invalid_value principal='mistakes-agent' "
              "collection='company' error=ValidationError site=django.db.models.fields.to_python:")
    assert line.startswith(prefix) and line[len(prefix):].isdigit(), line
    for name, (collection, pipeline) in MISTAKES.items():
        records.clear()
        call(client, collection, pipeline)
        (line,) = _warnings(records)
        if ' error=' in line:
            site = line.split(' site=')[1].rsplit(':', 1)[0]
            assert tuple(site.rsplit('.', 1)) in _VALIDATION_SITES, (name, line)


INJECTIONS = [
    'zz\nTraceback (most recent call last):\n  File "forged.py", line 1',
    'zz\r\nTraceback (most recent call last):',
    *[f'zz{separator}Traceback (most recent call last):' for separator in
      ('\r', '\x0b', '\x0c', '\x1c', '\x1d', '\x1e', '\x85', ' ', ' ', '\x00', '\x1b[2K', '\x7f')],
    'zz‮Traceback (most recent call last):',
]


def _assert_one_safe_line(line):
    assert len(line.splitlines()) == 1 and not any(ch in line for ch in '\n\r\x0b\x0c\x1c\x1d\x1e\x85  ')
    assert not any(0 <= ord(ch) < 0x20 or ord(ch) == 0x7f or ch in '  ‮' for ch in line), line
    assert not line.startswith('Traceback')


@pytest.mark.parametrize('name', INJECTIONS)
def test_names_cannot_break_or_forge_log_lines(client, records, name):
    for collection, pipeline in [
        ('company', [{'$project': {name: 1}}]),
        ('company', [{'$match': {name: 1}}]),
        ('company', [{'$sort': {name: 1}}]),
        (name, []),
    ]:
        records.clear()
        call(client, collection, pipeline)
        (line,) = _warnings(records)
        _assert_one_safe_line(line)


def test_long_names_are_cut_with_a_marker(client, records):
    call(client, 'f' * 20000, [{'$project': {'g' * 20000: 1}}])
    (line,) = _warnings(records)
    assert line == ("query_data_collections refused a query: kind=unknown_collection principal='mistakes-agent' "
                    f"collection='{'f' * 80}'...(+19920 chars) name='{'f' * 80}'...(+19920 chars)")


def test_loggable_escapes_every_line_break_and_control_character():
    from crm_app.mcp_query_help import loggable

    every = ''.join(chr(c) for c in list(range(0x20)) + [0x7f, 0x85, 0x2028, 0x2029, 0x202e])
    shown = loggable('a' + every + 'b', limit=1000)
    assert shown.startswith("'a") and shown.endswith("b'")
    assert all(0x20 <= ord(ch) < 0x7f for ch in shown), shown
    assert loggable('x' * 81) == f"'{'x' * 80}'...(+1 chars)"
    assert loggable(['not', 'a', 'string']) == '"[\'not\', \'a\', \'string\']"'


# ------------------------------------------------------------------ faults stay loud


def _errors_with_traceback(records):
    return [r for r in records if r.levelno >= logging.ERROR and r.exc_info]


def test_an_invalid_regex_is_a_database_error_and_keeps_its_traceback(client, records):
    from django.db import DatabaseError

    response = call(client, 'company', [{'$match': {'name__regex': '('}}])
    assert response.json()['result']['isError'] is True
    errors = _errors_with_traceback(records)
    assert errors and isinstance(errors[0].exc_info[1], DatabaseError)
    assert not _warnings(records)


def test_a_nul_character_rejected_by_postgres_keeps_its_traceback(client, records):
    from django.db import connection

    if connection.vendor != 'postgresql':
        pytest.skip('only PostgreSQL refuses NUL characters')
    response = call(client, 'company', [{'$match': {'name': 'a\x00b'}}])
    assert response.json()['result']['isError'] is True
    assert _errors_with_traceback(records) and not _warnings(records)


def test_a_programming_error_from_the_database_keeps_its_traceback(client, records, monkeypatch):
    from django.db import ProgrammingError
    from django.db.backends import utils

    original = utils.CursorWrapper._execute

    def broken(self, sql, params, *args):
        if 'FROM "crm_app_company"' in sql:  # only the tool's own query; the token check still runs
            raise ProgrammingError('relation "crm_app_company" does not exist')
        return original(self, sql, params, *args)

    monkeypatch.setattr(utils.CursorWrapper, '_execute', broken)
    response = call(client, 'company', [])
    assert response.json()['result']['isError'] is True
    errors = _errors_with_traceback(records)
    assert errors and isinstance(errors[0].exc_info[1], ProgrammingError)
    assert not _warnings(records)


def test_a_type_error_in_the_renderer_keeps_its_traceback(client, records, monkeypatch):
    from mcp_server import query_tool
    from rest_framework import renderers

    class Broken(renderers.JSONRenderer):
        def render(self, data, *args, **kwargs):
            raise TypeError('Object of type Decimal is not JSON serializable')

    # Only the renderer the query tool uses for its result, not the one that answers HTTP.
    monkeypatch.setitem(query_tool._output_formats, 'json', Broken)
    response = call(client, 'company', [{'$project': {'name': 1}}])
    assert response.json()['result']['isError'] is True
    errors = _errors_with_traceback(records)
    assert errors and isinstance(errors[0].exc_info[1], TypeError)
    assert not _warnings(records)


def _raised_at(module, function, exc, inner=None):
    """An exception whose innermost frame is `function` in `module` (or in `inner`)."""
    namespace = {'__name__': module, 'exc': exc, 'inner': inner}
    exec(compile(f'def {function}():\n    if inner:\n        inner()\n    raise exc\n', f'<{module}>', 'exec'),
         namespace)
    try:
        namespace[function]()
    except BaseException as raised:  # noqa: BLE001 - returned for inspection
        return raised
    raise AssertionError('nothing raised')


def test_only_the_listed_types_at_the_listed_sites_are_caller_mistakes():
    from django.core.exceptions import ValidationError
    from django.db import DataError, DatabaseError, OperationalError, ProgrammingError

    from crm_app.mcp_query_help import caller_input_kind

    library = ('mcp_server.query_tool', 'apply_json_mango_query')
    for exc in (ValueError('x'), TypeError('x'), AttributeError('x'), KeyError('x'), ValidationError('x')):
        assert caller_input_kind(_raised_at(*library, exc)) == 'invalid_pipeline', exc
    # The type check: database errors and other types are faults even at a validation site.
    for exc in (OperationalError('statement timeout'), ProgrammingError('x'), DataError('x'),
                DatabaseError('x'), RuntimeError('x'), LookupError('x'), Exception('x')):
        assert caller_input_kind(_raised_at(*library, exc)) is None, exc
    # The innermost frame decides: raised in our code while the library is on the stack.
    def ours():
        raise TypeError('renderer bug')
    assert caller_input_kind(_raised_at(*library, None, inner=ours)) is None
    # Only the listed functions: QuerySet slicing, not any QuerySet method.
    assert caller_input_kind(_raised_at('django.db.models.query', '__getitem__', ValueError('x'))) == \
        'invalid_skip_or_limit'
    for module, function in [('django.db.models.query', 'filter'), ('django.db.models.query', '_fetch_all'),
                             ('mcp_server.query_tool', '_postprocess_projection'),
                             ('django.db.models.fields', 'get_db_prep_value'),
                             ('django.db.backends.utils', '_execute'), ('crm_app.mcp_query_help', 'validate')]:
        assert caller_input_kind(_raised_at(module, function, ValueError('x'))) is None, (module, function)


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
    ('contract', 'number_of_zones'): 'count contractservicelocation rows by contract (one per zone or custom '
                                     'item) or zone rows by company; company.contracted_zone_count is the '
                                     'contracted count',
    ('company', 'currency'): 'currency is set on each contract, quote and invoice; a company has billing_entity',
    ('company', 'primary_contact'): 'query contact with this company and is_primary true',
    ('contract', 'contract_documents'): "Contract documents are a separate collection: query contractdocument "
                                        "with contract = the contract's id",
    ('contract', 'documents'): "Contract documents are a separate collection: query contractdocument "
                               "with contract = the contract's id",
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
