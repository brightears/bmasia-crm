"""Table-driven tests for the one renewal-state rule (no database needed)."""
from datetime import date

import pytest

from crm_app.services.renewals_page_service import (
    AUTO_RENEWS, DRAFTED, INVOICED, LAPSED, LOST, NOT_STARTED, PAID, RENEWED_UNLINKED,
    SENT, SIGNED, STATES, SuccessorFacts as S, TermFacts as T, attention_of,
    derive_renewal_state, invoice_state_of, pick_successor, product_display, term_months, value_change,
)

pytestmark = pytest.mark.unit

JAN, FEB, MAR = date(2027, 1, 1), date(2027, 2, 1), date(2027, 3, 1)

# (case, term, successors, expected state, expected successor key or None)
CASES = [
    # --- no successor -------------------------------------------------------
    ('active, nothing linked', T('Active'), [], NOT_STARTED, None),
    ('sent term (never signed), nothing linked', T('Sent'), [], NOT_STARTED, None),
    ('active auto-renew, nothing linked', T('Active', auto_renew=True), [], AUTO_RENEWS, None),
    ('expired, nothing linked', T('Expired'), [], LAPSED, None),
    ('expired auto-renew, nothing linked: Expired wins', T('Expired', auto_renew=True), [], LAPSED, None),
    ('renewed, nothing linked', T('Renewed'), [], RENEWED_UNLINKED, None),
    ('renewed auto-renew, nothing linked', T('Renewed', auto_renew=True), [], RENEWED_UNLINKED, None),
    ('cancelled, nothing linked', T('Cancelled'), [], LOST, None),
    ('cancelled auto-renew', T('Cancelled', auto_renew=True), [], LOST, None),

    # --- one successor, by its status ----------------------------------------
    ('draft renewal', T('Active'), [S('Draft', JAN, key='a')], DRAFTED, 'a'),
    ('sent renewal', T('Active'), [S('Sent', JAN, key='a')], SENT, 'a'),
    ('active renewal', T('Active'), [S('Active', JAN, key='a')], SIGNED, 'a'),
    ('renewal already renewed again', T('Renewed'), [S('Renewed', JAN, key='a')], SIGNED, 'a'),
    ('renewal that has itself expired', T('Renewed'), [S('Expired', JAN, key='a')], SIGNED, 'a'),
    ('sent renewal with signed date', T('Active'), [S('Sent', JAN, signed_date=JAN, key='a')], SIGNED, 'a'),
    ('active renewal, invoice issued', T('Renewed'), [S('Active', JAN, invoice_state='invoiced', key='a')], INVOICED, 'a'),
    ('active renewal, paid', T('Renewed'), [S('Active', JAN, invoice_state='paid', key='a')], PAID, 'a'),
    ('sent renewal, invoice issued (issued invoice is evidence)', T('Active'),
     [S('Sent', JAN, invoice_state='invoiced', key='a')], INVOICED, 'a'),
    ('draft renewal, paid', T('Active'), [S('Draft', JAN, invoice_state='paid', key='a')], PAID, 'a'),

    # --- term status vs successor --------------------------------------------
    ('expired placeholder with active renewal', T('Expired'), [S('Active', JAN, key='a')], SIGNED, 'a'),
    ('expired term with sent renewal', T('Expired'), [S('Sent', JAN, key='a')], SENT, 'a'),
    ('auto-renew term with draft renewal: the renewal decides', T('Active', auto_renew=True),
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

    # --- add-ons are not renewals --------------------------------------------------
    ('only an add-on linked', T('Active'), [S('Active', JAN, lifecycle_type='addon', key='a')], NOT_STARTED, None),
    ('only an add-on linked, auto-renew term', T('Active', auto_renew=True),
     [S('Active', JAN, lifecycle_type='addon', key='a')], AUTO_RENEWS, None),
    ('add-on plus sent renewal', T('Active'),
     [S('Active', FEB, lifecycle_type='addon', key='a'), S('Sent', JAN, lifecycle_type='renewal', key='b')], SENT, 'b'),
    ('cancelled add-on is not a declined renewal', T('Active'),
     [S('Cancelled', JAN, lifecycle_type='addon', key='a')], NOT_STARTED, None),
    ('term marked Renewed, only add-on linked', T('Renewed'),
     [S('Active', JAN, lifecycle_type='addon', key='a')], RENEWED_UNLINKED, None),
]


@pytest.mark.parametrize('case,term,successors,expected,successor_key', CASES, ids=[c[0] for c in CASES])
def test_derive_renewal_state(case, term, successors, expected, successor_key):
    result = derive_renewal_state(term, successors)
    assert result.state == expected
    assert (result.successor.key if result.successor else None) == successor_key


def test_every_state_is_reachable_and_labelled():
    reached = {derive_renewal_state(c[1], c[2]).state for c in CASES}
    assert reached == {key for key, _, _ in STATES}


@pytest.mark.parametrize('statuses,expected', [
    ([], 'none'),
    (['Draft'], 'none'),
    (['Cancelled', 'Refunded'], 'none'),
    (['Sent'], 'invoiced'),
    (['Overdue'], 'invoiced'),
    (['Paid'], 'paid'),
    (['Paid', 'Paid'], 'paid'),
    (['Paid', 'Sent'], 'invoiced'),  # instalments: one still open
    (['Paid', 'Draft'], 'paid'),     # a draft is not issued
    (['Paid', 'Cancelled'], 'paid'),
])
def test_invoice_state_of(statuses, expected):
    assert invoice_state_of(statuses) == expected


@pytest.mark.parametrize('state,days,expected', [
    (NOT_STARTED, 5, 'ended_nothing_sent'),
    (DRAFTED, 1, 'ended_nothing_sent'),
    (SENT, 10, 'ended_not_signed'),
    (NOT_STARTED, 0, 'ending_soon_nothing_sent'),
    (NOT_STARTED, -30, 'ending_soon_nothing_sent'),
    (DRAFTED, -12, 'ending_soon_nothing_sent'),
    (NOT_STARTED, -31, None),
    (SENT, -5, None),
    (SENT, 0, None),
    (SIGNED, 40, None),
    (PAID, 40, None),
    (AUTO_RENEWS, 40, None),
    (LAPSED, 40, None),
    (LOST, 40, None),
    (RENEWED_UNLINKED, -90, 'renewed_unlinked'),
    (NOT_STARTED, None, None),
])
def test_attention_of(state, days, expected):
    assert attention_of(state, days) == expected


@pytest.mark.parametrize('start,end,months', [
    (date(2026, 1, 1), date(2026, 12, 31), 12),
    (date(2025, 11, 1), date(2026, 10, 31), 12),
    (date(2026, 3, 15), date(2027, 3, 14), 12),
    (date(2025, 1, 1), date(2027, 12, 31), 36),   # multi-year
    (date(2026, 7, 1), date(2026, 12, 31), 6),
    (date(2026, 2, 1), date(2026, 2, 28), 1),
    (None, date(2026, 12, 31), None),
    (date(2026, 12, 31), date(2026, 1, 1), None),
])
def test_term_months(start, end, months):
    assert term_months(start, end) == months


@pytest.mark.parametrize('old,old_m,new,new_m,same,expected', [
    (108000, 12, 120000, 12, True, (12000.0, 'term')),
    (1200, 12, 1000, 12, True, (-200.0, 'term')),
    (36000, 36, 13200, 12, True, (1200.0, 'per_year')),   # 3-year term renewed for 1 year
    (6000, 6, 12000, 12, True, (0.0, 'per_year')),
    (1200, 12, 1300, 13, True, (100.0, 'term')),          # a month either way is the same term
    (1200, None, 1300, 12, True, (100.0, 'term')),
    (1200, 12, 1300, 12, False, (None, None)),            # never across currencies
    (1200, 12, None, 12, True, (None, None)),
])
def test_value_change(old, old_m, new, new_m, same, expected):
    assert value_change(old, old_m, new, new_m, same) == expected


def test_pick_successor_ignores_addons_and_cancelled():
    assert pick_successor([S('Cancelled', JAN), S('Active', JAN, lifecycle_type='addon')]) is None


@pytest.mark.parametrize('book,platforms,expected', [
    ('Soundtrack', ['beatbreeze'], ('Soundtrack', 'renewal_book')),   # the book's own evidence stays first
    ('Beat Breeze', [], ('Beat Breeze', 'renewal_book')),
    ('Other', [], ('Other', 'renewal_book')),
    ('Other', ['custom'], ('Other', 'renewal_book')),
    ('Other', ['beatbreeze', 'beatbreeze'], ('Beat Breeze', 'service_locations')),
    ('Other', ['soundtrack', 'beatbreeze', 'custom'], ('Beat Breeze + Soundtrack', 'service_locations')),
])
def test_product_display(book, platforms, expected):
    assert product_display(book, platforms) == expected
