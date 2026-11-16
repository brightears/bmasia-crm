"""query_data_collections stays inside the published fields of published collections.

Synthetic data only. Every refused path must give the same one-line
"Unknown field ..." error whether or not the name exists on the model.
"""
import json
import logging
from datetime import date
from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from mcp.server.fastmcp.exceptions import ToolError
from mcp_server import mcp_server, query_tool
from mcp_server.query_tool import _QueryExecutor
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from crm_app import mcp as crm_mcp
from crm_app import mcp_query_help as help_
from crm_app.mcp_query_help import (
    QUERY_UNAVAILABLE_MESSAGE, boundary_active, boundary_for, is_protected_model, never_publish_reason,
    published_collections, unknown_field_message,
)
from crm_app.models import Company, Contact, Contract, EmailLog, KBArticle, Opportunity, Quote, Task, Ticket

PLACEHOLDER_KEY = 'placeholderkey' + '0' * 26  # 40 characters, not a real credential


def _crm_toolsets():
    return [cls for cls in published_collections().values() if cls.__module__ == crm_mcp.__name__]


def _boundary():
    return boundary_for(published_collections())


def _executor():
    return _QueryExecutor(published_collections(), context=None, request=None)


def run(collection, pipeline):
    result = _executor().query(collection, json.loads(json.dumps(pipeline)))
    return json.loads(result[0].text) if result else []


def refused(collection, pipeline):
    with pytest.raises(ValueError) as caught:
        run(collection, pipeline)
    return str(caught.value)


@pytest.fixture
def data():
    user = get_user_model().objects.create_user(
        username='boundary-user', email='boundary-user@example.test', password='placeholder-not-a-secret',
        role='Admin', smtp_email='boundary-user@example.test', smtp_password='placeholder-not-a-secret',
    )
    Token.objects.create(user=user, key=PLACEHOLDER_KEY)
    company = Company.objects.create(
        name='Boundary Hotel', billing_entity='BMAsia Limited', notes='Lobby',
        care_summary='Synthetic care summary', it_notes='Synthetic IT note', soundtrack_account_id='SA-PLACEHOLDER',
    )
    contact = Contact.objects.create(company=company, name='Sam Example', email='sam@example.test')
    contract = Contract.objects.create(
        company=company, contract_number='HK-CT-BOUNDARY-1', status='Active',
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        value=Decimal('100.00'), total_value=Decimal('100.00'), currency='USD',
    )
    task = Task.objects.create(title='Boundary task', company=company, assigned_to=user, created_by=user,
                               related_contract=contract, related_contact=contact)
    return {'user': user, 'company': company, 'contact': contact, 'contract': contract, 'task': task}


# ------------------------------------------------------------------ (a) published lists


def test_published_lists_respect_the_never_publish_rule():
    published_models = {cls.model for cls in published_collections().values()}
    problems = []
    for cls in _crm_toolsets():
        for name in cls.fields:
            field = cls.model._meta.get_field(name)
            reason = never_publish_reason(cls.model, field)
            if reason:
                problems.append(f'{cls.__name__}.{name}: {reason}')
            if field.is_relation and (field.related_model not in published_models
                                      or is_protected_model(field.related_model)):
                problems.append(f'{cls.__name__}.{name}: relation to an unpublished model')
    assert problems == []


def test_published_lists_are_published_in_full():
    """Nothing a toolset lists is silently dropped: list, schema and boundary agree."""
    boundary = _boundary()
    for name, cls in published_collections().items():
        assert boundary.fields[name] == list(help_.collection_schema(cls)['$jsonSchema']['properties'])
        assert set(boundary.fields[name]) == set(cls.fields), name


def test_search_fields_are_published():
    boundary = _boundary()
    for name in published_collections():
        assert boundary.search_fields_published(name), name


def test_never_publish_rule_covers_names_patterns_encrypted_fields_and_protected_models():
    from encrypted_model_fields.fields import EncryptedCharField

    user_model = get_user_model()
    assert never_publish_reason(user_model, user_model._meta.get_field('password'))
    assert never_publish_reason(user_model, user_model._meta.get_field('smtp_password'))
    assert never_publish_reason(user_model, user_model._meta.get_field('username'))  # protected model
    assert never_publish_reason(Token, Token._meta.get_field('key'))
    assert never_publish_reason(Contact, Contact._meta.get_field('unsubscribe_token'))
    assert never_publish_reason(EmailLog, EmailLog._meta.get_field('tracking_token'))
    for name in ('token', 'secret', 'api_key', 'client_secret', 'refresh_token', 'smtp_host'):
        field = EncryptedCharField(max_length=10) if name == 'secret' else Contact._meta.get_field('notes').clone()
        field.set_attributes_from_name(name)
        assert never_publish_reason(Company, field), name
    encrypted = EncryptedCharField(max_length=10)
    encrypted.set_attributes_from_name('remote_reference')
    assert never_publish_reason(Company, encrypted) == 'encrypted field'
    for model, name in ((Task, 'assigned_to'), (Task, 'created_by'), (Quote, 'created_by'),
                        (Opportunity, 'owner'), (Ticket, 'assigned_to'), (KBArticle, 'author')):
        assert never_publish_reason(model, model._meta.get_field(name)) == 'relation to a protected model'
    assert never_publish_reason(Company, Company._meta.get_field('name')) is None


# ------------------------------------------------------------------ (b) every relation walk


def _relations(model):
    """Every relation on a model, forward and reverse, with the name a query path uses."""
    for field in model._meta.get_fields():
        if field.is_relation and field.related_model is not None:
            yield field.name, field


def _some_field(model):
    for field in model._meta.concrete_fields:
        if not field.is_relation:
            return field.name
    return 'pk'


def _shapes(path, relation_path, target_field):
    return [
        [{'$project': {'x': '$' + path}}],
        [{'$project': {path: 1}}],
        [{'$match': {path: 'x'}}],
        [{'$match': {path: {'$eq': 'x'}}}],
        [{'$match': {path: {'$regex': '^a'}}}],
        [{'$match': {path: {'$istartswith': 'a'}}}],
        [{'$match': {path: {'$gt': ''}}}],
        [{'$match': {'$or': [{path: 'x'}]}}],
        [{'$match': {'$and': [{'$nor': [{path: 'x'}]}]}}],
        [{'$sort': {path: 1}}],
        [{'$sort': {'-' + path: 1}}],
        [{'$group': {'_id': '$' + path}}],
        [{'$group': {'_id': {'k': '$' + path}}}],
        [{'$group': {'_id': None, 'n': {'$max': '$' + path}}}],
        [{'$lookup': {'from': 'company', 'localField': relation_path, 'foreignField': '_id', 'as': 'a'}},
         {'$project': {'x': '$a.' + target_field}}],
    ]


def test_unpublished_relations_are_refused_in_every_query_shape():
    """Walk every published relation chain (two steps deep) and try every unpublished relation."""
    boundary = _boundary()
    failures, protected_seen = [], set()
    checked = 0

    def attempt(collection, pipeline, name, here):
        nonlocal checked
        checked += 1
        expected = unknown_field_message(name, here, boundary.fields[here])
        try:
            run(collection, pipeline)
        except ValueError as exc:
            if str(exc) != expected:
                failures.append((collection, pipeline, str(exc)))
        else:
            failures.append((collection, pipeline, 'not refused'))

    def walk(collection, prefix, model, depth):
        here = boundary.collection_of[model]
        for rel_name, field in _relations(model):
            if rel_name in boundary.fields[here]:
                if depth < 2:
                    walk(collection, prefix + rel_name + '__', field.related_model, depth + 1)
                continue
            target = field.related_model
            if is_protected_model(target):
                protected_seen.add(target._meta.label)
            target_fields = [_some_field(target)]
            if target is get_user_model():
                target_fields = ['password', 'smtp_password', 'auth_token__key']
                protected_seen.add(Token._meta.label)
            for target_field in target_fields:
                for pipeline in _shapes(prefix + rel_name + '__' + target_field, prefix + rel_name, target_field):
                    attempt(collection, pipeline, rel_name, here)
            target_field = target_fields[0]
            attname = getattr(field, 'attname', None)
            if field.concrete and attname and attname != rel_name:
                for pipeline in _shapes(prefix + attname, prefix + attname, target_field)[:-1]:
                    attempt(collection, pipeline, attname, here)

    for name, cls in published_collections().items():
        walk(name, '', cls.model, 0)
    assert failures == []
    assert checked > 1000
    assert {'crm_app.User', 'authtoken.Token'} <= protected_seen


@pytest.mark.parametrize('collection, pipeline, name, on', [
    ('task', [{'$project': {'x': '$assigned_to__auth_token__key'}}], 'assigned_to', 'task'),
    ('task', [{'$project': {'x': '$created_by__password'}}], 'created_by', 'task'),
    ('task', [{'$match': {'assigned_to_id': 1}}], 'assigned_to_id', 'task'),
    ('quote', [{'$group': {'_id': '$created_by__username'}}], 'created_by', 'quote'),
    ('opportunity', [{'$sort': {'owner__smtp_password': 1}}], 'owner', 'opportunity'),
    ('company', [{'$match': {'contracts__value': {'$gt': 0}}}], 'contracts', 'company'),
    ('company', [{'$project': {'care_summary': 1}}], 'care_summary', 'company'),
    ('company', [{'$match': {'it_notes': {'$regex': '.'}}}], 'it_notes', 'company'),
    ('contract', [{'$project': {'x': '$company__care_summary'}}], 'care_summary', 'company'),
    ('contract', [{'$match': {'company__parent_company__it_notes': {'$istartswith': 's'}}}], 'it_notes', 'company'),
    ('task', [{'$sort': {'related_contract__company__soundtrack_account_id': 1}}],
     'soundtrack_account_id', 'company'),
    ('contract', [{'$lookup': {'from': 'company', 'localField': 'company', 'foreignField': '_id', 'as': 'co'}},
                  {'$project': {'x': '$co.care_summary'}}], 'care_summary', 'company'),
    ('contract', [{'$lookup': {'from': 'quote', 'localField': 'quote', 'foreignField': '_id', 'as': 'q'}}],
     'quote', 'contract'),
    ('contact', [{'$match': {'unsubscribe_token': 'x'}}], 'unsubscribe_token', 'contact'),
    ('zone', [{'$match': {'company__name__x__y': 'x'}, '$project': {'n': '$api_raw_data'}}], 'api_raw_data', 'zone'),
])
def test_unpublished_path_is_refused_with_the_published_field_list(data, collection, pipeline, name, on):
    message = refused(collection, pipeline)
    assert message == unknown_field_message(name, on, _boundary().fields[on])


def test_refused_hidden_and_nonexistent_names_look_the_same():
    boundary = _boundary()
    for collection, path, name, on in (
        ('company', 'care_summary', 'care_summary', 'company'),
        ('company', 'care_summarx', 'care_summarx', 'company'),
        ('task', 'related_contract__company__it_notes', 'it_notes', 'company'),
        ('task', 'related_contract__company__it_notez', 'it_notez', 'company'),
        ('task', 'assigned_to__password', 'assigned_to', 'task'),
        ('task', 'assigned_tx__password', 'assigned_tx', 'task'),
    ):
        message = refused(collection, [{'$match': {path: 'x'}}])
        # The message is a function of the typed name and the published list only.
        assert message == unknown_field_message(name, on, boundary.fields[on])


# ------------------------------------------------------------------ (c) reviewer probe shapes


def test_probe_projection_through_assigned_user_is_refused(data):
    message = refused('task', [{'$match': {'title': 'Boundary task'}},
                               {'$project': {'pw': '$assigned_to__password', 'tok': '$assigned_to__auth_token__key',
                                             'smtp': '$assigned_to__smtp_password'}}])
    assert message.startswith("Unknown field 'assigned_to' on collection 'task'.")
    assert PLACEHOLDER_KEY not in message and 'placeholder' not in message


def test_probe_filter_cannot_be_used_as_an_oracle(data):
    hit = refused('task', [{'$match': {'assigned_to__auth_token__key': {'$regex': '^' + PLACEHOLDER_KEY[0]}}},
                           {'$project': {'t': '$title'}}])
    miss = refused('task', [{'$match': {'assigned_to__auth_token__key': {'$regex': '^Z'}}},
                            {'$project': {'t': '$title'}}])
    assert hit == miss
    for op in ('$eq', '$gt', '$gte', '$lt', '$lte', '$in', '$istartswith', '$icontains', '$iexact'):
        value = [PLACEHOLDER_KEY] if op == '$in' else PLACEHOLDER_KEY[:3]
        assert refused('task', [{'$match': {'assigned_to__auth_token__key': {op: value}}}]) == hit
    assert refused('task', [{'$match': {'assigned_to__password__startswith': 'p'}}]) == hit


def test_output_limited_to_published_fields_without_project(data):
    rows = run('company', [{'$match': {'name': 'Boundary Hotel'}}])
    assert len(rows) == 1
    assert list(rows[0]) == _boundary().output_columns('company')
    for hidden in ('care_summary', 'it_notes', 'soundtrack_account_id', 'care_summary_updated_by'):
        assert hidden not in rows[0]
    rows = run('task', [{'$match': {'title': 'Boundary task'}}])
    assert 'assigned_to_id' not in rows[0] and 'created_by_id' not in rows[0]
    assert rows[0]['related_contract_id'] == str(data['contract'].pk)
    rows = run('contact', [{'$match': {'name': 'Sam Example'}}])
    assert 'unsubscribe_token' not in rows[0]


@pytest.mark.parametrize('pipeline', [
    [{'$project': {'notes': 0}}],
    [{'$project': {}}],
    [{'$project': {'name': 1}}, {'$project': {'name': 0}}],
    [{'$match': {'name': 'Boundary Hotel'}, '$project': {'name': 1}}],
    [{'$match': {'name': 'Boundary Hotel'}, '$group': {'_id': '$name'}}],
    [{'$sort': {'name': 1}, '$project': {'name': 1}}],
    [{'$limit': 5, '$group': {'_id': None, 'n': {'$sum': 1}}}],
    [{'$lookup': {'from': 'company', 'localField': 'parent_company', 'foreignField': '_id', 'as': 'p'},
      '$match': {'name': 'Boundary Hotel'}}],
    [{'$skip': 0}],
])
def test_output_limited_to_published_fields_for_any_stage_combination(data, pipeline):
    columns = set(_boundary().output_columns('company'))
    rows = run('company', pipeline)
    assert rows
    for row in rows:
        assert set(row) <= columns | {'name'}


def test_published_paths_still_work(data):
    contract_id = str(data['contract'].pk)
    assert run('task', [{'$match': {'related_contract__company__name': 'Boundary Hotel'}},
                        {'$project': {'t': '$title', 'c': '$related_contract__contract_number'}}]) == [
        {'t': 'Boundary task', 'c': 'HK-CT-BOUNDARY-1'}]
    assert run('task', [{'$match': {'related_contract__in': [contract_id]}}, {'$project': {'title': 1}}]) == [
        {'title': 'Boundary task'}]
    assert run('task', [{'$match': {'related_contract_id': contract_id}}, {'$project': {'title': 1}}]) == [
        {'title': 'Boundary task'}]
    assert run('task', [{'$match': {'related_opportunity__isnull': True, '_id': str(data['task'].pk)}},
                        {'$project': {'_id': 1}}]) == [{'_id': str(data['task'].pk)}]
    assert run('contract', [{'$match': {'created_at__year__gte': 2000, 'notes__icontains': ''}},
                            {'$project': {'contract_number': 1}}]) == [{'contract_number': 'HK-CT-BOUNDARY-1'}]
    assert run('company', [{'$search': {'text': {'query': 'lobby'}}}, {'$project': {'name': 1}}]) == [
        {'name': 'Boundary Hotel'}]
    assert run('company', [{'$match': {'$text': {'$search': 'boundary'}}}, {'$project': {'name': 1}}]) == [
        {'name': 'Boundary Hotel'}]


def test_refusal_reaches_the_client_as_one_line(data):
    with pytest.raises(ToolError) as caught:
        async_to_sync(mcp_server.call_tool)('query_data_collections', {
            'collection': 'task', 'search_pipeline': [{'$project': {'x': '$assigned_to__password'}}]})
    text = str(caught.value)
    assert '\n' not in text
    assert text.startswith("Error executing tool query_data_collections: Unknown field 'assigned_to' on collection "
                           "'task'.")


# ------------------------------------------------------------------ fail closed


def _mcp_call(client, key, name, arguments):
    return client.post('/mcp/', {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
                                 'params': {'name': name, 'arguments': arguments}},
                       format='json', HTTP_ACCEPT='application/json, text/event-stream',
                       HTTP_AUTHORIZATION=f'Token {key}')


@pytest.fixture
def restore_boundary(monkeypatch):
    tool = mcp_server._tool_manager.get_tool('query_data_collections')
    saved_fn, saved_state = tool.fn, dict(help_._STATE)
    saved_query = query_tool._QueryExecutor.query
    yield
    monkeypatch.undo()
    tool.fn = saved_fn
    help_._STATE.update(saved_state)
    query_tool._QueryExecutor.query = saved_query
    assert boundary_active()


def test_library_version_is_the_verified_one():
    assert help_._library_version() == help_.SUPPORTED_LIBRARY[1]
    assert boundary_active()


def test_query_over_http_works_while_the_boundary_is_active(data):
    response = _mcp_call(APIClient(), PLACEHOLDER_KEY, 'query_data_collections',
                         {'collection': 'company', 'search_pipeline': [{'$project': {'name': 1}}]})
    assert response.status_code == 200
    result = response.json()['result']
    assert result['isError'] is False
    assert json.loads(result['content'][0]['text']) == [{'name': 'Boundary Hotel'}]


def test_missing_library_internals_leave_the_app_running_and_the_query_tool_refusing(
        data, monkeypatch, caplog, restore_boundary):
    monkeypatch.delattr(query_tool, '_QueryExecutor')
    help_._STATE['installed'] = False
    with caplog.at_level(logging.ERROR, logger='crm_app.mcp_query_help'):
        assert help_.install() is False
    errors = [r for r in caplog.records if r.name == 'crm_app.mcp_query_help' and r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert not boundary_active()

    client = APIClient()
    response = _mcp_call(client, PLACEHOLDER_KEY, 'query_data_collections',
                         {'collection': 'company', 'search_pipeline': []})
    assert response.status_code == 200
    assert response.json() == {'jsonrpc': '2.0', 'id': 7, 'result': {
        'content': [{'type': 'text', 'text': QUERY_UNAVAILABLE_MESSAGE}], 'isError': True}}
    with pytest.raises(ToolError) as caught:
        async_to_sync(mcp_server.call_tool)('query_data_collections', {'collection': 'company'})
    assert QUERY_UNAVAILABLE_MESSAGE in str(caught.value)
    # Other tools keep working.
    described = _mcp_call(client, PLACEHOLDER_KEY, 'describe_collection', {'name': 'company'})
    assert described.json()['result']['isError'] is False


def test_unverified_library_version_refuses_queries(data, monkeypatch, caplog, restore_boundary):
    monkeypatch.setattr(help_, '_library_version', lambda: '9.9.9')
    with caplog.at_level(logging.ERROR, logger='crm_app.mcp_query_help'):
        assert help_.install() is False
    assert not boundary_active()
    response = _mcp_call(APIClient(), PLACEHOLDER_KEY, 'query_data_collections',
                         {'collection': 'company', 'search_pipeline': []})
    assert response.json()['result']['content'][0]['text'] == QUERY_UNAVAILABLE_MESSAGE


def test_install_is_idempotent(restore_boundary):
    wrapped = query_tool._QueryExecutor.query
    assert help_.install() is True
    assert query_tool._QueryExecutor.query is wrapped
