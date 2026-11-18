"""Table-driven tests for the one renewal-state rule and its helpers (no database needed)."""
from datetime import date
from decimal import Decimal

import pytest

from crm_app.services.renewals_page_service import (
    AUTO_RENEWS, AUTO_UNCONFIRMED, DRAFTED, INVOICED, LAPSED, LIVE_UNLINKED, LOST, NOT_STARTED, PAID, PART_PAID,
    PLACEHOLDER, RENEWED_UNLINKED, SENT, SIGNED, STATES, InvoiceFacts as I, SuccessorFacts as S, TermFacts as T,
    attention_of, calendar_window, classify_link, derive_renewal_state, due_so_far, funnel_window, gap_days, in_rate,
    instalments_per_year, invoice_state_of, month_of, pick_successor, product_display, summary_bucket, term_months,
    value_change,
)

pytestmark = pytest.mark.unit

JAN, FEB, MAR = date(2027, 1, 1), date(2027, 2, 1), date(2027, 3, 1)

# (case, term, successors, expected state, expected successor key or None)
CASES = [
    # --- no successor -------------------------------------------------------
    ('active, nothing linked', T('Active'), [], NOT_STARTED, None),
    ('sent term (never signed), nothing linked', T('Sent'), [], NOT_STARTED, None),
    ('active auto-renew, not ended yet', T('Active', auto_renew=True), [], AUTO_RENEWS, None),
    ('active auto-renew, ended, nothing linked', T('Active', auto_renew=True, ended=True), [], AUTO_UNCONFIRMED, None),
    ('expired, nothing linked', T('Expired'), [], LAPSED, None),
    ('expired auto-renew, nothing linked: Expired wins', T('Expired', auto_renew=True, ended=True), [], LAPSED, None),
    ('renewed, nothing linked', T('Renewed'), [], RENEWED_UNLINKED, None),
    ('renewed auto-renew, nothing linked', T('Renewed', auto_renew=True), [], RENEWED_UNLINKED, None),
    ('cancelled, nothing linked', T('Cancelled'), [], LOST, None),
    ('cancelled auto-renew', T('Cancelled', auto_renew=True), [], LOST, None),

    # --- the company has a live term that is not linked ------------------------
    ('expired, live term not linked', T('Expired', ended=True, live_unlinked=True), [], LIVE_UNLINKED, None),
    ('ended active, live term not linked', T('Active', ended=True, live_unlinked=True), [], LIVE_UNLINKED, None),
    ('ended auto-renew, live term not linked', T('Active', auto_renew=True, ended=True, live_unlinked=True), [],
     LIVE_UNLINKED, None),
    ('renewed, live term not linked: still renewed-not-linked', T('Renewed', live_unlinked=True), [],
     RENEWED_UNLINKED, None),
    ('cancelled, live term not linked: still lost', T('Cancelled', live_unlinked=True), [], LOST, None),
    ('declined renewal, live term not linked: still lost', T('Expired', live_unlinked=True),
     [S('Cancelled', JAN, key='a')], LOST, None),

    # --- placeholders --------------------------------------------------------
    ('placeholder, Expired', T('Expired', placeholder=True, ended=True), [], PLACEHOLDER, None),
    ('placeholder, Renewed with a renewal linked', T('Renewed', placeholder=True),
     [S('Active', JAN, key='a')], PLACEHOLDER, None),

    # --- one successor, by its status ----------------------------------------
    ('draft renewal', T('Active'), [S('Draft', JAN, key='a')], DRAFTED, 'a'),
    ('sent renewal', T('Active'), [S('Sent', JAN, key='a')], SENT, 'a'),
    ('active renewal', T('Active'), [S('Active', JAN, key='a')], SIGNED, 'a'),
    ('renewal already renewed again', T('Renewed'), [S('Renewed', JAN, key='a')], SIGNED, 'a'),
    ('renewal that has itself expired', T('Renewed'), [S('Expired', JAN, key='a')], SIGNED, 'a'),
    ('sent renewal with signed date', T('Active'), [S('Sent', JAN, signed_date=JAN, key='a')], SIGNED, 'a'),
    ('active renewal, invoice issued', T('Renewed'), [S('Active', JAN, invoice_state='invoiced', key='a')], INVOICED, 'a'),
    ('active renewal, part paid', T('Renewed'), [S('Active', JAN, invoice_state='part_paid', key='a')], PART_PAID, 'a'),
    ('active renewal, paid', T('Renewed'), [S('Active', JAN, invoice_state='paid', key='a')], PAID, 'a'),
    ('sent renewal, invoice issued (issued invoice is evidence)', T('Active'),
     [S('Sent', JAN, invoice_state='invoiced', key='a')], INVOICED, 'a'),
    ('draft renewal, paid', T('Active'), [S('Draft', JAN, invoice_state='paid', key='a')], PAID, 'a'),

    # --- term status vs successor --------------------------------------------
    ('expired placeholder-term with active renewal', T('Expired'), [S('Active', JAN, key='a')], SIGNED, 'a'),
    ('expired term with sent renewal', T('Expired'), [S('Sent', JAN, key='a')], SENT, 'a'),
    ('auto-renew term with draft renewal: the renewal decides', T('Active', auto_renew=True, ended=True),
     [S('Draft', JAN, key='a')], DRAFTED, 'a'),
    ('cancelled term with active renewal: Cancelled wins', T('Cancelled'), [S('Active', JAN, key='a')], LOST, None),

    # --- cancelled successors --------------------------------------------------
    ('only renewal cancelled (declined)', T('Active'), [S('Cancelled', JAN, key='a')], LOST, None),
    ('only renewal cancelled, auto-renew term', T('Active', auto_renew=True), [S('Cancelled', JAN, key='a')], LOST, None),
    ('only renewal cancelled, term marked Renewed', T('Renewed'), [S('Cancelled', JAN, key='a')], RENEWED_UNLINKED, None),
    ('only renewal cancelled, term Expired', T('Expired'), [S('Cancelled', JAN, key='a')], LOST, None),
    ('cancelled renewal replaced by a sent one', T('Active'),
     [S('Cancelled', FEB, key='a'), S('Sent', JAN, key='b')], SENT, 'b'),
    ('cancelled paid renewal does not count', T('Active'),
     [S('Cancelled', JAN, invoice_state='paid', key='a')], LOST, None),

    # --- several successors ------------------------------------------------------
    ('draft and active: active wins', T('Active'), [S('Draft', FEB, key='a'), S('Active', JAN, key='b')], SIGNED, 'b'),
    ('two drafts: latest start wins', T('Active'), [S('Draft', JAN, key='a'), S('Draft', FEB, key='b')], DRAFTED, 'b'),
    ('two actives, one paid: paid wins', T('Renewed'),
     [S('Active', FEB, key='a'), S('Active', JAN, invoice_state='paid', key='b')], PAID, 'b'),
    ('sent and draft: sent wins', T('Active'), [S('Draft', MAR, key='a'), S('Sent', JAN, key='b')], SENT, 'b'),
    ('money before stage: invoiced draft beats sent without invoice', T('Active'),
     [S('Sent', FEB, key='a'), S('Draft', JAN, invoice_state='invoiced', key='b')], INVOICED, 'b'),
    ('money before stage: part-paid draft beats active without invoice', T('Active'),
     [S('Active', FEB, key='a'), S('Draft', JAN, invoice_state='part_paid', key='b')], PART_PAID, 'b'),

    # --- links that are not the renewal ----------------------------------------------
    ('only an add-on linked', T('Active'), [S('Active', JAN, link='addon', key='a')], NOT_STARTED, None),
    ('only an add-on linked, auto-renew term', T('Active', auto_renew=True),
     [S('Active', JAN, link='addon', key='a')], AUTO_RENEWS, None),
    ('add-on plus sent renewal', T('Active'),
     [S('Active', FEB, link='addon', key='a'), S('Sent', JAN, key='b')], SENT, 'b'),
    ('cancelled add-on is not a declined renewal', T('Active'),
     [S('Cancelled', JAN, link='addon', key='a')], NOT_STARTED, None),
    ('term marked Renewed, only add-on linked', T('Renewed'),
     [S('Active', JAN, link='addon', key='a')], RENEWED_UNLINKED, None),
    ('unmarked add-on starting mid-term is not the renewal', T('Active'),
     [S('Active', JAN, link='mid_term', key='a')], NOT_STARTED, None),
    ('overlapping full term is not the renewal', T('Renewed'),
     [S('Active', JAN, link='overlap', key='a')], RENEWED_UNLINKED, None),
    ('linked contract starting long after the end still is the renewal', T('Active'),
     [S('Active', JAN, link='late', key='a')], SIGNED, 'a'),
    ('renewal beats a late link', T('Active'),
     [S('Active', JAN, link='late', key='a'), S('Sent', FEB, invoice_state='invoiced', key='b')], INVOICED, 'b'),
]


@pytest.mark.parametrize('case,term,successors,expected,successor_key', CASES, ids=[c[0] for c in CASES])
def test_derive_renewal_state(case, term, successors, expected, successor_key):
    result = derive_renewal_state(term, successors)
    assert result.state == expected
    assert (result.successor.key if result.successor else None) == successor_key


def test_every_state_is_reachable_and_labelled():
    reached = {derive_renewal_state(c[1], c[2]).state for c in CASES}
    assert reached == {key for key, _, _ in STATES}


# --- money ------------------------------------------------------------------

@pytest.mark.parametrize('freq,expected', [
    ('Annually', 1), ('Annual', 1), ('', 1), ('Quarterly', 4), ('Semi-annually', 2), ('Semi-Annual', 2),
    ('Biannually', 2), ('Bi-annually', 2), ('Half-yearly', 2), ('Monthly', 12), ('One-time', None),
    ('full term', None), ('Every month or so', 1), ('Bimonthly', 1)  # free text is never read as monthly
])
def test_instalments_per_year(freq, expected):
    assert instalments_per_year(freq) == expected


S26, E27 = date(2026, 12, 1), date(2027, 11, 30)


@pytest.mark.parametrize('value,freq,start,end,today,expected', [
    (1200, 'Annually', S26, E27, date(2026, 11, 18), '1200.00'),        # before the start: the first instalment
    (1200, 'Quarterly', S26, E27, date(2026, 11, 18), '300.00'),
    (1200, 'Quarterly', S26, E27, date(2027, 3, 1), '600.00'),          # second quarter started
    (1200, 'Quarterly', S26, E27, date(2027, 11, 1), '1200.00'),        # never more than the term
    (1200, 'Semi-Annual', S26, E27, date(2027, 6, 1), '1200.00'),
    (1200, 'Monthly', S26, E27, date(2027, 1, 15), '200.00'),
    (600, 'Quarterly', date(2026, 12, 1), date(2027, 5, 31), date(2026, 12, 2), '300.00'),  # 6-month term
    (1200, 'Annually', date(2026, 12, 1), date(2028, 11, 30), date(2027, 12, 5), '2400.00'),  # 2 years, per year
    (1200, 'One-time', S26, E27, date(2026, 11, 18), '1200'),
    (0, 'Annually', S26, E27, date(2026, 11, 18), '0'),
])
def test_due_so_far(value, freq, start, end, today, expected):
    assert due_so_far(value, freq, start, end, today) == Decimal(expected)


@pytest.mark.parametrize('invoices,due,expected', [
    ([], 1200, 'none'),
    ([I('Draft', 1200, 'USD')], 1200, 'none'),
    ([I('Cancelled', 1200, 'USD'), I('Refunded', 1200, 'USD')], 1200, 'none'),
    ([I('Sent', 1200, 'USD')], 1200, 'invoiced'),
    ([I('Overdue', 1200, 'USD')], 1200, 'invoiced'),
    ([I('Paid', 1200, 'USD')], 1200, 'paid'),
    ([I('Paid', 1195, 'USD')], 1200, 'paid'),                      # rounding within 1 %
    ([I('Paid', 300, 'USD')], 1200, 'part_paid'),                  # one quarterly instalment of four, all due
    ([I('Paid', 300, 'USD')], 300, 'paid'),                        # one quarter, only one due so far
    ([I('Paid', 600, 'USD'), I('Sent', 600, 'USD')], 1200, 'part_paid'),
    ([I('Paid', 1200, 'USD'), I('Sent', 300, 'USD')], 1200, 'part_paid'),  # covered, but not every one paid
    ([I('Paid', 1200, 'USD'), I('Draft', 50, 'USD')], 1200, 'paid'),
    ([I('Paid', 0, 'USD')], 1200, 'none'),                         # zero-value invoices do not count
    ([I('Paid', 0, 'USD'), I('Sent', 1200, 'USD')], 1200, 'invoiced'),
    ([I('Paid', 40000, 'THB')], 1200, 'none'),                     # other currency cannot be checked
])
def test_invoice_state_of(invoices, due, expected):
    assert invoice_state_of(invoices, Decimal(str(due)), 'USD') == expected


# --- links ------------------------------------------------------------------

TS, TE = date(2025, 12, 1), date(2026, 11, 30)


@pytest.mark.parametrize('start,lifecycle,expected', [
    (date(2026, 12, 1), '', 'renewal'),
    (date(2026, 9, 1), '', 'renewal'),          # end - 90 days
    (date(2026, 8, 31), '', 'mid_term'),         # earlier than that
    (date(2026, 3, 1), '', 'mid_term'),
    (date(2025, 12, 1), '', 'mid_term'),         # not after the term's start
    (date(2027, 1, 29), '', 'renewal'),          # end + 60 days
    (date(2027, 1, 30), '', 'late'),
    (date(2026, 12, 1), 'addon', 'addon'),
    (date(2026, 12, 1), 'renewal', 'renewal'),
    (date(2025, 11, 30), '', 'mid_term'),        # before the term's start
])
def test_classify_link(start, lifecycle, expected):
    assert classify_link(TS, TE, start, lifecycle) == expected


def test_link_on_or_before_the_start_of_a_short_term_is_mid_term():
    start, end = date(2026, 11, 1), date(2026, 11, 30)   # a one-month term: end - 90 is before its start
    assert classify_link(start, end, date(2026, 11, 1), '') == 'mid_term'
    assert classify_link(start, end, date(2026, 10, 15), '') == 'mid_term'
    assert classify_link(start, end, date(2026, 11, 2), '') == 'renewal'


@pytest.mark.parametrize('months,value,expected', [
    (12, 1200, 'overlap'),     # a full term at the same value: a second record, check the dates
    (12, 1205, 'overlap'),
    (12, 1000, 'mid_term'),    # different value: a possible add-on
    (6, 1200, 'mid_term'),     # shorter: a possible add-on
    (None, 1200, 'mid_term'),
])
def test_mid_term_link_that_is_a_full_term_is_an_overlap(months, value, expected):
    assert classify_link(TS, TE, date(2026, 4, 1), '', link_months=months, link_value=value,
                         term_value=1200) == expected


def test_pick_successor_ignores_non_renewal_links_and_cancelled():
    assert pick_successor([S('Cancelled', JAN), S('Active', JAN, link='addon'), S('Active', JAN, link='mid_term')]) is None
    assert pick_successor([S('Active', JAN, link='late', key='x')]).key == 'x'


# --- attention, totals, rate --------------------------------------------------

def test_attention_names_a_mid_term_or_overlapping_link_on_a_term_marked_renewed():
    assert attention_of(RENEWED_UNLINKED, 30, mid_term_link=True) == 'renewed_link_mid_term'
    assert attention_of(RENEWED_UNLINKED, 30, mid_term_link=True, overlap_link=True) == 'renewed_link_overlap'
    assert attention_of(NOT_STARTED, 30, mid_term_link=True) == 'ended_nothing_sent'


def test_attention_for_live_unlinked_and_recent_gap():
    assert attention_of(LIVE_UNLINKED, 30) == 'link_the_renewal'
    assert attention_of(LIVE_UNLINKED, -10) == 'link_the_renewal'
    assert attention_of(SIGNED, 200, recent_gap=True) == 'renewed_after_gap'
    assert attention_of(SIGNED, 200, refunded=True, recent_gap=True) == 'invoice_refunded'


@pytest.mark.parametrize('end,start,expected', [
    (date(2026, 6, 29), date(2026, 6, 30), 0),
    (date(2026, 6, 29), date(2026, 7, 1), 1),
    (date(2025, 12, 31), date(2026, 5, 3), 122),
    (None, date(2026, 1, 1), None),
])
def test_gap_days(end, start, expected):
    assert gap_days(end, start) == expected


@pytest.mark.parametrize('state,days,refunded,expected', [
    (NOT_STARTED, 5, False, 'ended_nothing_sent'),
    (DRAFTED, 1, False, 'ended_nothing_sent'),
    (SENT, 10, False, 'ended_not_signed'),
    (NOT_STARTED, 0, False, 'ending_soon_nothing_sent'),
    (NOT_STARTED, -30, False, 'ending_soon_nothing_sent'),
    (DRAFTED, -12, False, 'ending_soon_nothing_sent'),
    (NOT_STARTED, -31, False, None),
    (SENT, -5, False, None),
    (SENT, 0, False, None),
    (SIGNED, 40, False, None),
    (PAID, 40, False, None),
    (AUTO_RENEWS, -10, False, None),
    (AUTO_UNCONFIRMED, 40, False, 'auto_renew_ended'),
    (LAPSED, 40, False, None),
    (LOST, 40, False, None),
    (RENEWED_UNLINKED, -90, False, 'renewed_unlinked'),
    (SIGNED, 10, True, 'invoice_refunded'),
    (PLACEHOLDER, 40, True, None),
    (NOT_STARTED, None, False, None),
])
def test_attention_of(state, days, refunded, expected):
    assert attention_of(state, days, refunded) == expected


@pytest.mark.parametrize('state,never,y2025,expected', [
    (NOT_STARTED, False, False, 'open'), (AUTO_UNCONFIRMED, False, False, 'open'), (PAID, False, False, 'renewed'),
    (AUTO_RENEWS, False, False, 'auto'), (LAPSED, False, False, 'lost'), (LOST, False, False, 'lost'),
    (LOST, True, False, 'excluded'), (NOT_STARTED, True, False, 'open'), (PLACEHOLDER, False, False, 'excluded'),
    (LIVE_UNLINKED, False, False, 'unlinked'), (LIVE_UNLINKED, False, True, 'unlinked'),
    (LAPSED, False, True, 'history'), (LOST, False, True, 'history'), (SIGNED, False, True, 'renewed'),
    (NOT_STARTED, False, True, 'open'),
])
def test_summary_bucket(state, never, y2025, expected):
    assert summary_bucket(state, never, y2025) == expected


@pytest.mark.parametrize('state,days,never,expected', [
    (SIGNED, -40, False, True),          # decided early
    (LOST, -5, False, True),
    (NOT_STARTED, -10, False, False),    # still ahead, undecided
    (NOT_STARTED, 3, False, True),       # ended without a renewal
    (AUTO_UNCONFIRMED, 3, False, True),
    (AUTO_RENEWS, -3, False, False),
    (PLACEHOLDER, 30, False, False),
    (LAPSED, 30, True, False),           # never activated
    (SIGNED, 30, True, False),
    (NOT_STARTED, None, False, False),
    (LIVE_UNLINKED, 30, False, False),   # probably renewed, not proven: out of the rate
])
def test_in_rate(state, days, never, expected):
    assert in_rate(state, days, never) is expected


def test_2025_placeholder_terms_are_never_in_the_rate():
    assert in_rate(SIGNED, 300, False, True) is False
    assert in_rate(LAPSED, 300, False, True) is False


# --- months -----------------------------------------------------------------

@pytest.mark.parametrize('year,month,start,end', [
    (2026, 11, date(2026, 10, 31), date(2026, 11, 29)),
    (2026, 12, date(2026, 11, 30), date(2026, 12, 30)),
    (2027, 1, date(2026, 12, 31), date(2027, 1, 30)),     # across the year boundary
    (2027, 2, date(2027, 1, 31), date(2027, 2, 27)),
    (2028, 2, date(2028, 1, 31), date(2028, 2, 28)),      # leap year
    (2027, 3, date(2027, 2, 28), date(2027, 3, 30)),
    (2028, 3, date(2028, 2, 29), date(2028, 3, 30)),
])
def test_funnel_window(year, month, start, end):
    assert funnel_window(year, month) == (start, end)


def test_calendar_window():
    assert calendar_window(2027, 2) == (date(2027, 2, 1), date(2027, 2, 28))
    assert calendar_window(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))


@pytest.mark.parametrize('end,basis,expected', [
    (date(2026, 10, 31), 'funnel', (2026, 11)),
    (date(2026, 11, 29), 'funnel', (2026, 11)),
    (date(2026, 11, 30), 'funnel', (2026, 12)),
    (date(2026, 12, 31), 'funnel', (2027, 1)),
    (date(2027, 2, 28), 'funnel', (2027, 3)),
    (date(2028, 2, 28), 'funnel', (2028, 2)),
    (date(2028, 2, 29), 'funnel', (2028, 3)),
    (date(2026, 12, 31), 'calendar', (2026, 12)),
    (date(2026, 10, 31), 'calendar', (2026, 10)),
])
def test_month_of(end, basis, expected):
    assert month_of(end, basis) == expected


def test_month_of_agrees_with_the_windows():
    day = date(2025, 12, 1)
    while day < date(2028, 4, 1):
        for basis, window in (('funnel', funnel_window), ('calendar', calendar_window)):
            y, m = month_of(day, basis)
            start, end = window(y, m)
            assert start <= day <= end, (day, basis)
        day = date.fromordinal(day.toordinal() + 1)


# --- terms and values ---------------------------------------------------------

@pytest.mark.parametrize('start,end,months', [
    (date(2026, 1, 1), date(2026, 12, 31), 12),
    (date(2025, 11, 1), date(2026, 10, 31), 12),
    (date(2026, 3, 15), date(2027, 3, 14), 12),
    (date(2025, 1, 1), date(2027, 12, 31), 36),
    (date(2026, 7, 1), date(2026, 12, 31), 6),
    (date(2026, 2, 1), date(2026, 2, 28), 1),
    (None, date(2026, 12, 31), None),
    (date(2026, 12, 31), date(2026, 1, 1), None),
])
def test_term_months(start, end, months):
    assert term_months(start, end) == months


@pytest.mark.parametrize('old,new,same,expected', [
    (108000, 120000, True, 12000.0),
    (1200, 1000, True, -200.0),
    (12000, 12000, True, 0.0),      # 36-month term renewed for 12 months at the same annual price
    (12000, 13200, True, 1200.0),   # ... at a higher annual price
    (1200, 1300, False, None),      # never across currencies
    (1200, None, True, None),
])
def test_value_change_compares_annual_values(old, new, same, expected):
    assert value_change(old, new, same) == expected


@pytest.mark.parametrize('book,platforms,expected', [
    ('Soundtrack', ['beatbreeze'], ('Soundtrack', 'renewal_book')),
    ('Beat Breeze', [], ('Beat Breeze', 'renewal_book')),
    ('Other', [], ('Other', 'renewal_book')),
    ('Other', ['custom'], ('Other', 'renewal_book')),
    ('Other', ['beatbreeze', 'beatbreeze'], ('Beat Breeze', 'service_locations')),
    ('Other', ['soundtrack', 'beatbreeze', 'custom'], ('Beat Breeze + Soundtrack', 'service_locations')),
])
def test_product_display(book, platforms, expected):
    assert product_display(book, platforms) == expected
