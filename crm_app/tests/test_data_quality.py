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


NO_END = object()


def contract(co, status='Active', start=None, end=None, **kw):
    if end is NO_END:
        end = None
        start = start or T - timedelta(days=100)
    else:
        end = end if end is not None else T + timedelta(days=200)
        start = start or end - timedelta(days=364)
    return Contract.objects.create(company=co, status=status, start_date=start, end_date=end,
                                   value=Decimal('108000'), currency='THB', **kw)


def location(c, name='Lobby'):
    return ContractServiceLocation.objects.create(contract=c, location_name=name, platform='soundtrack')


def zone_link(c, active=True, zone=None):
    z = zone or Zone.objects.create(company=c.company, name=f'Zone {Zone.objects.count() + 1}')
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


# Table-driven successor cases. Each builder returns (ending contract, listed?, fact ending).
# The ending contract ends in 20 days (19 Nov + 20 = 9 Dec 2026) unless a case says otherwise.
# By default both contracts are at the property "Riverside Wing" with a location "Lobby".
E_END = T + timedelta(days=20)
SYB = 'soundtrack_unlimited_yearly'
WING = 'Riverside Wing'


def _ending(co=None, place='Lobby', **kw):
    kw.setdefault('property_name', WING)
    e = contract(co or company(contracted_product='soundtrack'), end=kw.pop('end', E_END), **kw)
    if place:
        location(e, place)
    return e


def _next(e, status='Draft', start=None, end=None, place='Lobby', co=None, **kw):
    kw.setdefault('property_name', WING)
    start = start or e.end_date + timedelta(days=1)
    c = contract(co or e.company, status=status, start=start, end=end or start + timedelta(days=364), **kw)
    if place:
        location(c, place)
    return c


def possible(c):
    return f'possible renewal: {c.contract_number} (not linked)'


# --- cleared: an unambiguous renewal -------------------------------------------------------

def case_genuine_unlinked_renewal():
    e = _ending()
    _next(e)
    return e, False, None


def case_unlinked_renewal_starting_on_the_end_date():
    e = _ending()
    _next(e, start=E_END)
    return e, False, None


def case_unlinked_sent_renewal():
    e = _ending()
    _next(e, status='Sent')
    return e, False, None


def case_unlinked_active_renewal_without_end_date():
    e = _ending()
    _next(e, status='Active', end=NO_END)
    return e, False, None


def case_same_property_spelled_differently():
    e = _ending(place=None)
    _next(e, place=None, property_name='riverside  wing')
    return e, False, None


def case_no_property_on_either_side_but_a_shared_zone():
    e = _ending(place=None, property_name='')
    link = zone_link(e)
    n = _next(e, place=None, property_name='')
    zone_link(n, zone=link.zone)
    return e, False, None


def case_multi_year_renewal():
    e = _ending(start=E_END - timedelta(days=3 * 365))
    _next(e, end=E_END + timedelta(days=3 * 365))
    return e, False, None


def case_unknown_product_matches():
    e = _ending(co=company(contracted_product=''))
    _next(e, service_type='beat_breeze_yearly')
    return e, False, None


def case_start_60_days_after_end():
    e = _ending()
    _next(e, start=E_END + timedelta(days=60))
    return e, False, None


def case_linked_draft():
    e = _ending()
    _next(e, renewed_from=e, place=None, property_name='')
    return e, False, None


def case_linked_renewed_renewal():
    e = _ending()
    _next(e, status='Renewed', renewed_from=e, place=None)
    return e, False, None


def case_cancelled_then_redrafted():
    e = _ending()
    _next(e, status='Cancelled', renewed_from=e)
    _next(e, renewed_from=e)
    return e, False, None


# --- listed: possible renewal (not linked) -------------------------------------------------

def case_renewal_with_property_on_one_side_only():
    e = _ending()
    n = _next(e, property_name='')
    return e, True, possible(n)


def case_neither_records_places():
    e = _ending(place=None, property_name='')
    n = _next(e, place=None, property_name='')
    return e, True, possible(n)


def case_only_a_generic_location_name_matches():
    e = _ending(property_name='')
    n = _next(e, property_name='')
    return e, True, possible(n)


def case_add_on_without_lifecycle_type_at_the_same_property():
    e = _ending(end=T + timedelta(days=30))
    n = _next(e, start=T - timedelta(days=60))
    return e, True, None, f'Ends in 30 days (19 Dec 2026); {possible(n)}'


def case_early_renewal_starting_before_the_end():
    e = _ending()
    n = _next(e, start=E_END - timedelta(days=10))
    return e, True, possible(n)


def case_start_90_days_before_end():
    e = _ending()
    n = _next(e, start=E_END - timedelta(days=90))
    return e, True, possible(n)


# --- listed: no renewal drafted ------------------------------------------------------------

def case_two_venues_on_staggered_terms():
    e = _ending()
    venue_b = contract(e.company, start=T - timedelta(days=120), end=T + timedelta(days=245),
                       property_name='Hillside Wing')
    location(venue_b, 'Lobby')
    return e, True, 'no renewal drafted'


def case_other_venues_renewal_draft():
    e = _ending()
    _next(e, start=E_END - timedelta(days=10), property_name='Hillside Wing')
    return e, True, 'no renewal drafted'


def case_different_property_name_after_the_end():
    e = _ending(place=None)
    _next(e, place=None, property_name='Hillside Wing')
    return e, True, 'no renewal drafted'


def case_add_on():
    e = _ending()
    _next(e, start=E_END - timedelta(days=15), lifecycle_type='addon')
    return e, True, 'no renewal drafted'


def case_churn_contract():
    e = _ending()
    _next(e, lifecycle_type='churn')
    return e, True, 'no renewal drafted'


def case_one_off_setup_draft():
    e = _ending()
    _next(e, start=T + timedelta(days=1), service_type='one_time_setup')
    return e, True, 'no renewal drafted'


def case_one_time_contract_type():
    e = _ending()
    _next(e, contract_type='One-time')
    return e, True, 'no renewal drafted'


def case_one_time_billing():
    e = _ending()
    _next(e, billing_frequency='One-time')
    return e, True, 'no renewal drafted'


def case_zero_duration_term():
    e = _ending()
    start = E_END + timedelta(days=1)
    _next(e, start=start, end=start)
    return e, True, 'no renewal drafted'


def case_multi_year_parallel_contract():
    e = _ending()
    contract(e.company, start=T - timedelta(days=700), end=T + timedelta(days=400), property_name=WING)
    return e, True, 'no renewal drafted'


def case_renewal_on_parent_company():
    parent = company('Test Parent Group')
    e = _ending(co=company(contracted_product='soundtrack', parent_company=parent))
    _next(e, co=parent)
    return e, True, 'no renewal drafted'


def case_child_renewal_does_not_cover_parent():
    parent = company('Test Parent Holdings', contracted_product='soundtrack')
    e = _ending(co=parent)
    _next(e, co=company(contracted_product='soundtrack', parent_company=parent))
    return e, True, 'no renewal drafted'


def case_other_product():
    e = _ending(service_type=SYB)
    _next(e, service_type='beat_breeze_yearly')
    return e, True, 'no renewal drafted'


def case_draft_linked_to_another_contract():
    e = _ending()
    other = contract(e.company, end=T - timedelta(days=200), status='Expired')
    _next(e, renewed_from=other)
    return e, True, 'no renewal drafted'


def case_same_start_as_ending_contract():
    e = _ending(start=T - timedelta(days=40))
    _next(e, start=T - timedelta(days=40), end=T + timedelta(days=100))
    return e, True, 'no renewal drafted'


def case_start_91_days_before_end():
    e = _ending()
    _next(e, start=E_END - timedelta(days=91))
    return e, True, 'no renewal drafted'


def case_start_61_days_after_end():
    e = _ending()
    _next(e, start=E_END + timedelta(days=61))
    return e, True, 'no renewal drafted'


def case_ends_with_the_ending_contract():
    e = _ending()
    _next(e, start=E_END - timedelta(days=30), end=E_END)
    return e, True, 'no renewal drafted'


def case_auto_renewing_contract_is_listed():
    e = _ending(auto_renew=True)
    return e, True, 'no renewal drafted; auto-renews'


# --- listed: a linked renewal that is not the next term ------------------------------------

def case_linked_cancelled_renewal():
    e = _ending()
    n = _next(e, status='Cancelled', renewed_from=e)
    return e, True, f'renewal {n.contract_number} was cancelled'


def case_linked_expired_renewal():
    e = _ending()
    n = _next(e, status='Expired', renewed_from=e)
    return e, True, f'renewal {n.contract_number} expired'


SUCCESSOR_CASES = [v for k, v in sorted(globals().items()) if k.startswith('case_')]


@pytest.mark.parametrize('build', SUCCESSOR_CASES, ids=lambda f: f.__name__[5:])
def test_successor_rule(build):
    e, listed, fact_end, *full = build()
    rows = {r['id']: r for r in dq.CHECKS_BY_KEY['contract_ending_no_successor'].rows(dq.Context())}
    assert (str(e.pk) in rows) is listed
    if listed:
        expected = full[0] if full else f'Ends in 20 days (9 Dec 2026); {fact_end}'
        assert rows[str(e.pk)]['fact'] == expected


def test_two_venues_on_one_record_share_a_generic_location_name():
    """One unlinked renewal for the Riverside venue clears Riverside only."""
    co = company(contracted_product='soundtrack')
    riverside = _ending(co=co, place='Lobby', property_name='Riverside')
    hillside = _ending(co=co, place='Lobby', property_name='Hillside', end=T + timedelta(days=25))
    _next(riverside, place='Lobby', property_name='Riverside')
    rows = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['contract_ending_no_successor'].rows(dq.Context())}
    assert str(riverside.pk) not in rows
    assert rows[str(hillside.pk)] == 'Ends in 25 days (14 Dec 2026); no renewal drafted'


def test_one_renewal_clears_one_ending_contract_only():
    co = company(contracted_product='soundtrack')
    first = _ending(co=co)
    second = _ending(co=co, end=T + timedelta(days=20))
    n = _next(first, start=E_END + timedelta(days=1))
    rows = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['contract_ending_no_successor'].rows(dq.Context())}
    listed = [c for c in (first, second) if str(c.pk) in rows]
    assert len(listed) == 1
    assert rows[str(listed[0].pk)] == f'Ends in 20 days (9 Dec 2026); {possible(n)}'


def test_product_falls_back_to_company_product():
    bb_company = company(contracted_product='beatbreeze')
    current = contract(bb_company, end=T + timedelta(days=20))
    contract(bb_company, status='Draft', start=T + timedelta(days=21), end=T + timedelta(days=385),
             service_type='soundtrack_essential_yearly')
    assert ids('contract_ending_no_successor') == [str(current.pk)]


def test_ending_owner_filter():
    co = company()
    seller = User.objects.create_user(username='ending.owner', password='x', role='Sales')
    owned = contract(co, end=T + timedelta(days=5),
                     opportunity=Opportunity.objects.create(company=co, name='R', owner=seller))
    unowned = contract(company(), end=T + timedelta(days=6))
    assert ids('contract_ending_no_successor', owner_id=str(seller.pk)) == [str(owned.pk)]
    assert ids('contract_ending_no_successor', owner_id='none') == [str(unowned.pk)]


def test_active_without_end_date():
    co = company()
    open_ended = contract(co, end=NO_END, start=T - timedelta(days=100))
    contract(co, status='Draft', end=NO_END)
    assert ids('contract_active_no_end_date') == [str(open_ended.pk)]
    assert only_row('contract_active_no_end_date')['fact'] == 'Started 11 Aug 2026; no end date recorded'
    # it is in no other contract term check
    for key in ('contract_active_past_end', 'contract_auto_renew_past_end', 'contract_ending_no_successor'):
        assert str(open_ended.pk) not in ids(key)


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
    assert facts[str(neither.pk)] == 'No service locations and no zone links: the PDF has no zone schedule'
    assert facts[str(links_only.pk)] == ('No service locations; the PDF lists its 1 linked zone, '
                                         'the renewal book uses the company-wide zone count')
    facts = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['contract_no_zone_links'].rows(dq.Context())}
    assert facts[str(locations_only.pk)] == '2 service locations; no active zone link'


# --- companies and contacts -------------------------------------------------------------

def test_company_without_email_contact():
    missing = company('Harbour Test Hotel')
    contract(missing)
    Contact.objects.create(company=missing, name='Old Contact', email='old@example.com', is_active=False)
    Contact.objects.create(company=missing, name='No Email', email='')
    Contact.objects.create(company=missing, name='Placeholder', email='n/a@')
    ok = company()
    contract(ok)
    Contact.objects.create(company=ok, name='Has Email', email='gm@example.com')
    unsubscribed = company()
    contract(unsubscribed)
    Contact.objects.create(company=unsubscribed, name='Opted Out', email='gm@optout.example', unsubscribed=True,
                           receives_notifications=False)
    no_contract = company()
    contract(no_contract, status='Expired', end=T - timedelta(days=30))
    bare = company()
    contract(bare)
    assert set(ids('company_no_email_contact')) == {str(missing.pk), str(bare.pk)}
    facts = {r['id']: r['fact'] for r in dq.CHECKS_BY_KEY['company_no_email_contact'].rows(dq.Context())}
    assert facts[str(missing.pk)] == '1 Active contract; 3 contacts, none active with a valid email'
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


def test_shared_email_whole_parent_chain_is_one_group():
    hq = company('Test Chain HQ')
    brand = company('Test Chain Brand', parent_company=hq)
    venue = company('Test Chain Venue', parent_company=brand)
    for c in (hq, brand, venue):
        Contact.objects.create(company=c, name='Group Finance', email='finance@chain.example')
    assert ids('contact_email_problem') == []
    outsider = company('Test Unrelated Outsider')
    Contact.objects.create(company=outsider, name='Group Finance', email='finance@chain.example')
    assert only_row('contact_email_problem')['fact'].startswith('Same email at 4 companies: ')


def test_corporate_root_survives_a_parent_cycle():
    a, b, c = 'a', 'b', 'c'
    assert dq.corporate_root(c, {c: b, b: a}) == a
    assert dq.corporate_root(a, {a: b, b: a}) == dq.corporate_root(b, {a: b, b: a}) == a
    assert dq.corporate_root(c, {c: c}) == c


def test_invalid_email_found_whatever_its_shape():
    co = company()
    long_label = 'a@' + 'x' * 64 + '.com'  # a domain label over 63 characters: fails, and is over 64 long
    odd = ['n/a@', 'x@example.123', 'a..b@example.com', '.a@example.com', 'a@-example.com', 'gm@example.com ',
           'gm@example.com\n', long_label]
    for email in odd + ['ok.person+tag@sub.example.co.th', "o'brien@example.com"]:
        Contact.objects.create(company=co, name=email, email=email)
    facts = {r['label']: r['fact'] for r in dq.CHECKS_BY_KEY['contact_email_problem'].rows(dq.Context())}
    assert set(facts) == set(odd)


@pytest.mark.parametrize('email', ['gm@example.com', 'first.last+tag@sub.example.co.th', "o'brien@example.org",
                                   'x_y-z@example-hotel.travel'])
def test_certainly_valid_pattern_implies_valid(email):
    import re
    assert re.match(dq.CERTAINLY_VALID_EMAIL, email)
    assert dq.is_valid_email(email)


def test_shared_invalid_address_is_listed_as_invalid_only():
    a, b = company('Invalid Share A'), company('Invalid Share B')
    Contact.objects.create(company=a, name='Desk', email='desk@share.example ')
    Contact.objects.create(company=b, name='Desk', email='Desk@share.example ')
    facts = [r['fact'] for r in dq.CHECKS_BY_KEY['contact_email_problem'].rows(dq.Context())]
    assert len(facts) == 2 and all('is not a valid address' in f for f in facts)


def test_email_pattern_has_no_end_of_line_leeway():
    import re
    assert re.match(dq.CERTAINLY_VALID_EMAIL, 'gm@example.com')
    assert not re.match(dq.CERTAINLY_VALID_EMAIL, 'gm@example.com\n')


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
    ('Kinara Probe Public Company Limited', 'Kinara Probe'),
    ('Co Ltd Probe Garden', 'Probe Garden'),
    ('บริษัท สยาม ซาวด์ จำกัด (มหาชน)', 'สยาม ซาวด์'),
    ('บริษัทสยามซาวด์จำกัด', 'สยาม ซาวด์'),
    ('บริษัท สยามซาวด์ จำกัด', 'สยามซาวด์'),
    ('Talvora Test Nangang Taipei', 'Talvora Test Taipei Nangang'),
    ('Hotel Orvane Deira', 'Orvane Deira Hotel'),
    ('Probe Bay Hotel Phuket', 'Probe Bay Phuket Hotel'),
    ('Probe Resort & Spa', 'Probe Resort Spa'),
    ('Probe Resort and Spa Co., Ltd.', 'Probe Resort'),
    ('LumenBay Resort', 'Lumen Bay Resort'),
    ('Orvélia Probe Retreat', 'Orvelia Probe Retreat'),
    ('Lönnhaven Probe Lodge', 'Lonnhaven Probe Lodge'),
    ('Probe Mall of the Moon', 'Probe Mall of Moon'),
    ('Probe Park Condominium Juristic Person', 'Probe Park'),
])
def test_names_that_look_alike(a, b):
    assert dq.names_look_alike(a, b)


@pytest.mark.parametrize('a,b', [
    ('Lumen Bay', 'Lumen Bayside'),
    ('Coralstone Mall', 'Coralstone Mall Penang'),
    ('Moonlit Garden Resort', 'Moonlit Garden Hotel'),
    ('Sa Ninh Probe Cosmetics', 'Ninh Probe Cosmetics Co., Ltd.'),
    ('The Public Probe House', 'Probe House'),
    ('Private Probe Room', 'Probe Room'),
    ('Probe Hotels', 'Hotel Probe'),
    ('Probe Hotel', 'Probe'),
    ('Orvane Deira', 'Orvane Deira Hotel'),
    ('KK Probe Garden', 'Probe Garden'),
    ('AG Probe Studio', 'Probe Studio'),
    ('Greenleaf Probe Spa', 'Greenleaf Probe'),
    ('Probe Day Spa', 'Probe Day'),
    ('Probe (Thailand) Co., Ltd.', 'Probe'),
    ('Person Probe Studio', 'Probe Studio'),
    ('Probe Condominium', 'Probe'),
    ('ส้มตำ โพรบ', 'สมตำ โพรบ'),
])
def test_names_that_differ(a, b):
    assert not dq.names_look_alike(a, b)


def test_short_or_generic_names_have_no_key():
    assert dq.company_name_keys('Co.') == ()
    assert dq.company_name_keys('The A Ltd') == ()
    assert dq.company_name_keys('The Hotel') == ()
    assert dq.company_name_keys('Hotel & Spa Co., Ltd.') == ()


def test_lookalike_companies_one_row_per_group():
    names = ['Lumen Test Bay Co., Ltd.', 'lumen-test-bay', 'The Lumen Test Bay', 'LumenTestBay', 'Lumen Test Bayside',
             'Co', 'Co.']
    made = [company(n) for n in names]
    # distinct creation times, oldest first: the group never depends on name collation
    for i, c in enumerate(made):
        Company.objects.filter(pk=c.pk).update(created_at=at(T - timedelta(days=30 - i)))
    r = only_row('company_lookalike_names')
    assert r['id'] == str(made[0].pk)
    assert r['fact'] == ('4 records with the same name: Lumen Test Bay Co., Ltd.; lumen-test-bay; '
                         'The Lumen Test Bay; LumenTestBay')
    assert [x['label'] for x in r['related']] == ['lumen-test-bay', 'The Lumen Test Bay', 'LumenTestBay']


def test_lookalike_tie_on_creation_time_breaks_on_id():
    made = [company(n) for n in ('Zeta Probe Lodge', 'zeta-probe-lodge', 'The Zeta Probe Lodge')]
    Company.objects.filter(pk__in=[c.pk for c in made]).update(created_at=at(T - timedelta(days=3)))
    first = min(made, key=lambda c: c.pk)
    assert only_row('company_lookalike_names')['id'] == str(first.pk)


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
    both = contract(co, end=T - timedelta(days=6), quote=quote(co, 'Accepted', T, created_by=maker),
                    opportunity=Opportunity.objects.create(company=co, name='Deal 2', owner=seller))
    owners = {r['id']: r['owner_name'] for r in dq.CHECKS_BY_KEY['contract_active_past_end'].rows(dq.Context())}
    assert owners == {str(by_opp.pk): 'Sam', str(by_quote.pk): 'Mai', str(nobody.pk): None, str(both.pk): 'Sam'}
    assert ids('contract_active_past_end', owner_id=str(seller.pk)) == [str(by_opp.pk), str(both.pk)]
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
        contract(co, end=NO_END)
        twin = company(f'Seed {n}-{i} Other Group')
        Contact.objects.create(company=co, name=f'Shared {i}', email=f'shared{n}.{i}@seed.example')
        Contact.objects.create(company=twin, name=f'Shared {i}', email=f'Shared{n}.{i}@seed.example')


# Queries per check (count and first page together); never more with more rows.
EXPECTED_QUERIES = {check.key: 2 for check in dq.CHECKS} | {
    'contract_ending_no_successor': 3,  # ending contracts, candidates, zone links
    'company_no_email_contact': 2,  # companies with an Active contract, their contacts' emails
    'contact_email_problem': 4,  # addresses SQL cannot vouch for, shared addresses, their holders, parent links
    'company_lookalike_names': 1,  # all company names
}


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


@pytest.mark.parametrize('query', ['rows=21', 'rows=-1', 'rows=x', 'company=not-an-id', 'owner=someone', 'owner=NONE'])
def test_bad_summary_parameters(api, query):
    assert api.get(f'/api/v1/data-quality/?{query}').status_code == 400


def test_summary_rows_cap_and_filters(api):
    a, b = company('Summary Filter A'), company('Summary Filter B')
    for i in range(25):
        task(a, 'To Do', at(T - timedelta(days=2)), f'A{i:02d}')
    task(b, 'To Do', at(T - timedelta(days=2)), 'B only')
    tasks = next(c for c in api.get('/api/v1/data-quality/?rows=20').json()['checks'] if c['key'] == 'task_overdue')
    assert tasks['count'] == 26 and len(tasks['rows']) == 20
    tasks = next(c for c in api.get(f'/api/v1/data-quality/?company={b.pk}').json()['checks']
                 if c['key'] == 'task_overdue')
    assert tasks['count'] == 1 and [r['label'] for r in tasks['rows']] == ['B only']


def test_check_page_is_not_cached(api):
    assert api.get('/api/v1/data-quality/task_overdue/')['Cache-Control'] == 'no-store'
    assert api.get('/api/v1/data-quality/task_overdue/?export=csv')['Cache-Control'] == 'no-store'
    assert api.get('/api/v1/data-quality/task_overdue/?export=CSV')['Content-Type'].startswith('text/csv')


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


@pytest.mark.parametrize('name', ['=SUM(A1)', '+1', '-1', '@cmd', '\tTab Venue', '\rCR Venue', ' Space Venue',
                                  '"Quoted Venue', "'Apostrophe Venue", '\u00a0NBSP Venue', '\uff1dWide Venue'])
def test_csv_escapes_risky_starts(api, name):
    task(company(name), 'To Do', at(T - timedelta(days=2)), 'Chase')
    text = api.get('/api/v1/data-quality/task_overdue/?export=csv').content.decode('utf-8').lstrip('\ufeff')
    assert list(csv.reader(io.StringIO(text)))[1][3] == "'" + name


def test_csv_keeps_negative_amounts_and_applies_filters(api):
    co, other = company('Credit Test Venue'), company('Other Test Venue')
    inv = invoice(co, 'Sent', T - timedelta(days=3), 'TEST-CREDIT-1')
    Invoice.objects.filter(pk=inv.pk).update(total_amount=Decimal('-500.00'))
    invoice(other, 'Sent', T - timedelta(days=4), 'TEST-CREDIT-2')
    text = api.get(f'/api/v1/data-quality/invoice_overdue/?export=csv&company={co.pk}').content.decode('utf-8')
    rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))
    assert len(rows) == 2 and rows[1][2] == 'TEST-CREDIT-1' and rows[1][7] == '-500.00'
    owner = User.objects.create_user(username='csv.owner', password='x', role='Sales')
    text = api.get(f'/api/v1/data-quality/invoice_overdue/?export=csv&owner={owner.pk}').content.decode('utf-8')
    assert len(list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))) == 1


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


def test_checks_api_and_command_never_write(api):
    _seed(2)
    with CaptureQueriesContext(connection) as captured:
        dq.summary(dq.Context(), rows_per_check=20)
        for check in dq.CHECKS:
            check.rows(dq.Context())
            assert api.get(f'/api/v1/data-quality/{check.key}/').status_code == 200
            assert api.get(f'/api/v1/data-quality/{check.key}/?export=csv').status_code == 200
        assert api.get('/api/v1/data-quality/?rows=20').status_code == 200
        call_command('data_quality_report', '--json', '--rows', '3', stdout=io.StringIO())
    statements = [q['sql'].lstrip().upper() for q in captured.captured_queries]
    assert statements and all(sql.startswith('SELECT') for sql in statements), \
        [sql for sql in statements if not sql.startswith('SELECT')]
