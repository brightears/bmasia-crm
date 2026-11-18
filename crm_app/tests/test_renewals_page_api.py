"""The Renewals page API (/api/v1/renewals/) and the Renewal Book it builds on.

Fixtures are invented. Companies are created without a music-service account id
so no post-save signal calls an outside API.
"""
import json
from datetime import date
from decimal import Decimal
from itertools import count

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from crm_app.mcp import renewal_book as mcp_renewal_book
from crm_app.models import Company, Contract, ContractServiceLocation, Invoice, Opportunity, User
from crm_app.services.renewal_book_service import build_renewal_book
from crm_app.services.renewals_page_service import build_renewals_view

TODAY = date(2026, 11, 18)
TH = 'BMAsia (Thailand) Co., Ltd.'
HK = 'BMAsia Limited'
_numbers = count(1)


def company(name, entity=HK, **extra):
    return Company.objects.create(name=name, country='Thailand', billing_entity=entity, **extra)


def contract(co, end, *, status='Active', start=None, value='1200.00', currency='USD', **extra):
    n = next(_numbers)
    prefix = 'TH' if co.billing_entity == TH else 'HK'
    return Contract.objects.create(
        company=co,
        contract_number=extra.pop('contract_number', f'{prefix}-CT99{n:03d}'),
        contract_type='Annual',
        status=status,
        start_date=start or date(end.year - 1, end.month, 1),
        end_date=end,
        value=Decimal(value),
        currency=currency,
        **extra,
    )


def invoice(c, status, amount='1200.00'):
    n = next(_numbers)
    return Invoice.objects.create(
        company=c.company, contract=c, invoice_number=f'INV-T{n:04d}', status=status,
        issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
        amount=Decimal(amount), total_amount=Decimal(amount), currency=c.currency,
    )


@pytest.fixture
def client():
    user = User.objects.create_user(username='renewals.tester', password='not-a-real-password', role='Admin')
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def rows_by_number(data):
    return {r['contract_number']: r for r in data['rows']}


# ---------------------------------------------------------------------------
# The Renewal Book stays as it is (agents read it)
# ---------------------------------------------------------------------------

BOOK_KEYS = {'year', 'month', 'month_label', 'currency', 'count', 'totals_by_product', 'totals_by_status', 'rows'}
BOOK_ROW_KEYS = {
    'contract_id', 'company_id', 'version', 'updated_at', 'contract_number', 'corporate_group', 'company',
    'country', 'end_date', 'zones', 'zones_source', 'value', 'currency', 'product', 'lifecycle_type', 'status',
    'cancelled', 'auto_renew', 'billing_frequency', 'successor_contract', 'successor_status', 'invoices_paid',
    'outstanding_amount',
}


def test_mcp_renewal_book_output_shape_is_unchanged():
    term = contract(company('Shape Pin Hotel'), date(2026, 10, 31))
    contract(term.company, date(2027, 10, 31), status='Sent', start=date(2026, 11, 1), renewed_from=term)
    body = json.loads(mcp_renewal_book(2026, 10, 'USD'))
    assert set(body) == BOOK_KEYS
    assert set(body['rows'][0]) == BOOK_ROW_KEYS
    assert body['rows'][0]['successor_status'] == 'Sent'
    assert set(build_renewal_book(2026, 10)['rows'][0]) == BOOK_ROW_KEYS


def test_page_rows_carry_the_renewal_book_row_unchanged(client):
    th = company('Agree Resort', TH, contracted_zone_count=4)
    a = contract(th, date(2026, 11, 30), currency='THB', value='108000.00')
    ContractServiceLocation.objects.create(contract=a, location_name='Lobby', platform='beatbreeze')
    ContractServiceLocation.objects.create(contract=a, location_name='Pool', platform='beatbreeze')
    b = contract(company('Agree Hotel'), date(2026, 11, 15))
    contract(b.company, date(2027, 11, 15), status='Active', start=date(2026, 11, 16), renewed_from=b)
    contract(company('Draft Only'), date(2026, 11, 20), status='Draft', contract_number='DRAFT-9001')

    book = build_renewal_book(2026, 11)
    page = client.get('/api/v1/renewals/?year=2026&month=11').json()
    assert page['count'] == book['count'] == 2
    by_number = rows_by_number(page)
    for book_row in book['rows']:
        row = by_number[book_row['contract_number']]
        assert {k: row[k] for k in book_row} == book_row
    assert by_number[a.contract_number]['zones'] == 2
    assert by_number[a.contract_number]['zones_source'] == 'service_locations'


# ---------------------------------------------------------------------------
# Month view
# ---------------------------------------------------------------------------

def test_month_view_states_successor_value_change_and_order(client):
    hk = company('Month Hotel One')
    ended = contract(hk, date(2026, 11, 2))                          # ended, nothing sent -> attention
    soon = contract(company('Month Hotel Two'), date(2026, 11, 30))  # ends in 12 days, nothing sent -> attention
    sent = contract(company('Month Hotel Three'), date(2026, 11, 25))
    contract(sent.company, date(2027, 11, 25), status='Sent', start=date(2026, 11, 26), renewed_from=sent)
    paid = contract(company('Month Hotel Four'), date(2026, 11, 10), status='Renewed', value='1000.00')
    renewal = contract(paid.company, date(2027, 11, 10), start=date(2026, 11, 11), value='1100.00',
                       renewed_from=paid)
    invoice(renewal, 'Paid', '1100.00')
    auto = contract(company('Month Hotel Five'), date(2026, 11, 5), auto_renew=True)
    gone = contract(company('Month Hotel Six'), date(2026, 11, 3), status='Cancelled')

    data = build_renewals_view(year=2026, month=11, today=TODAY)
    rows = rows_by_number(data)
    assert rows[ended.contract_number]['renewal']['state'] == 'not_started'
    assert rows[ended.contract_number]['renewal']['attention'] == 'ended_nothing_sent'
    assert rows[ended.contract_number]['days_from_end'] == 16
    assert rows[soon.contract_number]['renewal']['attention'] == 'ending_soon_nothing_sent'
    assert rows[soon.contract_number]['days_from_end'] == -12
    assert rows[sent.contract_number]['renewal']['state'] == 'sent'
    assert rows[sent.contract_number]['renewal']['attention'] is None
    paid_row = rows[paid.contract_number]['renewal']
    assert paid_row['state'] == 'paid' and paid_row['label'] == 'Paid'
    assert paid_row['successor']['contract_number'] == renewal.contract_number
    assert paid_row['successor']['invoice_state'] == 'paid'
    assert paid_row['value_change'] == 100.0 and paid_row['value_change_basis'] == 'term'
    assert rows[auto.contract_number]['renewal']['state'] == 'auto_renews'
    assert rows[gone.contract_number]['renewal']['state'] == 'lost'

    order = [r['contract_number'] for r in data['rows']]
    # needs action first (by end date), then the rest by end date
    assert order == [ended.contract_number, soon.contract_number, gone.contract_number,
                     auto.contract_number, paid.contract_number, sent.contract_number]


def test_successor_invoices_decide_not_the_terms_own(client):
    term = contract(company('Invoice Source Hotel'), date(2026, 11, 20))
    invoice(term, 'Paid')  # the current term's own invoice: not evidence of a renewal
    row = build_renewals_view(year=2026, month=11, today=TODAY)['rows'][0]
    assert row['renewal']['state'] == 'not_started'
    assert row['invoices_paid'] is True  # the Renewal Book field keeps its meaning

    renewal = contract(term.company, date(2027, 11, 20), status='Sent', start=date(2026, 11, 21), renewed_from=term)
    invoice(renewal, 'Sent')
    row = build_renewals_view(year=2026, month=11, today=TODAY)['rows'][0]
    assert row['renewal']['state'] == 'invoiced'


def test_several_successors_and_addons(client):
    term = contract(company('Several Hotel'), date(2026, 11, 20))
    dead = contract(term.company, date(2027, 11, 20), status='Cancelled', start=date(2026, 12, 1), renewed_from=term)
    live = contract(term.company, date(2027, 11, 20), status='Draft', start=date(2026, 11, 21), renewed_from=term,
                    contract_number='DRAFT-9101')
    addon = contract(term.company, date(2027, 11, 20), status='Active', start=date(2026, 11, 21), renewed_from=term,
                     lifecycle_type='addon')
    row = build_renewals_view(year=2026, month=11, today=TODAY)['rows'][0]
    assert row['renewal']['state'] == 'drafted'
    assert row['renewal']['successor']['contract_number'] == live.contract_number
    assert {o['contract_number'] for o in row['renewal']['other_linked']} == {dead.contract_number,
                                                                               addon.contract_number}


def test_multi_year_term_value_change_is_per_year(client):
    term = contract(company('Three Year Hotel'), date(2026, 12, 31), start=date(2024, 1, 1), value='36000.00')
    contract(term.company, date(2027, 12, 31), start=date(2027, 1, 1), value='13200.00', renewed_from=term)
    row = build_renewals_view(year=2026, month=12, today=TODAY)['rows'][0]
    assert row['term_months'] == 36
    assert row['renewal']['value_change'] == 1200.0
    assert row['renewal']['value_change_basis'] == 'per_year'


def test_value_change_is_never_across_currencies(client):
    term = contract(company('Currency Switch Hotel'), date(2026, 11, 30), currency='USD')
    contract(term.company, date(2027, 11, 30), start=date(2026, 12, 1), currency='THB', value='40000.00',
             renewed_from=term)
    row = build_renewals_view(year=2026, month=11, today=TODAY)['rows'][0]
    assert row['renewal']['successor']['currency'] == 'THB'
    assert row['renewal']['value_change'] is None


def test_entity_filter_uses_the_contracts_own_issuer_first(client):
    th = company('Entity Thai Resort', TH)
    a = contract(th, date(2026, 11, 30), currency='THB')
    b = contract(company('Entity HK Hotel'), date(2026, 11, 30))
    c = contract(company('Entity Override Hotel'), date(2026, 11, 29), billing_entity=TH, currency='THB')
    th_rows = rows_by_number(client.get('/api/v1/renewals/?year=2026&month=11&entity=th').json())
    hk_rows = rows_by_number(client.get('/api/v1/renewals/?year=2026&month=11&entity=hk').json())
    assert set(th_rows) == {a.contract_number, c.contract_number}
    assert set(hk_rows) == {b.contract_number}
    assert th_rows[c.contract_number]['entity'] == 'th'


def test_owner_from_opportunity_then_bmasia_contact(client):
    owner = User.objects.create_user(username='owner.one', first_name='Avery', last_name='Stone', role='Sales')
    co = company('Owner Hotel')
    opp = Opportunity.objects.create(company=co, name='Owner renewal', owner=owner)
    a = contract(co, date(2026, 11, 30), opportunity=opp)
    b = contract(company('Contact Hotel'), date(2026, 11, 29), bmasia_contact_name='Robin Vale')
    c = contract(company('Nobody Hotel'), date(2026, 11, 28))
    rows = rows_by_number(build_renewals_view(year=2026, month=11, today=TODAY))
    assert (rows[a.contract_number]['owner'], rows[a.contract_number]['owner_source']) == ('Avery Stone',
                                                                                         'opportunity_owner')
    assert (rows[b.contract_number]['owner'], rows[b.contract_number]['owner_source']) == ('Robin Vale',
                                                                                         'bmasia_contact')
    assert rows[c.contract_number]['owner'] is None


# ---------------------------------------------------------------------------
# Strip, open view, parameters, auth, cost
# ---------------------------------------------------------------------------

def test_month_strip_counts_the_whole_year(client):
    contract(company('Strip A'), date(2026, 1, 31))
    contract(company('Strip B'), date(2026, 11, 2))           # attention
    b2 = contract(company('Strip C'), date(2026, 11, 20))
    contract(b2.company, date(2027, 11, 20), status='Active', start=date(2026, 11, 21), renewed_from=b2)
    contract(company('Strip D'), date(2027, 1, 31))          # other year
    data = build_renewals_view(year=2026, month=11, today=TODAY)
    months = {m['month']: m for m in data['months']}
    assert len(data['months']) == 12
    assert months[1]['count'] == 1 and months[1]['attention'] == 1  # ended long ago, nothing sent
    assert months[11]['count'] == 2 and months[11]['attention'] == 1 and months[11]['renewed'] == 1
    assert months[12]['count'] == 0


def test_open_view_lists_open_and_attention_rows_across_months(client):
    old_open = contract(company('Open Old'), date(2026, 2, 28))
    renewed = contract(company('Open Renewed'), date(2026, 5, 31))
    contract(renewed.company, date(2027, 5, 31), start=date(2026, 6, 1), renewed_from=renewed)
    future = contract(company('Open Future'), date(2027, 3, 31))
    too_old = contract(company('Open Too Old'), date(2025, 10, 31))
    lost = contract(company('Open Lost'), date(2026, 12, 31), status='Cancelled')
    data = build_renewals_view(year=2026, view='open', today=TODAY)
    assert data['window'] == {'start': '2025-11-01', 'end': '2027-05-31'}
    assert client.get('/api/v1/renewals/?view=open&year=2026').status_code == 200
    numbers = {r['contract_number'] for r in data['rows']}
    assert old_open.contract_number in numbers and future.contract_number in numbers
    assert renewed.contract_number not in numbers and lost.contract_number not in numbers
    assert too_old.contract_number not in numbers
    assert data['view'] == 'open' and data['month'] is None


@pytest.mark.parametrize('query', [
    'year=2026&month=13', 'year=2026&month=x', 'year=abc&month=1', 'year=2026&month=1&entity=sg',
    'year=2026&view=everything', 'year=1999&month=1',
])
def test_bad_parameters_are_refused(client, query):
    response = client.get(f'/api/v1/renewals/?{query}')
    assert response.status_code == 400
    assert 'error' in response.json()


def test_signed_in_users_only():
    assert APIClient().get('/api/v1/renewals/?year=2026&month=11').status_code == 401


def test_read_only():
    user = User.objects.create_user(username='renewals.writer', password='not-a-real-password', role='Admin')
    api = APIClient()
    api.force_authenticate(user=user)
    for method in (api.post, api.put, api.patch, api.delete):
        assert method('/api/v1/renewals/', {}).status_code == 405


def _queries_for(n):
    for i in range(n):
        term = contract(company(f'Cost Hotel {n}-{i}'), date(2026, 11, 10 + i % 15))
        ContractServiceLocation.objects.create(contract=term, location_name='Lobby')
        renewal = contract(term.company, date(2027, 11, 10), start=date(2026, 11, 26), renewed_from=term)
        invoice(renewal, 'Sent')
    with CaptureQueriesContext(connection) as ctx:
        build_renewals_view(year=2026, month=11, today=TODAY)
    return len(ctx.captured_queries)


def test_query_count_does_not_grow_with_rows():
    few = _queries_for(2)
    many = _queries_for(10)
    assert few == many
    assert many <= 8
