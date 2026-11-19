"""query_data_collections: published fields, valid pipelines, one-line errors, describe_collection.

Queries go through the real registered MCP tool (FastMCP.call_tool), so the
error text checked here is the text a client receives.
"""
import json
import re
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from asgiref.sync import async_to_sync
from mcp.server.fastmcp.exceptions import ToolError
from mcp_server import mcp_server
from mcp_server.query_tool import ModelQueryToolsetMeta, _QueryExecutor, generate_json_schema

from crm_app import mcp as crm_mcp
from crm_app.mcp_query_help import published_collections, published_fields
from crm_app.models import (
    Company, Contact, Contract, Device, Invoice, Opportunity, Quote, Task, Zone,
)

TOOL_ERROR_PREFIX = 'Error executing tool query_data_collections: '


def _crm_toolsets():
    return [cls for cls in ModelQueryToolsetMeta.registry.values() if cls.__module__ == crm_mcp.__name__]


def _content(result):
    return result[0] if isinstance(result, tuple) else result


def run_query(collection, pipeline):
    content = _content(async_to_sync(mcp_server.call_tool)(
        'query_data_collections', {'collection': collection, 'search_pipeline': pipeline},
    ))
    if not content:
        return []
    return json.loads(content[0].text)


def tool_error_text(name, arguments):
    """The error text of a failed tool call. A caller mistake comes back as an error result
    (the reply clients get over HTTP is the same either way); a fault raises ToolError."""
    from mcp.types import CallToolResult

    try:
        result = async_to_sync(mcp_server.call_tool)(name, arguments)
    except ToolError as exc:
        return str(exc)
    assert isinstance(result, CallToolResult) and result.isError, result
    return result.content[0].text


def query_error(collection, pipeline):
    text = tool_error_text('query_data_collections', {'collection': collection, 'search_pipeline': pipeline})
    assert text.startswith(TOOL_ERROR_PREFIX), text
    message = text[len(TOOL_ERROR_PREFIX):]
    assert '\n' not in message
    return message


def _published_line(collection):
    return ', '.join(published_fields(published_collections()[collection]))


@pytest.fixture
def data():
    parent = Company.objects.create(name='Query Group Parent', billing_entity='BMAsia Limited',
                                    is_corporate_parent=True)
    hotel = Company.objects.create(
        name='Query Riverside Hotel', legal_entity_name='Query Riverside Hotel Co., Ltd.',
        billing_entity='BMAsia (Thailand) Co., Ltd.', country='Thailand', city='Bangkok',
        address_line1='1 Example Road', address_line2='Floor 2', state='Bangkok',
        postal_code='10110', tax_id='0105500000001', branch='00001', parent_company=parent,
        notes='Rooftop bar and lobby',
    )
    resort = Company.objects.create(name='Query Beach Resort', billing_entity='BMAsia Limited',
                                    country='Vietnam', city='Da Nang', branch='00002')
    contact = Contact.objects.create(company=hotel, name='Alex Example', email='alex@example.test',
                                     is_active=True)
    Contact.objects.create(company=hotel, name='Former Example', email='former@example.test', is_active=False)
    active = Contract.objects.create(
        company=hotel, contract_number='TH-CT-QUERY-1', status='Active',
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        value=Decimal('1000.00'), total_value=Decimal('1000.00'), currency='THB',
        notes='Lobby music renewal',
    )
    sent = Contract.objects.create(
        company=resort, contract_number='HK-CT-QUERY-2', status='Sent',
        start_date=date(2026, 2, 1), end_date=date(2027, 1, 31),
        value=Decimal('500.00'), total_value=Decimal('500.00'), currency='USD',
    )
    Contract.objects.create(
        company=resort, contract_number='HK-CT-QUERY-3', status='Active',
        start_date=date(2026, 3, 1), end_date=date(2027, 2, 28),
        value=Decimal('250.00'), total_value=Decimal('250.00'), currency='USD',
    )
    invoice = Invoice.objects.create(
        company=hotel, contract=active, invoice_number='TH-IV-QUERY-1', status='Sent',
        issue_date=date(2026, 9, 9), due_date=date(2026, 10, 9),
        amount=Decimal('1000.00'), total_amount=Decimal('1000.00'), currency='THB',
    )
    opportunity = Opportunity.objects.create(company=resort, name='Query Spa upgrade',
                                             expected_value=Decimal('750.00'))
    quote = Quote.objects.create(company=hotel, contact=contact, quote_number='TH-QT-QUERY-1',
                                 valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1))
    task = Task.objects.create(company=hotel, title='Query follow up', related_contact=contact,
                               related_contract=active, related_opportunity=opportunity)
    device = Device.objects.create(company=hotel, name='Query PC 1')
    seen = datetime(2026, 11, 10, 8, 30, tzinfo=dt_timezone.utc)
    zone = Zone.objects.create(company=hotel, name='Query Lobby', platform='beatbreeze', status='online',
                               device=device, device_name='Lobby player', last_seen_online=seen)
    Zone.objects.create(company=hotel, name='Query Old Bar', platform='soundtrack', status='cancelled',
                        is_orphaned=True)
    return {
        'hotel': hotel, 'resort': resort, 'contact': contact, 'active': active, 'sent': sent,
        'invoice': invoice, 'opportunity': opportunity, 'quote': quote, 'task': task,
        'device': device, 'zone': zone,
    }


# ------------------------------------------------------------------ published fields


def test_every_published_field_is_a_concrete_model_field():
    toolsets = _crm_toolsets()
    assert len(toolsets) >= 17
    problems = []
    for cls in toolsets:
        for name in cls.fields:
            try:
                field = cls.model._meta.get_field(name)
            except Exception:
                problems.append(f'{cls.__name__}.{name} does not exist')
                continue
            if not field.concrete:
                problems.append(f'{cls.__name__}.{name} is not a concrete field')
    assert problems == []


def test_newly_published_fields_are_in_the_schema():
    expected = {
        'company': {'address_line1', 'address_line2', 'state', 'postal_code', 'branch', 'tax_id'},
        'contact': {'is_active', 'unsubscribed', 'receives_notifications', 'receives_renewal_emails',
                    'receives_seasonal_emails', 'receives_payment_emails', 'receives_quarterly_emails',
                    'receives_soundtrack_alerts', 'receives_quote_emails', 'receives_contract_emails',
                    'receives_invoice_emails'},
        'contract': {'tax_rate', 'tax_amount', 'discount_percentage'},
        'invoice': {'issue_date', 'discount_amount'},
        'opportunity': {'expected_value'},
        'quote': {'contact', 'tax_amount', 'discount_amount'},
        'task': {'related_contact', 'related_contract', 'related_opportunity'},
        'zone': {'status', 'platform', 'is_orphaned', 'device', 'device_name', 'last_seen_online'},
    }
    collections = published_collections()
    for collection, names in expected.items():
        assert names <= set(published_fields(collections[collection])), collection


def test_zone_instructions_describe_real_state_fields():
    text = crm_mcp.ZoneQuery.extra_instructions
    assert 'is_active' not in text
    for name in ('status', 'platform', 'is_orphaned', 'device', 'last_seen_online'):
        assert name in text


def test_every_toolset_offers_case_insensitive_operators():
    for cls in _crm_toolsets():
        assert set(cls.extra_filters) == {'icontains', 'iexact', 'istartswith'}, cls.__name__


def test_pdf_guidance_on_document_collections():
    assert 'generate_contract_pdf(id)' in crm_mcp.ContractQuery.extra_instructions
    assert 'generate_quote_pdf(id)' in crm_mcp.QuoteQuery.extra_instructions
    assert 'generate_invoice_pdf(id)' in crm_mcp.InvoiceQuery.extra_instructions
    for cls in (crm_mcp.ContractQuery, crm_mcp.QuoteQuery, crm_mcp.InvoiceQuery):
        assert 'get_commercial_document_context' in cls.extra_instructions


# ------------------------------------------------------------------ valid pipelines


def test_match_on_contract_status(data):
    rows = run_query('contract', [{'$match': {'status': 'Sent'}}, {'$project': {'contract_number': 1}}])
    assert rows == [{'contract_number': 'HK-CT-QUERY-2'}]


def test_lookup_contract_to_company_with_projection(data):
    rows = run_query('contract', [
        {'$lookup': {'from': 'company', 'localField': 'company', 'foreignField': '_id', 'as': 'co'}},
        {'$match': {'co.name': 'Query Riverside Hotel'}},
        {'$project': {'contract_number': 1, 'company_name': '$co.name'}},
    ])
    assert rows == [{'contract_number': 'TH-CT-QUERY-1', 'company_name': 'Query Riverside Hotel'}]


def test_sort_and_limit(data):
    rows = run_query('contract', [
        {'$sort': {'value': -1}}, {'$limit': 2}, {'$project': {'contract_number': 1}},
    ])
    assert rows == [{'contract_number': 'TH-CT-QUERY-1'}, {'contract_number': 'HK-CT-QUERY-2'}]


def test_group_with_sum(data):
    rows = run_query('contract', [
        {'$match': {'currency': 'USD'}},
        {'$group': {'_id': '$status', 'count': {'$sum': 1}, 'total': {'$sum': '$value'}}},
    ])
    by_status = {row['status']: row for row in rows}
    assert by_status['Active']['count'] == 1 and float(by_status['Active']['total']) == 250.0
    assert by_status['Sent']['count'] == 1 and float(by_status['Sent']['total']) == 500.0


def test_text_search(data):
    rows = run_query('company', [{'$search': {'text': {'query': 'rooftop'}}}, {'$project': {'name': 1}}])
    assert rows == [{'name': 'Query Riverside Hotel'}]


def test_regex_and_in(data):
    rows = run_query('contract', [
        {'$match': {'contract_number': {'$regex': '^HK-CT-QUERY'}, 'status': {'$in': ['Sent', 'Draft']}}},
        {'$project': {'contract_number': 1}},
    ])
    assert rows == [{'contract_number': 'HK-CT-QUERY-2'}]


def test_case_insensitive_operators(data):
    project = {'$project': {'name': 1}}
    assert run_query('company', [{'$match': {'name': {'$icontains': 'RIVERSIDE'}}}, project]) == [
        {'name': 'Query Riverside Hotel'}]
    assert run_query('company', [{'$match': {'name': {'$iexact': 'query beach resort'}}}, project]) == [
        {'name': 'Query Beach Resort'}]
    assert run_query('company', [{'$match': {'city': {'$istartswith': 'da'}}}, project]) == [
        {'name': 'Query Beach Resort'}]
    rows = run_query('contract', [
        {'$lookup': {'from': 'company', 'localField': 'company', 'foreignField': '_id', 'as': 'co'}},
        {'$match': {'$or': [{'co.name': {'$icontains': 'beach'}}, {'notes': {'$icontains': 'LOBBY'}}]}},
        {'$sort': {'contract_number': 1}}, {'$project': {'contract_number': 1}},
    ])
    assert [row['contract_number'] for row in rows] == ['HK-CT-QUERY-2', 'HK-CT-QUERY-3', 'TH-CT-QUERY-1']


def test_queries_on_newly_published_company_fields(data):
    rows = run_query('company', [
        {'$match': {'address_line1': '1 Example Road', 'address_line2': 'Floor 2', 'state': 'Bangkok',
                    'postal_code': '10110', 'tax_id': '0105500000001', 'branch': '00001'}},
        {'$project': {'name': 1, 'branch': 1, 'tax_id': 1}},
    ])
    assert rows == [{'name': 'Query Riverside Hotel', 'branch': '00001', 'tax_id': '0105500000001'}]


def test_queries_on_newly_published_contact_invoice_opportunity_quote_fields(data):
    assert run_query('contact', [{'$match': {'is_active': False}}, {'$project': {'name': 1}}]) == [
        {'name': 'Former Example'}]
    assert run_query('invoice', [{'$match': {'issue_date': '2026-09-09'}}, {'$project': {'invoice_number': 1}}]) == [
        {'invoice_number': 'TH-IV-QUERY-1'}]
    rows = run_query('opportunity', [{'$match': {'expected_value': {'$gte': 700}}}, {'$project': {'name': 1}}])
    assert rows == [{'name': 'Query Spa upgrade'}]
    rows = run_query('quote', [
        {'$lookup': {'from': 'contact', 'localField': 'contact', 'foreignField': '_id', 'as': 'ct'}},
        {'$match': {'contact': str(data['contact'].pk)}},
        {'$project': {'quote_number': 1, 'contact_name': '$ct.name'}},
    ])
    assert rows == [{'quote_number': 'TH-QT-QUERY-1', 'contact_name': 'Alex Example'}]


def test_queries_on_newly_published_task_fields(data):
    rows = run_query('task', [
        {'$match': {'related_contact': str(data['contact'].pk), 'related_contract': str(data['active'].pk),
                    'related_opportunity': str(data['opportunity'].pk)}},
        {'$lookup': {'from': 'contract', 'localField': 'related_contract', 'foreignField': '_id', 'as': 'k'}},
        {'$project': {'title': 1, 'contract_number': '$k.contract_number'}},
    ])
    assert rows == [{'title': 'Query follow up', 'contract_number': 'TH-CT-QUERY-1'}]


def test_queries_on_newly_published_zone_fields(data):
    rows = run_query('zone', [
        {'$match': {'status': 'online', 'platform': 'beatbreeze', 'is_orphaned': False,
                    'device': str(data['device'].pk), 'device_name': 'Lobby player',
                    'last_seen_online': {'$gte': '2026-11-10T00:00:00Z'}}},
        {'$lookup': {'from': 'device', 'localField': 'device', 'foreignField': '_id', 'as': 'd'}},
        {'$project': {'name': 1, 'device_label': '$d.name'}},
    ])
    assert rows == [{'name': 'Query Lobby', 'device_label': 'Query PC 1'}]
    assert run_query('zone', [{'$match': {'is_orphaned': True}}, {'$project': {'status': 1}}]) == [
        {'status': 'cancelled'}]


VALID_PIPELINES = [
    ('contract', [{'$match': {'status': 'Active'}}]),
    ('contract', [{'$lookup': {'from': 'company', 'localField': 'company', 'foreignField': '_id', 'as': 'co'}},
                  {'$project': {'contract_number': 1, 'n': '$co.name'}}]),
    ('contract', [{'$sort': {'end_date': 1}}, {'$limit': 2}]),
    ('contract', [{'$group': {'_id': '$currency', 'total': {'$sum': '$value'}}}]),
    ('company', [{'$search': {'text': {'query': 'hotel'}}}]),
    ('company', [{'$match': {'name': {'$regex': 'Query'}}}]),
    ('contract', [{'$match': {'status': {'$in': ['Active', 'Sent']}}}]),
    ('contract', [{'$match': {'status': 'NoSuchStatus'}}]),
    ('zone', [{'$match': {'company__name': 'Query Riverside Hotel'}}]),
    ('contact', [{'$match': {'is_active': True}}]),
    ('quote', [{'$match': {'quote_number': 'TH-QT-QUERY-1'}}]),
    ('invoice', [{'$match': {'status': 'Sent'}}]),
]


def _rows(result):
    return json.loads(result[0].text) if result else []


@pytest.mark.parametrize('collection, pipeline', VALID_PIPELINES)
def test_valid_queries_return_the_published_projection_of_the_library_result(data, collection, pipeline):
    """Same rows as the unwrapped library; output limited to published fields."""
    from crm_app.mcp_query_help import boundary_for

    original = _QueryExecutor.query.__wrapped__
    collections = published_collections()
    executor = _QueryExecutor(collections, context=None, request=None)
    wrapped = _rows(_QueryExecutor.query(executor, collection, json.loads(json.dumps(pipeline))))
    unwrapped = _rows(original(executor, collection, json.loads(json.dumps(pipeline))))
    explicit = any('$project' in stage or '$group' in stage for stage in pipeline)
    if explicit:
        assert wrapped == unwrapped
    else:
        columns = boundary_for(collections).output_columns(collection)
        assert wrapped == [{key: value for key, value in row.items() if key in columns} for row in unwrapped]
        assert all(list(row) == columns for row in wrapped)
    if 'NoSuchStatus' not in json.dumps(pipeline):
        assert wrapped


# ------------------------------------------------------------------ errors


def test_unknown_field_is_one_line_with_suggestion_and_published_fields_only(data):
    message = query_error('company', [{'$match': {'legal_name': 'x'}}])
    assert message == (
        "Unknown field 'legal_name' on collection 'company'. Did you mean 'legal_entity_name'? "
        f"Published fields: {_published_line('company')}"
    )
    company = published_collections()['company']
    unpublished = ({f.name for f in Company._meta.get_fields()} - set(published_fields(company)))
    assert unpublished
    words = set(re.findall(r"[A-Za-z_]+", message))
    assert not (words & unpublished), words & unpublished


@pytest.mark.parametrize('collection, pipeline, expected_start', [
    ('contact', [{'$match': {'first_name': 'Alex'}}],
     "Unknown field 'first_name' on collection 'contact'. Did you mean 'name'?"),
    ('contact', [{'$project': {'full_name': 1}}],
     "Unknown field 'full_name' on collection 'contact'. Did you mean 'name'?"),
    ('company', [{'$match': {'branch_number': '00001'}}],
     "Unknown field 'branch_number' on collection 'company'. Did you mean 'branch'?"),
    ('invoice', [{'$sort': {'invoice_date': -1}}],
     "Unknown field 'invoice_date' on collection 'invoice'. Did you mean 'issue_date'?"),
    ('opportunity', [{'$group': {'_id': None, 'total': {'$sum': '$value'}}}],
     "Unknown field 'value' on collection 'opportunity'. Did you mean 'expected_value'?"),
    ('quote', [{'$match': {'customer_contact_email': 'alex@example.test'}}],
     "Unknown field 'customer_contact_email' on collection 'quote'. Did you mean 'contact'?"),
    ('contract', [{'$project': {'pdf_url': 1}}],
     "Unknown field 'pdf_url' on collection 'contract'. Hint: no stored PDF link; call generate_contract_pdf"),
    ('contract', [{'$match': {'preamble_template_name': 'Standard'}}],
     "Unknown field 'preamble_template_name' on collection 'contract'. Hint: use preamble_template with a "
     "$lookup on contracttemplate."),
    ('contract', [{'$match': {'customer_company_name': 'x'}}],
     "Unknown field 'customer_company_name' on collection 'contract'. Hint: use company with a $lookup on company."),
    ('zone', [{'$match': {'is_active': True}}],
     "Unknown field 'is_active' on collection 'zone'. Hint: zones have no active flag; use status and is_orphaned."),
    ('contract', [{'$match': {'statuss': 'Active'}}],
     "Unknown field 'statuss' on collection 'contract'. Did you mean 'status'?"),
])
def test_unknown_field_suggestions(data, collection, pipeline, expected_start):
    message = query_error(collection, pipeline)
    assert message.startswith(expected_start), message
    assert message.endswith(f"Published fields: {_published_line(collection)}")


def test_unknown_field_behind_a_lookup_names_the_joined_collection(data):
    message = query_error('contract', [
        {'$lookup': {'from': 'company', 'localField': 'company', 'foreignField': '_id', 'as': 'co'}},
        {'$project': {'contract_number': 1, 'n': '$co.legal_name'}},
    ])
    assert message.startswith(
        "Unknown field 'legal_name' on collection 'company'. Did you mean 'legal_entity_name'?")
    assert message.endswith(_published_line('company'))


def test_unknown_lookup_local_field(data):
    message = query_error('contract', [
        {'$lookup': {'from': 'company', 'localField': 'companyy', 'foreignField': '_id', 'as': 'co'}},
    ])
    assert message.startswith("Unknown field 'companyy' on collection 'contract'. Did you mean 'company'?")


@pytest.mark.parametrize('name, suggestion', [
    ('contracts', 'contract'), ('Companies', 'company'), ('opportunities', 'opportunity'),
    ('servicelocation', 'contractservicelocation'), ('contract_line_item', 'contractlineitem'),
])
def test_unknown_collection(name, suggestion):
    message = query_error(name, [])
    collections = ', '.join(published_collections())
    assert message == f"Unknown collection '{name}'. Did you mean '{suggestion}'? Collections: {collections}"


@pytest.mark.parametrize('collection, pipeline, expected', [
    ('contract', [{'$unwind': '$company'}], "Unsupported stage {'$unwind': '$company'} : please review pipeline"),
    ('contract', [{'$match': {'status': {'$foo': 1}}}], 'Unsupported operator $foo'),
    ('contract', [{'$match': {'company': {'name': 'x'}}}], 'Unknown match key: name'),
    ('contract', [{'$project': {'n': '$co.name'}}], "Unknown lookup alias 'co'"),
])
def test_other_errors_keep_their_library_text(data, collection, pipeline, expected):
    assert query_error(collection, pipeline).startswith(expected)


# ------------------------------------------------------------------ describe_collection


def test_describe_collection_matches_the_published_schema():
    described = json.loads(crm_mcp.describe_collection('Company'))
    cls = published_collections()['company']
    schema = generate_json_schema(cls.model, fields=cls.fields, exclude=cls.get_excluded_fields())
    assert described['collection'] == 'company'
    assert [f['name'] for f in described['fields']] == list(schema['$jsonSchema']['properties'])
    by_name = {f['name']: f for f in described['fields']}
    assert by_name['parent_company']['ref'] == 'company'
    assert by_name['parent_company']['type'] == 'objectId'
    assert by_name['billing_entity']['choices']
    assert by_name['legal_entity_name']['type'] == 'string'
    assert described['text_search_fields'] == sorted(cls.search_fields)
    assert described['extra_operators'] == ['$icontains', '$iexact', '$istartswith']
    assert described['extra_instructions'] == cls.extra_instructions
    assert {'name': 'legal_name', 'use': 'legal_entity_name'} in described['alias_hints']
    assert {'name': 'address', 'use': 'address_line1'} in described['alias_hints']


def test_describe_collection_refs_use_collection_names():
    described = json.loads(crm_mcp.describe_collection('task'))
    refs = {f['name']: f.get('ref') for f in described['fields']}
    assert refs['related_contact'] == 'contact'
    assert refs['related_contract'] == 'contract'
    assert refs['related_opportunity'] == 'opportunity'
    assert {'name': 'contact', 'use': 'related_contact'} in described['alias_hints']
    service_location = json.loads(crm_mcp.describe_collection('contractservicelocation'))
    assert {f['name']: f.get('ref') for f in service_location['fields']}['contract'] == 'contract'


def test_describe_collection_unknown_name_is_the_query_error():
    with pytest.raises(ValueError) as caught:
        crm_mcp.describe_collection('contracts')
    collections = ', '.join(published_collections())
    assert str(caught.value) == f"Unknown collection 'contracts'. Did you mean 'contract'? Collections: {collections}"


def test_describe_collection_is_a_registered_tool():
    content = _content(async_to_sync(mcp_server.call_tool)('describe_collection', {'name': 'zone'}))
    described = json.loads(content[0].text)
    assert described['collection'] == 'zone'
    assert {'status', 'platform', 'is_orphaned'} <= {f['name'] for f in described['fields']}
