"""query_data_collections: relation key paths, pipeline shape, contact email preferences."""
import json
from datetime import date
from decimal import Decimal

import pytest
from mcp_server.query_tool import _QueryExecutor

from crm_app.mcp_query_help import (
    PIPELINE_SHAPE_MESSAGE, boundary_for, published_collections, unknown_field_message,
)
from crm_app.models import Company, Contact, Contract, Task


def _executor():
    return _QueryExecutor(published_collections(), context=None, request=None)


def run(collection, pipeline):
    result = _executor().query(collection, pipeline)
    return json.loads(result[0].text) if result else []


def _published(collection):
    return boundary_for(published_collections()).fields[collection]


@pytest.fixture
def data():
    company = Company.objects.create(name='Path Hotel', billing_entity='BMAsia Limited',
                                     current_plan='Plan A', music_zone_count=3)
    contract = Contract.objects.create(
        company=company, contract_number='HK-CT-PATH-1', status='Active',
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        value=Decimal('100.00'), total_value=Decimal('100.00'), currency='USD', tax_rate=Decimal('7.00'),
    )
    Task.objects.create(title='Path task', company=company, related_contract=contract)
    Contact.objects.create(company=company, name='Pat Example', email='pat@example.test',
                           unsubscribed=True, receives_renewal_emails=False)
    return {'company': company, 'contract': contract}


# ------------------------------------------------------------------ relation key paths

RELATION_KEY_PATHS = [
    # (collection, path, refused name, collection named in the error)
    ('task', 'company_id__current_plan', 'current_plan', 'company'),
    ('task', 'company_id__music_zone_count', 'music_zone_count', 'company'),
    ('task', 'company_id__name', 'name', 'company'),
    ('contract', 'company_id__current_plan', 'current_plan', 'company'),
    ('task', 'related_contract_id__tax_rate', 'tax_rate', 'contract'),
    ('task', 'related_contract_id__company__current_plan', 'company', 'contract'),
    ('invoice', 'contract_id__tax_rate', 'tax_rate', 'contract'),
]


def _shapes(path):
    return {
        'project': [{'$project': {'x': '$' + path}}],
        'match': [{'$match': {path: 'x'}}],
        'sort': [{'$sort': {path: 1}}],
    }


@pytest.mark.parametrize('shape', ['project', 'match', 'sort'])
@pytest.mark.parametrize('collection, path, name, on', RELATION_KEY_PATHS)
def test_relation_key_path_is_refused(data, collection, path, name, on, shape):
    with pytest.raises(ValueError) as caught:
        run(collection, _shapes(path)[shape])
    assert str(caught.value) == unknown_field_message(name, on, _published(on))


def test_relation_key_with_one_lookup_still_works(data):
    contract_id = str(data['contract'].pk)
    assert run('task', [{'$match': {'related_contract_id': contract_id}}, {'$project': {'title': 1}}]) == [
        {'title': 'Path task'}]
    assert run('task', [{'$match': {'related_contract_id__in': [contract_id]}}, {'$project': {'title': 1}}]) == [
        {'title': 'Path task'}]
    assert run('task', [{'$match': {'related_contract_id__isnull': False}}, {'$project': {'title': 1}}]) == [
        {'title': 'Path task'}]


# ------------------------------------------------------------------ pipeline shape


@pytest.mark.parametrize('pipeline', [None, {}, {'$match': {}}, 'x', 7, [{'$match': {}}, 'x'], [[]], [None]])
def test_pipeline_must_be_a_list_of_objects(data, pipeline):
    with pytest.raises(ValueError) as caught:
        _executor().query('company', pipeline)
    assert str(caught.value) == PIPELINE_SHAPE_MESSAGE


def test_empty_pipeline_returns_all_rows_with_published_fields(data):
    rows = run('company', [])
    assert [row['name'] for row in rows] == ['Path Hotel']
    assert list(rows[0]) == boundary_for(published_collections()).output_columns('company')
    assert 'current_plan' not in rows[0]


# ------------------------------------------------------------------ contact email preferences

EMAIL_PREFERENCES = [
    'unsubscribed', 'receives_notifications', 'receives_renewal_emails', 'receives_seasonal_emails',
    'receives_payment_emails', 'receives_quarterly_emails', 'receives_soundtrack_alerts',
    'receives_quote_emails', 'receives_contract_emails', 'receives_invoice_emails',
]


def test_contact_email_preferences_are_published(data):
    assert set(EMAIL_PREFERENCES) <= set(_published('contact'))
    receives = {f.name for f in Contact._meta.concrete_fields if f.name.startswith('receives_')}
    assert receives <= set(_published('contact'))
    assert 'unsubscribe_token' not in _published('contact')
    assert 'mobile' not in _published('contact')
    rows = run('contact', [{'$match': {'unsubscribed': True, 'receives_renewal_emails': False}},
                           {'$project': {'name': 1, 'unsubscribed': 1, 'receives_invoice_emails': 1}}])
    assert rows == [{'name': 'Pat Example', 'unsubscribed': True, 'receives_invoice_emails': True}]
    row = run('contact', [{'$match': {'name': 'Pat Example'}}])[0]
    assert set(EMAIL_PREFERENCES) <= set(row)
    assert 'unsubscribe_token' not in row and 'mobile' not in row


# ------------------------------------------------------------------ tax and discount fields


def test_contract_tax_rate_can_be_filtered_and_projected(data):
    rows = run('contract', [{'$match': {'tax_rate': {'$gte': 5}}},
                            {'$project': {'contract_number': 1, 'tax_rate': 1, 'discount_percentage': 1}}])
    assert rows == [{'contract_number': 'HK-CT-PATH-1', 'tax_rate': 7.0, 'discount_percentage': 0.0}]
    assert run('contract', [{'$match': {'tax_rate': {'$lt': 5}}}]) == []


def test_quote_discount_amount_can_be_filtered_and_projected(data):
    from crm_app.models import Quote

    Quote.objects.create(company=data['company'], quote_number='HK-QT-PATH-1', valid_from=date(2026, 11, 1),
                         valid_until=date(2026, 12, 1), discount_amount=Decimal('25.00'))
    rows = run('quote', [{'$match': {'discount_amount': {'$gt': 0}}},
                         {'$project': {'quote_number': 1, 'discount_amount': 1, 'tax_amount': 1}}])
    assert len(rows) == 1
    assert rows[0]['quote_number'] == 'HK-QT-PATH-1' and rows[0]['discount_amount'] == 25.0
    assert 'tax_amount' in rows[0]
