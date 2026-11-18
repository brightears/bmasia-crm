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
from crm_app.models import AuditLog, Company, Contract, ContractServiceLocation, Invoice, Opportunity, User
from crm_app.services.renewal_book_service import build_renewal_book
from crm_app.services.renewals_page_service import BOOK_RENEWAL_FIELDS, build_renewals_view

TODAY = date(2026, 11, 18)
TH = 'BMAsia (Thailand) Co., Ltd.'
HK = 'BMAsia Limited'
_numbers = count(1)


def company(name, entity=HK, **extra):
    return Company.objects.create(name=name, country='Thailand', billing_entity=entity, **extra)


def contract(co, end, *, status='Active', start=None, value='1200.00', currency='USD', **extra):
    n = next(_numbers)
    prefix = 'TH' if co.billing_entity == TH else 'HK'
    if start is None:
        nxt = date.fromordinal(end.toordinal() + 1)
        start = date(nxt.year - 1, nxt.month, nxt.day)
    return Contract.objects.create(
        company=co,
        contract_number=extra.pop('contract_number', f'{prefix}-CT99{n:03d}'),
        contract_type='Annual',
        status=status,
        start_date=start,
        end_date=end,
        value=Decimal(value),
        currency=currency,
        **extra,
    )


def renewal_of(term, *, status='Active', months=12, start=None, **extra):
    start = start or date.fromordinal(term.end_date.toordinal() + 1)
    end = date(start.year + months // 12, start.month, 1)
    end = date.fromordinal(date(end.year, end.month, start.day).toordinal() - 1)
    extra.setdefault('value', str(term.value))
    extra.setdefault('currency', term.currency)
    return contract(term.company, end, status=status, start=start, renewed_from=term, **extra)


def invoice(c, status, amount='1200.00', currency=None):
    n = next(_numbers)
    return Invoice.objects.create(
        company=c.company, contract=c, invoice_number=f'INV-T{n:04d}', status=status,
        issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1),
        amount=Decimal(amount), total_amount=Decimal(amount), currency=currency or c.currency,
    )


@pytest.fixture
def client():
    user = User.objects.create_user(username='renewals.tester', password='not-a-real-password', role='Admin')
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def rows_by_number(data):
    return {r['contract_number']: r for r in data['rows']}


def view(**kw):
    kw.setdefault('today', TODAY)
    return build_renewals_view(**kw)


def one_row(**kw):
    rows = view(**kw)['rows']
    assert len(rows) == 1, [r['contract_number'] for r in rows]
    return rows[0]


# ---------------------------------------------------------------------------
# The Renewal Book stays as it is (agents read it); the page gives one answer
# ---------------------------------------------------------------------------

BOOK_KEYS = {'year', 'month', 'month_label', 'currency', 'count', 'totals_by_product', 'totals_by_status', 'rows'}
BOOK_ROW_KEYS = {
    'contract_id', 'company_id', 'version', 'updated_at', 'contract_number', 'corporate_group', 'company',
    'country', 'end_date', 'zones', 'zones_source', 'value', 'currency', 'product', 'lifecycle_type', 'status',
    'cancelled', 'auto_renew', 'billing_frequency', 'successor_contract', 'successor_status', 'invoices_paid',
    'outstanding_amount',
}


def test_mcp_renewal_book_output_shape_is_unchanged():
    term = contract(company('Shape Pin Hotel'), date(2026, 10, 30))
    renewal_of(term, status='Sent')
    body = json.loads(mcp_renewal_book(2026, 10, 'USD'))
    assert set(body) == BOOK_KEYS
    assert set(body['rows'][0]) == BOOK_ROW_KEYS
    assert body['rows'][0]['successor_status'] == 'Sent'
    assert set(build_renewal_book(2026, 10)['rows'][0]) == BOOK_ROW_KEYS


def test_page_rows_carry_the_book_row_with_its_renewal_view_under_book(client):
    th = company('Agree Resort', TH, contracted_zone_count=4)
    a = contract(th, date(2026, 11, 20), currency='THB', value='108000.00')
    ContractServiceLocation.objects.create(contract=a, location_name='Lobby', platform='beatbreeze')
    ContractServiceLocation.objects.create(contract=a, location_name='Pool', platform='beatbreeze')
    b = contract(company('Agree Hotel'), date(2026, 11, 15))
    renewal_of(b)
    contract(company('Draft Only'), date(2026, 11, 21), status='Draft', contract_number='DRAFT-9001')

    book = build_renewal_book(2026, 11)
    page = client.get('/api/v1/renewals/?year=2026&month=11&basis=calendar').json()
    assert page['count'] == book['count'] == 2
    by_number = rows_by_number(page)
    for book_row in book['rows']:
        row = by_number[book_row['contract_number']]
        for key in BOOK_RENEWAL_FIELDS:
            assert key not in row  # one answer per row: renewal
        assert row['book'] == {k: book_row[k] for k in BOOK_RENEWAL_FIELDS}
        assert {k: row[k] for k in book_row if k not in BOOK_RENEWAL_FIELDS} == {
            k: v for k, v in book_row.items() if k not in BOOK_RENEWAL_FIELDS}
    assert by_number[a.contract_number]['zones'] == 2
    assert by_number[a.contract_number]['product'] == 'Other'
    assert (by_number[a.contract_number]['product_display'],
            by_number[a.contract_number]['product_source']) == ('Beat Breeze', 'service_locations')


def test_book_and_page_successors_differ_but_the_page_row_has_one_answer():
    term = contract(company('Two Answers Hotel'), date(2026, 11, 15), status='Renewed')
    live = renewal_of(term, start=date(2026, 11, 16))
    dead = renewal_of(term, status='Cancelled', start=date(2026, 12, 1))
    row = one_row(year=2026, month=11)
    assert row['book']['successor_contract'] == dead.contract_number  # the book: latest start
    assert row['renewal']['successor']['contract_number'] == live.contract_number
    assert row['renewal']['state'] == 'signed'


# ---------------------------------------------------------------------------
# Month windows
# ---------------------------------------------------------------------------

def test_funnel_month_is_the_default_and_calendar_is_a_switch():
    oct31 = contract(company('Ends Oct 31'), date(2026, 10, 31))
    nov15 = contract(company('Ends Nov 15'), date(2026, 11, 15))
    nov30 = contract(company('Ends Nov 30'), date(2026, 11, 30))
    funnel = view(year=2026, month=11)
    assert set(rows_by_number(funnel)) == {oct31.contract_number, nov15.contract_number}
    assert funnel['basis'] == 'funnel'
    assert funnel['window'] == {'start': '2026-10-31', 'end': '2026-11-29'}
    calendar = view(year=2026, month=11, basis='calendar')
    assert set(rows_by_number(calendar)) == {nov15.contract_number, nov30.contract_number}
    assert calendar['window'] == {'start': '2026-11-01', 'end': '2026-11-30'}
    assert set(rows_by_number(view(year=2026, month=12))) == {nov30.contract_number}


def test_strip_follows_the_basis_across_the_year_boundary():
    contract(company('Ends Dec 31 2025'), date(2025, 12, 31))   # funnel: Jan 2026
    contract(company('Ends Dec 31 2026'), date(2026, 12, 31))   # funnel: Jan 2027
    contract(company('Ends Feb 27 2026'), date(2026, 2, 27))
    contract(company('Ends Feb 28 2026'), date(2026, 2, 28))   # funnel: Mar 2026
    funnel = {m['month']: m['count'] for m in view(year=2026, month=1)['months']}
    assert (funnel[1], funnel[2], funnel[3], funnel[12]) == (1, 1, 1, 0)
    calendar = {m['month']: m['count'] for m in view(year=2026, month=1, basis='calendar')['months']}
    assert (calendar[1], calendar[2], calendar[3], calendar[12]) == (0, 2, 0, 1)


# ---------------------------------------------------------------------------
# States on real records
# ---------------------------------------------------------------------------

def test_month_view_states_successor_value_change_and_order():
    ended = contract(company('Month Hotel One'), date(2026, 11, 2))
    soon = contract(company('Month Hotel Two'), date(2026, 11, 28))
    sent = contract(company('Month Hotel Three'), date(2026, 11, 25))
    renewal_of(sent, status='Sent')
    paid = contract(company('Month Hotel Four'), date(2026, 11, 10), status='Renewed', value='1000.00')
    paid_renewal = renewal_of(paid, value='1100.00')
    invoice(paid_renewal, 'Paid', '1100.00')
    auto = contract(company('Month Hotel Five'), date(2026, 11, 25), auto_renew=True)
    gone = contract(company('Month Hotel Six'), date(2026, 11, 3), status='Cancelled')

    data = view(year=2026, month=11)
    rows = rows_by_number(data)
    assert rows[ended.contract_number]['renewal']['attention'] == 'ended_nothing_sent'
    assert rows[ended.contract_number]['days_from_end'] == 16
    assert rows[soon.contract_number]['renewal']['attention'] == 'ending_soon_nothing_sent'
    assert rows[sent.contract_number]['renewal']['state'] == 'sent'
    paid_row = rows[paid.contract_number]['renewal']
    assert paid_row['state'] == 'paid' and paid_row['successor']['invoice_state'] == 'paid'
    assert paid_row['value_change'] == 100.0 and paid_row['value_change_basis'] == 'term'
    assert rows[auto.contract_number]['renewal']['state'] == 'auto_renews'
    assert rows[gone.contract_number]['renewal']['state'] == 'lost'
    order = [r['contract_number'] for r in data['rows']]
    assert order == [ended.contract_number, soon.contract_number, gone.contract_number,
                     paid.contract_number, auto.contract_number, sent.contract_number]


def test_ended_auto_renew_term_needs_attention_and_is_in_all_open():
    term = contract(company('Auto Ended Hotel'), date(2026, 8, 30), auto_renew=True)
    row = one_row(year=2026, month=8)
    assert row['renewal']['state'] == 'auto_unconfirmed'
    assert row['renewal']['attention'] == 'auto_renew_ended'
    assert row['renewal']['summary_bucket'] == 'open' and row['renewal']['in_rate'] is True
    assert term.contract_number in rows_by_number(view(year=2026, view='open'))
    future = contract(company('Auto Future Hotel'), date(2026, 12, 15), auto_renew=True)
    assert one_row(year=2026, month=12)['renewal']['state'] == 'auto_renews'
    assert future.contract_number not in rows_by_number(view(year=2026, view='open'))


def test_successor_invoices_decide_not_the_terms_own():
    term = contract(company('Invoice Source Hotel'), date(2026, 11, 20))
    invoice(term, 'Paid')
    row = one_row(year=2026, month=11)
    assert row['renewal']['state'] == 'not_started'
    assert row['book']['invoices_paid'] is True
    renewal = renewal_of(term, status='Sent')
    invoice(renewal, 'Sent')
    assert one_row(year=2026, month=11)['renewal']['state'] == 'invoiced'


def test_one_paid_quarterly_instalment_is_part_paid_and_refund_needs_attention():
    term = contract(company('Quarterly Hotel'), date(2026, 10, 31))
    renewal = renewal_of(term, billing_frequency='Quarterly')
    invoice(renewal, 'Paid', '300.00')
    # Renewal started 1 Nov; by 18 Nov one quarter is due: paid.
    assert one_row(year=2026, month=11)['renewal']['state'] == 'paid'
    late = date(2027, 2, 15)  # second quarter due, still one paid
    assert one_row(year=2026, month=11, today=late)['renewal']['state'] == 'part_paid'
    invoice(renewal, 'Refunded', '300.00')
    row = one_row(year=2026, month=11)
    assert row['renewal']['attention'] == 'invoice_refunded'


def test_zero_value_paid_invoice_earns_nothing():
    term = contract(company('Zero Invoice Hotel'), date(2026, 11, 20))
    renewal = renewal_of(term, status='Sent')
    invoice(renewal, 'Paid', '0.00')
    assert one_row(year=2026, month=11)['renewal']['state'] == 'sent'


def test_issued_invoice_outranks_a_sent_renewal_without_one():
    term = contract(company('Rank Hotel'), date(2026, 11, 20))
    renewal_of(term, status='Sent', start=date(2026, 11, 21))
    draft = renewal_of(term, status='Draft', start=date(2026, 11, 22), contract_number='DRAFT-9301')
    invoice(draft, 'Sent')
    row = one_row(year=2026, month=11)
    assert (row['renewal']['state'], row['renewal']['successor']['contract_number']) == ('invoiced', 'DRAFT-9301')


def test_several_successors_mid_term_links_and_addons():
    term = contract(company('Several Hotel'), date(2026, 11, 20))
    dead = renewal_of(term, status='Cancelled', start=date(2026, 12, 1))
    live = renewal_of(term, status='Draft', contract_number='DRAFT-9101')
    addon = renewal_of(term, start=date(2026, 3, 1))  # unmarked, starts mid-term
    row = one_row(year=2026, month=11)
    assert row['renewal']['state'] == 'drafted'
    assert row['renewal']['successor']['contract_number'] == live.contract_number
    links = {o['contract_number']: o['link'] for o in row['renewal']['other_linked']}
    assert links == {dead.contract_number: 'renewal', addon.contract_number: 'mid_term'}


def test_unmarked_addon_alone_is_not_the_renewal_and_is_marked_as_addon_term():
    term = contract(company('Addon Hotel'), date(2026, 11, 20))
    addon = renewal_of(term, start=date(2026, 5, 1), months=12)  # ends 30 Apr 2027
    row = one_row(year=2026, month=11)
    assert row['renewal']['state'] == 'not_started'
    addon_row = rows_by_number(view(year=2027, month=4, basis='calendar'))[addon.contract_number]
    assert addon_row['is_addon'] is True
    marked = contract(company('Marked Addon Hotel'), date(2026, 11, 25), lifecycle_type='addon')
    assert rows_by_number(view(year=2026, month=11))[marked.contract_number]['is_addon'] is True


def test_multi_year_renewal_gets_no_value_change_figure():
    term = contract(company('Three Year Hotel'), date(2026, 11, 29), start=date(2023, 11, 30), value='12000.00')
    renewal_of(term, value='12000.00')
    row = one_row(year=2026, month=11)
    assert row['term_months'] == 36
    assert row['renewal']['value_change'] is None
    assert row['renewal']['value_change_basis'] == 'different_length'


def test_value_change_is_never_across_currencies():
    term = contract(company('Currency Switch Hotel'), date(2026, 11, 20), currency='USD')
    renewal_of(term, currency='THB', value='40000.00')
    row = one_row(year=2026, month=11)
    assert row['renewal']['successor']['currency'] == 'THB'
    assert row['renewal']['value_change'] is None


def test_late_link_counts_as_the_renewal_and_mid_term_link_is_named():
    placeholder = contract(company('Late Link Hotel'), date(2025, 12, 31), start=date(2025, 1, 1), status='Renewed')
    real = renewal_of(placeholder, start=date(2026, 8, 1))
    row = one_row(year=2026, month=1)
    assert row['renewal']['state'] == 'signed'
    assert row['renewal']['successor']['contract_number'] == real.contract_number
    assert row['renewal']['successor']['link'] == 'late'
    term = contract(company('Mid Link Hotel'), date(2026, 11, 20), status='Renewed')
    renewal_of(term, start=date(2026, 4, 1))
    rows = rows_by_number(view(year=2026, month=11))
    assert rows[term.contract_number]['renewal']['attention'] == 'renewed_link_mid_term'


def test_successor_on_another_company_record_is_flagged():
    term = contract(company('Twin A Hotel'), date(2026, 11, 20))
    contract(company('Twin B Hotel'), date(2027, 11, 20), start=date(2026, 11, 21), renewed_from=term)
    assert one_row(year=2026, month=11)['renewal']['successor']['other_company'] is True


# ---------------------------------------------------------------------------
# Rows that are not real terms
# ---------------------------------------------------------------------------

def test_sent_never_activated_term_is_flagged_and_not_counted_as_lost():
    offer = contract(company('Offer Hotel'), date(2026, 11, 20), status='Sent')
    row = one_row(year=2026, month=11)
    assert row['never_activated'] is True
    assert row['renewal']['in_rate'] is False
    renewal_of(offer, status='Cancelled')
    row = one_row(year=2026, month=11)
    assert row['renewal']['state'] == 'lost' and row['renewal']['summary_bucket'] == 'excluded'


def test_rule2_and_rule3_placeholders_are_recognised():
    year_one = contract(company('Year One Hotel'), date(2026, 11, 20), status='Expired',
                        notes='Placeholder record (2025-11-21 – 2026-11-20), multi-year duplicate of HK-CT99999.')
    twin = contract(company('Twin Placeholder Hotel'), date(2026, 11, 21), status='Expired')
    AuditLog.objects.create(action='UPDATE', model_name='Contract', record_id=str(twin.pk),
                            additional_data={'class': 'R3', 'op': 'mark_expired', 'evidence': 'rule 3'})
    other = contract(company('Lapsed Hotel'), date(2026, 11, 22), status='Expired')
    AuditLog.objects.create(action='UPDATE', model_name='Contract', record_id=str(other.pk),
                            additional_data={'class': 'R1', 'op': 'mark_renewed'})
    data = view(year=2026, month=11)
    rows = rows_by_number(data)
    assert rows[year_one.contract_number]['renewal']['state'] == 'placeholder'
    assert rows[twin.contract_number]['renewal']['state'] == 'placeholder'
    assert rows[twin.contract_number]['renewal']['summary_bucket'] == 'excluded'
    assert rows[twin.contract_number]['renewal']['attention'] is None
    assert rows[other.contract_number]['renewal']['state'] == 'lapsed'
    nov = data['months'][10]
    assert (nov['count'], nov['placeholders'], nov['lost']) == (1, 2, 1)


# ---------------------------------------------------------------------------
# Owner, entity
# ---------------------------------------------------------------------------

def test_entity_filter_uses_the_contracts_own_issuer_first(client):
    a = contract(company('Entity Thai Resort', TH), date(2026, 11, 20), currency='THB')
    b = contract(company('Entity HK Hotel'), date(2026, 11, 20))
    c = contract(company('Entity Override Hotel'), date(2026, 11, 19), billing_entity=TH, currency='THB')
    th_rows = rows_by_number(client.get('/api/v1/renewals/?year=2026&month=11&entity=th').json())
    hk_rows = rows_by_number(client.get('/api/v1/renewals/?year=2026&month=11&entity=hk').json())
    assert set(th_rows) == {a.contract_number, c.contract_number}
    assert set(hk_rows) == {b.contract_number}
    assert th_rows[c.contract_number]['entity'] == 'th'


def test_owner_from_opportunity_then_bmasia_contact():
    owner = User.objects.create_user(username='owner.one', first_name='Avery', last_name='Stone', role='Sales')
    co = company('Owner Hotel')
    opp = Opportunity.objects.create(company=co, name='Owner renewal', owner=owner)
    a = contract(co, date(2026, 11, 20), opportunity=opp)
    b = contract(company('Contact Hotel'), date(2026, 11, 19), bmasia_contact_name='Robin Vale')
    c = contract(company('Nobody Hotel'), date(2026, 11, 18))
    rows = rows_by_number(view(year=2026, month=11))
    assert (rows[a.contract_number]['owner'], rows[a.contract_number]['owner_source']) == ('Avery Stone',
                                                                                         'opportunity_owner')
    assert (rows[b.contract_number]['owner'], rows[b.contract_number]['owner_source']) == ('Robin Vale',
                                                                                         'bmasia_contact')
    assert rows[c.contract_number]['owner'] is None


# ---------------------------------------------------------------------------
# Strip, open view, parameters, auth, cost
# ---------------------------------------------------------------------------

def test_month_strip_counts():
    contract(company('Strip A'), date(2026, 1, 30))                             # ended, nothing sent
    contract(company('Strip B'), date(2026, 11, 2))                             # attention
    b2 = contract(company('Strip C'), date(2026, 11, 20))
    renewal_of(b2)
    contract(company('Strip D'), date(2026, 11, 25), auto_renew=True)           # auto, not ended
    contract(company('Strip E'), date(2027, 1, 15))                             # other year
    data = view(year=2026, month=11)
    months = {m['month']: m for m in data['months']}
    assert len(data['months']) == 12
    assert months[1]['count'] == 1 and months[1]['attention'] == 1
    nov = months[11]
    assert (nov['count'], nov['attention'], nov['renewed'], nov['auto'], nov['open']) == (3, 1, 1, 1, 1)
    assert months[12]['count'] == 0


def test_open_view_lists_open_and_attention_rows_across_months():
    old_open = contract(company('Open Old'), date(2026, 2, 27))
    renewed = contract(company('Open Renewed'), date(2026, 5, 30))
    renewal_of(renewed)
    unlinked = contract(company('Open Unlinked'), date(2026, 6, 15), status='Renewed')  # attention only
    future = contract(company('Open Future'), date(2027, 3, 15))
    too_old = contract(company('Open Too Old'), date(2025, 10, 15))
    lost = contract(company('Open Lost'), date(2026, 12, 15), status='Cancelled')
    data = view(year=2026, view='open')
    assert data['window'] == {'start': '2025-10-31', 'end': '2027-05-30'}
    numbers = set(rows_by_number(data))
    assert {old_open.contract_number, future.contract_number, unlinked.contract_number} <= numbers
    assert not {renewed.contract_number, lost.contract_number, too_old.contract_number} & numbers
    assert data['view'] == 'open' and data['month'] is None


@pytest.mark.parametrize('query', [
    'year=2026&month=13', 'year=2026&month=x', 'year=abc&month=1', 'year=2026&month=1&entity=sg',
    'year=2026&view=everything', 'year=1999&month=1', 'year=2026&month=1&basis=weekly',
    'year=2026&view=open&month=x',
])
def test_bad_parameters_are_refused(client, query):
    response = client.get(f'/api/v1/renewals/?{query}')
    assert response.status_code == 400
    assert 'error' in response.json()


def test_response_is_private_and_not_stored(client):
    response = client.get('/api/v1/renewals/?year=2026&month=11')
    assert response.status_code == 200
    assert response['Cache-Control'] == 'private, no-store'


def test_signed_in_users_only():
    assert APIClient().get('/api/v1/renewals/?year=2026&month=11').status_code == 401


def test_read_only():
    user = User.objects.create_user(username='renewals.writer', password='not-a-real-password', role='Admin')
    api = APIClient()
    api.force_authenticate(user=user)
    for method in (api.post, api.put, api.patch, api.delete):
        assert method('/api/v1/renewals/', {}).status_code == 405


def _queries_for(n, offset):
    for i in range(n):
        term = contract(company(f'Cost Hotel {offset}-{i}'), date(2026, 11, 1 + i % 25))
        ContractServiceLocation.objects.create(contract=term, location_name='Lobby')
        renewal = renewal_of(term)
        invoice(renewal, 'Sent')
        contract(company(f'Cost Other Month {offset}-{i}'), date(2026, 3, 1 + i % 25))
    with CaptureQueriesContext(connection) as month_ctx:
        view(year=2026, month=11)
    with CaptureQueriesContext(connection) as open_ctx:
        view(year=2026, view='open')
    return len(month_ctx.captured_queries), len(open_ctx.captured_queries)


def test_query_count_does_not_grow_with_rows():
    few = _queries_for(2, 'a')
    many = _queries_for(10, 'b')
    assert few == many
    assert many[0] <= 13 and many[1] <= 13
