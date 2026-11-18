"""Data-quality checks (crm_app/data_quality.py): definitions at their boundaries, Bangkok
"today", fixed query counts, the API (permissions, paging, filters, CSV) and the command.

All names are invented. Companies are created without a Soundtrack account id, so the
Company post-save signal never calls the Soundtrack API.
"""
import csv
import io
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app import data_quality as dq
from crm_app.models import (
    Company, Contact, Contract, ContractServiceLocation, ContractZone, Invoice, Opportunity, Quote, Task, User, Zone,
)

# 18:30 UTC on 18 Nov is 01:30 on 19 Nov in Bangkok: the UTC date and the business date differ.
FROZEN = '2026-11-18T18:30:00+00:00'
T = date(2026, 11, 19)


@pytest.fixture(autouse=True)
def frozen_clock():
    with freeze_time(FROZEN):
        yield


def at(day, hour=0, minute=0, second=0):
    """An aware Bangkok datetime."""
    return timezone.make_aware(datetime.combine(day, time(hour, minute, second)))


_n = {'c': 0}


def company(name=None, **kw):
    _n['c'] += 1
    return Company.objects.create(name=name or f'Test Venue {_n["c"]:03d}', soundtrack_account_id='', **kw)


def contract(co, status='Active', start=None, end=None, **kw):
    end = end if end is not None else T + timedelta(days=200)
    start = start or end - timedelta(days=364)
    return Contract.objects.create(company=co, status=status, start_date=start, end_date=end,
                                   value=Decimal('108000'), currency='THB', **kw)


def location(c, name='Lobby'):
    return ContractServiceLocation.objects.create(contract=c, location_name=name, platform='soundtrack')


def zone_link(c, active=True):
    z = Zone.objects.create(company=c.company, name=f'Zone {Zone.objects.count() + 1}')
    return ContractZone.objects.create(contract=c, zone=z, start_date=c.start_date, is_active=active,
                                       end_date=None if active else c.start_date + timedelta(days=10))


def ids(check_key, **filters):
    check = dq.CHECKS_BY_KEY[check_key]
    return [r['id'] for r in check.rows(dq.Context(), dq.Filters(**filters))]


def only_row(check_key):
    rows = dq.CHECKS_BY_KEY[check_key].rows(dq.Context())
    assert len(rows) == 1, rows
    return rows[0]


def test_today_is_the_bangkok_day():
    assert dq.Context().today == T
    assert timezone.now().date() == date(2026, 11, 18)  # what a UTC-date check would wrongly use


# --- contracts --------------------------------------------------------------------------

def test_active_past_end_boundaries():
    co = company()
    ended_yesterday = contract(co, end=T - timedelta(days=1))
    contract(co, end=T)  # ends today: still running
    auto = contract(co, end=T - timedelta(days=5), auto_renew=True)
    contract(co, status='Expired', end=T - timedelta(days=10))
    contract(co, status='Renewed', end=T - timedelta(days=10))
    assert ids('contract_active_past_end') == [str(ended_yesterday.pk)]
    assert ids('contract_auto_renew_past_end') == [str(auto.pk)]
    r = only_row('contract_active_past_end')
    assert r['fact'] == 'Ended yesterday (18 Nov 2026); no renewal recorded'
    assert r['link'] == f'/contracts/{ended_yesterday.pk}'
    assert r['company_name'] == co.name
    assert (r['amount'], r['currency'], r['date']) == ('108000.00', 'THB', '2026-11-18')


def test_active_past_end_names_the_renewal_in_progress():
    co = company()
    old = contract(co, end=T - timedelta(days=23))
    contract(co, status='Sent', start=T - timedelta(days=22), end=T + timedelta(days=342), renewed_from=old)
    renewal = Contract.objects.get(renewed_from=old)
    fact = only_row('contract_active_past_end')['fact']
    assert fact == f'Ended 23 days ago (27 Oct 2026); renewal {renewal.contract_number} is Sent'


def test_ending_without_successor_window():
    today = contract(company(), end=T)
    last_day = contract(company(), end=T + timedelta(days=60))
    contract(company(), end=T + timedelta(days=61))
    contract(company(), end=T - timedelta(days=1))  # already past end: another check
    contract(company(), status='Sent', end=T + timedelta(days=10))  # not Active
    assert set(ids('contract_ending_no_successor')) == {str(today.pk), str(last_day.pk)}
    facts = [r['fact'] for r in dq.CHECKS_BY_KEY['contract_ending_no_successor'].rows(dq.Context())]
    assert facts == ['Ends today (19 Nov 2026); no renewal drafted',
                     'Ends in 60 days (18 Jan 2027); no renewal drafted']


def test_ending_successor_rules():
    soundtrack = 'soundtrack_unlimited_yearly'
    # linked renewal in any status, even Cancelled (a declined renewal is an outcome)
    a = company()
    a1 = contract(a, end=T + timedelta(days=20), service_type=soundtrack)
    contract(a, status='Cancelled', start=T + timedelta(days=21), end=T + timedelta(days=385), renewed_from=a1)
    # unlinked draft, same company, later start, same product
    b = company()
    contract(b, end=T + timedelta(days=20), service_type=soundtrack)
    contract(b, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385), service_type=soundtrack)
    # unlinked draft with unknown product counts as the renewal
    c = company()
    contract(c, end=T + timedelta(days=20), service_type=soundtrack)
    contract(c, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385))
    # unlinked draft for another product does not
    d = company()
    d1 = contract(d, end=T + timedelta(days=20), service_type=soundtrack)
    contract(d, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385),
             service_type='beat_breeze_yearly')
    # a draft that starts earlier is not a successor; an Expired later one neither; nor a
    # parallel Active contract that starts later but ends with this one
    e = company()
    e1 = contract(e, start=T - timedelta(days=300), end=T + timedelta(days=20), service_type=soundtrack)
    contract(e, status='Draft', start=T - timedelta(days=400), end=T - timedelta(days=36), service_type=soundtrack)
    contract(e, status='Expired', start=T + timedelta(days=21), end=T + timedelta(days=385), service_type=soundtrack)
    contract(e, start=T - timedelta(days=100), end=T + timedelta(days=20), service_type=soundtrack)
    # another company's draft does not count; auto-renewing contracts are included
    f = company()
    f1 = contract(f, end=T + timedelta(days=20), auto_renew=True)
    contract(company(), status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385))
    # a contract of unknown product matches any later contract of its company
    g = company(contracted_product='')
    contract(g, end=T + timedelta(days=20))
    contract(g, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385),
             service_type='beat_breeze_yearly')
    ending = set(ids('contract_ending_no_successor'))
    assert {str(d1.pk), str(e1.pk), str(f1.pk)} <= ending
    assert len(ending) == 4  # the parallel contract of e has no successor either
    f_row = [r for r in dq.CHECKS_BY_KEY['contract_ending_no_successor'].rows(dq.Context()) if r['id'] == str(f1.pk)]
    assert f_row[0]['fact'].endswith('; auto-renews')


def test_product_falls_back_to_company_product():
    bb_company = company(contracted_product='beatbreeze')
    current = contract(bb_company, end=T + timedelta(days=20))
    contract(bb_company, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385),
             service_type='soundtrack_essential_yearly')
    assert ids('contract_ending_no_successor') == [str(current.pk)]


def test_sent_unsigned_boundary():
    co = company()
    late = contract(co, status='Sent', start=T - timedelta(days=31))
    contract(co, status='Sent', start=T - timedelta(days=30))
    contract(co, status='Active', start=T - timedelta(days=100))
    assert ids('contract_sent_unsigned') == [str(late.pk)]
    late.refresh_from_db()
    assert late.sent_date is not None  # stamped by Contract.save on the UTC date
    fact = only_row('contract_sent_unsigned')['fact']
    assert fact.startswith('Term started 31 days ago (19 Oct 2026); sent ')
    Contract.objects.filter(pk=late.pk).update(sent_date=None)
    assert only_row('contract_sent_unsigned')['fact'] == \
        'Term started 31 days ago (19 Oct 2026); no sent date recorded; not signed'


def test_stale_draft_boundary_in_bangkok_time():
    co = company()
    stale = contract(co, status='Draft', start=T + timedelta(days=30))
    fresh = contract(co, status='Draft', start=T - timedelta(days=5))
    cutoff = at(T - timedelta(days=60))
    # one second before midnight Bangkok on the 61st day back: stale; at midnight of the 60th: not
    Contract.objects.filter(pk=stale.pk).update(updated_at=cutoff - timedelta(seconds=1))
    Contract.objects.filter(pk=fresh.pk).update(updated_at=cutoff)
    assert ids('contract_draft_stale') == [str(stale.pk)]
    assert only_row('contract_draft_stale')['fact'] == 'Last changed 61 days ago (19 Sep 2026)'
    Contract.objects.filter(pk=fresh.pk).update(updated_at=cutoff - timedelta(days=1))
    rows = dq.CHECKS_BY_KEY['contract_draft_stale'].rows(dq.Context())
    assert rows[0]['fact'] == 'Last changed 61 days ago (19 Sep 2026); its term start 14 Nov 2026 has passed'


def test_zone_checks_split_by_authoritative_structure():
    co = company()
    neither = contract(co)
    links_only = contract(co)
    zone_link(links_only)
    complete = contract(co)
    location(complete)
    zone_link(complete)
    locations_only = contract(co)
    location(locations_only)
    location(locations_only, 'Pool')
    closed_link = contract(co)
    location(closed_link)
    zone_link(closed_link, active=False)
    contract(co, status='Draft')  # only Active contracts are checked
    assert set(ids('contract_no_service_locations')) == {str(neither.pk), str(links_only.pk)}
    assert set(ids('contract_no_zone_links')) == {str(locations_only.pk), str(closed_link.pk)}
    facts = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['contract_no_service_locations'].rows(dq.Context())}
    assert facts[str(neither.pk)] == 'No service locations and no zone links'
    assert facts[str(links_only.pk)] == 'No service locations; 1 active zone link'
    facts = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['contract_no_zone_links'].rows(dq.Context())}
    assert facts[str(locations_only.pk)] == '2 service locations; no active zone link'


# --- companies and contacts -------------------------------------------------------------

def test_company_without_email_contact():
    missing = company('Harbour Test Hotel')
    contract(missing)
    Contact.objects.create(company=missing, name='Old Contact', email='old@example.com', is_active=False)
    Contact.objects.create(company=missing, name='No Email', email='')
    ok = company()
    contract(ok)
    Contact.objects.create(company=ok, name='Has Email', email='gm@example.com')
    no_contract = company()
    contract(no_contract, status='Expired', end=T - timedelta(days=30))
    bare = company()
    contract(bare)
    assert set(ids('company_no_email_contact')) == {str(missing.pk), str(bare.pk)}
    facts = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['company_no_email_contact'].rows(dq.Context())}
    assert facts[str(missing.pk)] == '1 Active contract; 2 contacts, none active with an email'
    assert facts[str(bare.pk)] == '1 Active contract; no contacts'
    assert ids('company_no_email_contact', company_id=str(missing.pk)) == [str(missing.pk)]


def test_contact_email_problems():
    group = company('Test Group HQ')
    venue = company('Test Group Riverside', parent_company=group)
    other = company('Unrelated Test Bistro')
    bad = Contact.objects.create(company=other, name='Typo Person', email='typo@example')
    Contact.objects.create(company=other, name='Spaced Person', email='spaced @example.com')
    Contact.objects.create(company=group, name='Regional GM', email='GM@group.example')
    Contact.objects.create(company=venue, name='Regional GM', email='gm@Group.Example')  # same group: expected
    Contact.objects.create(company=venue, name='Shared Box', email='accounts@shared.example')
    Contact.objects.create(company=other, name='Shared Box', email='Accounts@Shared.example')
    Contact.objects.create(company=other, name='Gone', email='bad@@example.com', is_active=False)
    rows = dq.CHECKS_BY_KEY['contact_email_problem'].rows(dq.Context())
    invalid = [r for r in rows if 'not a valid' in r['fact']]
    shared = [r for r in rows if r['fact'].startswith('Same email')]
    assert len(rows) == 3 and len(invalid) == 2 and len(shared) == 1
    assert sorted(r['fact'] for r in invalid) == ['Email "spaced @example.com" is not a valid address',
                                                   'Email "typo@example" is not a valid address']
    assert str(bad.pk) in {r['id'] for r in invalid}
    assert all(r['link'] == f'/companies/{other.pk}' for r in invalid)
    assert shared[0]['label'] == 'accounts@shared.example'
    assert shared[0]['fact'] == 'Same email at 2 companies: Test Group Riverside, Unrelated Test Bistro'
    assert shared[0]['link'] == f'/companies/{venue.pk}'
    assert shared[0]['related'] == [{'label': 'Unrelated Test Bistro', 'link': f'/companies/{other.pk}'}]
    # filtering by company finds a shared address from either side
    assert len(dq.CHECKS_BY_KEY['contact_email_problem'].rows(dq.Context(), dq.Filters(company_id=str(venue.pk)))) == 1
    # these records have no owner
    assert dq.CHECKS_BY_KEY['contact_email_problem'].count(dq.Context(), dq.Filters(owner_id='none')) == 3
    some_user = User.objects.create_user(username='owner.test', password='x', role='Admin')
    assert dq.CHECKS_BY_KEY['contact_email_problem'].count(dq.Context(), dq.Filters(owner_id=str(some_user.pk))) == 0


def test_shared_email_fact_wording():
    a, b = company('Alpha Test Cafe'), company('Beta Test Cafe')
    Contact.objects.create(company=a, name='Front Desk', email='desk@cafes.example')
    Contact.objects.create(company=b, name='Front Desk', email='desk@cafes.example')
    assert only_row('contact_email_problem')['fact'] == 'Same email at 2 companies: Alpha Test Cafe, Beta Test Cafe'


@pytest.mark.parametrize('a,b', [
    ('Lumen Bay Co., Ltd.', 'lumen-bay'),
    ('The Lumen Bay', 'LUMEN BAY LIMITED'),
    ('Orchid & Pine Pte. Ltd.', 'Orchid and Pine'),
    ('PT Kinara Resort Tbk', 'Kinara Resort'),
    ('บริษัท สยาม ซาวด์ จำกัด (มหาชน)', 'สยาม ซาวด์'),
    ('Ascott Test Nangang Taipei', 'Ascott Test Taipei Nangang'),
    ('AVANI Test Deira', 'Avani Test Deira Hotel'),
])
def test_normalised_names_match(a, b):
    assert dq.normalise_company_name(a) == dq.normalise_company_name(b)


@pytest.mark.parametrize('a,b', [
    ('Lumen Bay', 'Lumen Bayside'),
    ('Coralstone Mall', 'Coralstone Mall Penang'),
    ('Moonlit Garden Resort', 'Moonlit Garden Hotel'),
])
def test_normalised_names_differ(a, b):
    assert dq.normalise_company_name(a) != dq.normalise_company_name(b)


def test_lookalike_companies_one_row_per_group():
    first = company('Lumen Test Bay Co., Ltd.')
    company('lumen-test-bay')
    company('The Lumen Test Bay')
    company('Lumen Test Bayside')
    company('Co')  # normalises to nothing: ignored
    company('Co.')
    r = only_row('company_lookalike_names')
    assert r['id'] == str(first.pk)
    assert r['fact'] == '3 records with the same name: Lumen Test Bay Co., Ltd.; The Lumen Test Bay; lumen-test-bay'
    assert [x['label'] for x in r['related']] == ['The Lumen Test Bay', 'lumen-test-bay']


# --- quotes, invoices, tasks ------------------------------------------------------------

def quote(co, status, valid_until, **kw):
    return Quote.objects.create(company=co, status=status, valid_from=valid_until - timedelta(days=30),
                                valid_until=valid_until, total_value=Decimal('4450'), currency='USD', **kw)


def test_quote_sent_expired():
    co = company()
    creator = User.objects.create_user(username='quote.maker', password='x', role='Sales',
                                       first_name='Quinn', last_name='Maker')
    expired = quote(co, 'Sent', T - timedelta(days=1), created_by=creator)
    quote(co, 'Sent', T)
    quote(co, 'Accepted', T - timedelta(days=5))
    converted = quote(co, 'Sent', T - timedelta(days=5))
    contract(co, quote=converted)
    assert ids('quote_sent_expired') == [str(expired.pk)]
    r = only_row('quote_sent_expired')
    assert r['fact'] == 'Valid until 18 Nov 2026 (yesterday); still Sent'
    assert (r['owner_name'], r['link'], r['amount']) == ('Quinn Maker', f'/quotes/{expired.pk}', '4450.00')
    assert ids('quote_sent_expired', owner_id=str(creator.pk)) == [str(expired.pk)]
    assert ids('quote_sent_expired', owner_id='none') == []


def invoice(co, status, due, number):
    return Invoice.objects.create(company=co, status=status, invoice_number=number, issue_date=due - timedelta(days=30),
                                  due_date=due, amount=Decimal('50000'), total_amount=Decimal('50000'), currency='THB')


def test_invoice_overdue():
    co = company()
    late = invoice(co, 'Sent', T - timedelta(days=1), 'TEST-INV-1')
    marked = invoice(co, 'Overdue', T - timedelta(days=40), 'TEST-INV-2')
    invoice(co, 'Sent', T, 'TEST-INV-3')
    invoice(co, 'Draft', T - timedelta(days=5), 'TEST-INV-4')
    invoice(co, 'Paid', T - timedelta(days=5), 'TEST-INV-5')
    invoice(co, 'Cancelled', T - timedelta(days=5), 'TEST-INV-6')
    assert ids('invoice_overdue') == [str(marked.pk), str(late.pk)]
    rows = dq.CHECKS_BY_KEY['invoice_overdue'].rows(dq.Context())
    assert rows[1]['fact'] == 'Due 18 Nov 2026; 1 day overdue'
    assert rows[1]['link'] == f'/invoices?open={late.pk}'


def test_invoice_owner_comes_from_its_contract():
    co = company()
    owner = User.objects.create_user(username='opp.owner', password='x', role='Sales')
    opp = Opportunity.objects.create(company=co, name='Renewal 2026', owner=owner)
    c = contract(co, opportunity=opp)
    inv = invoice(co, 'Sent', T - timedelta(days=3), 'TEST-INV-9')
    Invoice.objects.filter(pk=inv.pk).update(contract=c)
    assert only_row('invoice_overdue')['owner_id'] == str(owner.pk)
    assert ids('invoice_overdue', owner_id=str(owner.pk)) == [str(inv.pk)]


def task(co, status, due, title, **kw):
    return Task.objects.create(company=co, status=status, due_date=due, title=title, **kw)


def test_task_overdue_uses_bangkok_day_and_open_statuses():
    co = company()
    assignee = User.objects.create_user(username='task.owner', password='x', role='Sales', first_name='Tara')
    yesterday_late = task(co, 'To Do', at(T) - timedelta(seconds=1), 'Call back GM', assigned_to=assignee)
    task(co, 'To Do', at(T, 0, 30), 'Due earlier today')  # past the clock, but due today
    on_hold = task(co, 'On Hold', at(T - timedelta(days=3), 10), 'Send playlist')
    task(co, 'Cancelled', at(T - timedelta(days=5), 10), 'Dropped')
    task(co, 'Done', at(T - timedelta(days=5), 10), 'Finished')
    task(co, 'In Progress', None, 'Undated')
    assert ids('task_overdue') == [str(on_hold.pk), str(yesterday_late.pk)]
    rows = dq.CHECKS_BY_KEY['task_overdue'].rows(dq.Context())
    assert rows[0]['fact'] == 'Due 16 Nov 2026 (3 days ago); On Hold'
    assert rows[1]['fact'] == 'Due 18 Nov 2026 (yesterday)'
    assert (rows[1]['owner_name'], rows[1]['link']) == ('Tara', f'/tasks/{yesterday_late.pk}')


# --- owners -------------------------------------------------------------------------------

def test_contract_owner_from_opportunity_then_quote_creator():
    co = company()
    seller = User.objects.create_user(username='seller.one', password='x', role='Sales', first_name='Sam')
    maker = User.objects.create_user(username='maker.one', password='x', role='Sales', first_name='Mai')
    by_opp = contract(co, end=T - timedelta(days=3),
                      opportunity=Opportunity.objects.create(company=co, name='Deal', owner=seller))
    by_quote = contract(co, end=T - timedelta(days=4), quote=quote(co, 'Accepted', T, created_by=maker))
    nobody = contract(co, end=T - timedelta(days=5))
    owners = {r['id']: r['owner_name'] for r in dq.CHECKS_BY_KEY['contract_active_past_end'].rows(dq.Context())}
    assert owners == {str(by_opp.pk): 'Sam', str(by_quote.pk): 'Mai', str(nobody.pk): None}
    assert ids('contract_active_past_end', owner_id=str(maker.pk)) == [str(by_quote.pk)]
    assert ids('contract_active_past_end', owner_id='none') == [str(nobody.pk)]


# --- query counts ---------------------------------------------------------------------------

def _seed(n):
    """n records for every check."""
    for i in range(n):
        co = company(f'Seed {n}-{i} Venue Co., Ltd.')
        company(f'seed {n} {i} venue')  # lookalike
        contract(co, end=T - timedelta(days=2 + i))  # past end, no locations
        contract(co, end=T - timedelta(days=2 + i), auto_renew=True)
        ending = contract(company(f'Seed {n}-{i} Ending Venue'), end=T + timedelta(days=10 + i))  # no contacts
        location(ending)
        contract(co, status='Sent', start=T - timedelta(days=40 + i))
        d = contract(co, status='Draft', start=T + timedelta(days=100))
        Contract.objects.filter(pk=d.pk).update(updated_at=at(T - timedelta(days=90)))
        Contact.objects.create(company=co, name=f'Bad {i}', email=f'bad{i}@')
        quote(co, 'Sent', T - timedelta(days=3 + i))
        invoice(co, 'Sent', T - timedelta(days=3 + i), f'SEED-{n}-{i}')
        task(co, 'To Do', at(T - timedelta(days=2 + i)), f'Seed task {i}')


EXPECTED_QUERIES = {check.key: (1 if isinstance(check, dq.ListCheck) else 2) for check in dq.CHECKS}


def _queries(check):
    ctx = dq.Context()
    with CaptureQueriesContext(connection) as captured:
        count = check.count(ctx)
        check.rows(ctx, None, 0, 50)
    return count, len(captured)


@pytest.mark.parametrize('key', list(dq.CHECKS_BY_KEY))
def test_query_count_is_fixed_per_check(key):
    check = dq.CHECKS_BY_KEY[key]
    _seed(1)
    small_count, small = _queries(check)
    _seed(6)
    large_count, large = _queries(check)
    assert large_count > small_count > 0, (small_count, large_count)
    assert small == large == EXPECTED_QUERIES[key]


def test_summary_query_count_is_fixed():
    expected = sum(EXPECTED_QUERIES.values())
    _seed(1)
    with CaptureQueriesContext(connection) as small:
        dq.summary(dq.Context(), rows_per_check=5)
    _seed(6)
    with CaptureQueriesContext(connection) as large:
        dq.summary(dq.Context(), rows_per_check=5)
    assert len(small) == len(large) == expected


# --- API ------------------------------------------------------------------------------------

@pytest.fixture
def api():
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username='needs.fixing', password='x', role='Sales'))
    return client


def test_anonymous_is_refused():
    client = APIClient()
    assert client.get('/api/v1/data-quality/').status_code == 401
    assert client.get('/api/v1/data-quality/task_overdue/').status_code == 401
    assert client.get('/api/v1/data-quality/task_overdue/?export=csv').status_code == 401


def test_read_only(api):
    for method in ('post', 'put', 'patch', 'delete'):
        assert getattr(api, method)('/api/v1/data-quality/').status_code == 405
        assert getattr(api, method)('/api/v1/data-quality/task_overdue/').status_code == 405


def test_summary_endpoint_orders_by_severity_then_count(api):
    co = company()
    contract(co, end=T - timedelta(days=2))  # high: past end (also medium: no locations)
    for i in range(3):
        task(co, 'To Do', at(T - timedelta(days=2)), f'Late {i}')  # medium x3
    response = api.get('/api/v1/data-quality/?rows=2')
    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    data = response.json()
    assert data['today'] == '2026-11-19'
    keys = [c['key'] for c in data['checks']]
    assert len(keys) == len(dq.CHECKS)
    severities = [c['severity'] for c in data['checks']]
    assert severities == sorted(severities, key=dq.SEVERITY_ORDER.get)
    assert keys[0] == 'contract_active_past_end'
    mediums = [c for c in data['checks'] if c['severity'] == 'medium']
    assert [m['key'] for m in mediums][:2] == ['task_overdue', 'contract_no_service_locations']
    tasks = next(c for c in data['checks'] if c['key'] == 'task_overdue')
    assert tasks['count'] == 3 and len(tasks['rows']) == 2
    assert data['total'] == sum(c['count'] for c in data['checks'])
    assert data['clear'] == sum(1 for c in data['checks'] if c['count'] == 0)
    assert {'key', 'title', 'why', 'severity', 'record_type', 'count', 'rows'} <= set(data['checks'][0])


def test_check_endpoint_pages_and_filters(api):
    a, b = company('Paging Test A'), company('Paging Test B')
    for i in range(5):
        task(a, 'To Do', at(T - timedelta(days=10 - i)), f'A{i}')
    task(b, 'To Do', at(T - timedelta(days=1)), 'B0')
    data = api.get('/api/v1/data-quality/task_overdue/?page=2&page_size=2').json()
    assert (data['count'], data['page'], data['page_size']) == (6, 2, 2)
    assert [r['label'] for r in data['rows']] == ['A2', 'A3']
    assert data['title'] == 'Overdue tasks'
    data = api.get(f'/api/v1/data-quality/task_overdue/?company={b.pk}').json()
    assert [r['label'] for r in data['rows']] == ['B0']


@pytest.mark.parametrize('query', ['page=0', 'page_size=201', 'page=x', 'company=not-an-id', 'owner=someone'])
def test_bad_parameters(api, query):
    assert api.get(f'/api/v1/data-quality/task_overdue/?{query}').status_code == 400


def test_unknown_check(api):
    response = api.get('/api/v1/data-quality/no_such_check/')
    assert response.status_code == 404
    assert 'task_overdue' in response.json()['checks']


def test_csv_export(api):
    co = company('=Formula Test Venue')
    for i in range(3):
        task(co, 'To Do', at(T - timedelta(days=2 + i)), f'Chase {i}')
    response = api.get('/api/v1/data-quality/task_overdue/?export=csv&page_size=1')
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/csv; charset=utf-8'
    assert response['Content-Disposition'] == 'attachment; filename="needs-fixing-task_overdue-2026-11-19.csv"'
    text = response.content.decode('utf-8')
    assert text.startswith('﻿')
    rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    assert rows[0] == ['check', 'record_type', 'label', 'company', 'fact', 'owner', 'date', 'amount', 'currency',
                       'link', 'record_id', 'company_id']
    assert len(rows) == 4  # all rows, not one page
    assert rows[1][3] == "'=Formula Test Venue"
    assert rows[1][4] == 'Due 15 Nov 2026 (4 days ago)'


# --- command --------------------------------------------------------------------------------

def test_command_table_and_json():
    co = company()
    contract(co, end=T - timedelta(days=2))
    out = io.StringIO()
    call_command('data_quality_report', stdout=out)
    text = out.getvalue()
    assert 'Data quality as of 19 Nov 2026 (Bangkok)' in text
    assert any(line.startswith('contract_active_past_end') and line.split()[2] == '1' for line in text.splitlines())
    out = io.StringIO()
    call_command('data_quality_report', '--json', '--rows', '1', stdout=out)
    payload = json.loads(out.getvalue())
    past = next(c for c in payload['checks'] if c['key'] == 'contract_active_past_end')
    assert past['count'] == 1 and past['rows'][0]['link'] == f'/contracts/{Contract.objects.get(end_date=T - timedelta(days=2)).pk}'
    out = io.StringIO()
    call_command('data_quality_report', '--json', '--today', '2026-11-16', stdout=out)
    assert json.loads(out.getvalue())['today'] == '2026-11-16'


def test_checks_never_write():
    _seed(2)
    with CaptureQueriesContext(connection) as captured:
        dq.summary(dq.Context(), rows_per_check=20)
        for check in dq.CHECKS:
            check.rows(dq.Context())
    assert all(q['sql'].lstrip().upper().startswith('SELECT') for q in captured.captured_queries)
