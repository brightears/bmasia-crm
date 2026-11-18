"""Company timeline after review: bad input, rows that render to nothing, per-user visibility.

All names are invented. Companies carry no music-service account id.
"""
from __future__ import annotations

import base64
import json
import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm_app import timeline
from crm_app.models import (
    AuditLog, CareTouch, Contact, Contract, EmailLog, Invoice, Note, Opportunity, OpportunityActivity, Quote,
    QuoteActivity, Task, Ticket, TicketComment,
)
from crm_app.tests.test_company_timeline import (
    BASE, TZ, _all, _at, _audit, _client, _company, _contract, _get, _quote, _types, _user,
)


@pytest.fixture
def admin():
    return _user('alex.review', 'Admin', 'Alex', 'Review')


@pytest.fixture
def company():
    return _company('Harbourline Test Resort')


def _url(company):
    return f'/api/v1/companies/{company.pk}/timeline/'


def _cursor(t, i):
    raw = json.dumps({'t': t, 'i': i}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


# ---------------------------------------------------------------- M1: bad input is a 400


@pytest.mark.parametrize('params,param', [
    ({'cursor': _cursor('2026-11-10T09:30:00+07:00', 'note:not-a-uuid')}, 'cursor'),
    ({'cursor': _cursor('2026-11-10T09:30:00+07:00', 'note:12')}, 'cursor'),
    ({'cursor': _cursor('2026-11-10T09:30:00+07:00', 'note:')}, 'cursor'),
    ({'cursor': _cursor('2026-11-10T09:30:00+07:00', 'note:a b')}, 'cursor'),
    ({'cursor': _cursor('0001-01-01T00:00:00+07:00', f'note:{uuid.uuid4()}')}, 'cursor'),
    ({'cursor': _cursor('9999-12-31T23:59:59+00:00', f'note:{uuid.uuid4()}')}, 'cursor'),
    ({'cursor': _cursor('2026-11-10T09:30:00', f'note:{uuid.uuid4()}')}, 'cursor'),  # no zone
    ({'cursor': 'x' * 600}, 'cursor'),
    ({'cursor': 'not-a-cursor'}, 'cursor'),
    ({'from': '0001-01-01'}, 'from'),
    ({'to': '9999-12-31'}, 'to'),
    ({'from': '1899-12-31'}, 'from'),
    ({'from': '2026-11-10', 'to': '2026-11-01'}, 'from'),
    ({'from': '2026-13-01'}, 'from'),
    ({'q': 'a\x00b'}, 'q'),
    ({'q': 'line\nbreak'}, 'q'),
    ({'q': 'x' * 201}, 'q'),
    ({'record': 'contract:\x00'}, 'record'),
    ({'record': 'zone:' + str(uuid.uuid4())}, 'record'),
    ({'types': 'note\x00'}, 'types'),
    ({'types': 'note,bogus'}, 'types'),
    ({'actor': 'x'}, 'actor'),
    ({'page_size': '0'}, 'page_size'),
    ({'page_size': '101'}, 'page_size'),
    ({'page_size': '1000'}, 'page_size'),
    ({'page_size': '-1'}, 'page_size'),
    ({'page_size': '2.5'}, 'page_size'),
])
def test_bad_input_is_a_400_naming_the_parameter(admin, company, params, param):
    Note.objects.create(company=company, author=admin, text='something')
    response = _client(admin).get(_url(company), params)
    assert response.status_code == 400, response.content
    body = response.json()
    assert body['param'] == param and body['error']


@pytest.mark.parametrize('params', [
    {'page_size': '100'}, {'page_size': '1'}, {'from': '1900-01-01', 'to': '9998-12-31'},
    {'q': 'x' * 200}, {'q': 'ทดสอบ'}, {'q': '%_'},
    {'cursor': _cursor('9998-12-31T23:59:59+07:00', f'zz_unknown:{uuid.uuid4()}')},  # unknown source: harmless
    {'cursor': _cursor('1900-01-02T00:00:00+07:00', f'note:{uuid.uuid4()}')},
])
def test_extreme_but_valid_input_is_accepted(admin, company, params):
    assert _client(admin).get(_url(company), params).status_code == 200


ALPHABET = ['a', 'Z', '0', '9', '-', ':', '_', '%', ' ', '\x00', '\n', '\x7f', 'é', 'ท', '😀', ',', '=', '+', '/']


def _fuzz_value(rnd):
    kind = rnd.random()
    if kind < 0.15:
        return ''.join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 600)))
    if kind < 0.3:
        return str(rnd.choice([0, -1, 1, 99, 100, 101, 10 ** 12, 1.5]))
    if kind < 0.45:
        year = rnd.choice([1, 1899, 1900, 2026, 9998, 9999])
        return f'{year:04d}-{rnd.randint(0, 13):02d}-{rnd.randint(0, 32):02d}'
    if kind < 0.6:
        t = rnd.choice(['0001-01-01T00:00:00+00:00', '2026-11-10T09:30:00+07:00', '9999-12-31T23:59:59+00:00',
                        '2026-11-10T09:30:00', 'nonsense'])
        i = rnd.choice([f'note:{uuid.uuid4()}', 'note:1', 'note:', ':x', 'Note:x', 'audit_change:zz',
                        f'email:{uuid.uuid4().hex}', 'x' * 70, 'note:\x00'])
        return _cursor(t, i)
    if kind < 0.75:
        return rnd.choice(list(timeline.RECORD_TYPES) + ['zone', '']) + ':' + rnd.choice(
            [str(uuid.uuid4()), 'x', '', '\x00'])
    return ''.join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 20)))


def test_fuzzed_parameters_never_give_a_server_error(admin, company):
    Note.objects.create(company=company, author=admin, text='fuzz target')
    rnd = random.Random(20261118)
    client = _client(admin)
    names = ['types', 'from', 'to', 'record', 'actor', 'q', 'cursor', 'page_size', 'facets']
    seen = set()
    for _ in range(160):
        params = {name: _fuzz_value(rnd) for name in rnd.sample(names, rnd.randint(1, 4))}
        response = client.get(_url(company), params)
        assert response.status_code in (200, 400), (params, response.status_code)
        if response.status_code == 400:
            assert response.json()['error']
        seen.add(response.status_code)
    assert seen == {200, 400}


# ---------------------------------------------------------------- M2: rows that render to nothing


def _noop(user, contract, when):
    """A writer that lists fields it did not change (MCP guarded paths do this)."""
    return _audit(user, 'Contract', contract.pk, {'notes': {'old': 'same', 'new': 'same'},
                                                  'status': {'old': 'Draft', 'new': 'Draft'}}, when)


def test_a_run_of_no_op_saves_does_not_empty_the_first_page(admin, company):
    contract = _contract(company, 'TH-CT26930', when=BASE - timedelta(days=30))
    _at(Note.objects.create(company=company, author=admin, text='older real note'), BASE - timedelta(days=20))
    for i in range(30):
        _noop(admin, contract, BASE + timedelta(minutes=i))
    first = _get(admin, company, facets=1)
    assert [e['type'] for e in first['results']] == ['note', 'contract_created']
    assert first['has_more'] is False and first['next_cursor'] is None
    types = first['facets']['types']
    assert types['contract'] == 1 and types['note'] == 1 and types['change'] == 0  # visible events only
    assert sum(types.values()) == 2


QUERIES_FIRST_PAGE = 31
# Worst case: every round asks every source (26) plus one user lookup per audit
# source (3), for 1 + EXTRA_ROUNDS rounds, plus the company and the four label maps.
MAX_QUERIES_ANY_PAGE = (1 + timeline.EXTRA_ROUNDS) * (26 + 3) + 5


def test_thousands_of_no_op_saves_page_on_with_bounded_queries(admin, company):
    contract = _contract(company, 'TH-CT26931', when=BASE - timedelta(days=30))
    _at(Note.objects.create(company=company, author=admin, text='the only real note'), BASE - timedelta(days=20))
    AuditLog.objects.bulk_create([
        AuditLog(user=admin, action='UPDATE', model_name='Contract', record_id=str(contract.pk),
                 changes={'notes': {'before': 'same', 'after': 'same'}}) for _ in range(3000)])
    client = _client(admin)
    seen, cursor, pages, counts = [], None, 0, []
    while True:
        params = {'page_size': 25}
        if cursor:
            params['cursor'] = cursor
        with CaptureQueriesContext(connection) as q:
            data = client.get(_url(company), params).json()
        counts.append(len(q.captured_queries))
        seen.extend(e['type'] for e in data['results'])
        pages += 1
        if not data['has_more']:
            break
        assert data['results'] == []  # only unseen no-op rows ahead, and it says so
        cursor = data['next_cursor']
        assert pages < 10
    assert seen == ['note', 'contract_created']
    # 3,000 rows at 25 + 3 x 250 a request: four requests, the last one finds the events.
    assert pages == 4
    # The first request reads the usual 31 queries and three extra rounds of the one open source.
    assert counts[0] == QUERIES_FIRST_PAGE + timeline.EXTRA_ROUNDS
    assert max(counts) <= MAX_QUERIES_ANY_PAGE
    facets = _get(admin, company, facets=1)['facets']['types']
    assert facets['change'] == 0 and facets['contract'] == 1


@pytest.mark.parametrize('seed', [1, 2, 3])
def test_mixed_walk_with_rows_that_render_to_nothing(admin, seed):
    """Visible rows, rows that render to nothing, identical instants, date-only rows, inserts between pages:
    every page size gives the same feed, each event once, newest first."""
    rnd = random.Random(seed)
    company = _company(f'Mixed Walk Test Co {seed}')
    contract = _contract(company, f'TH-MW{seed}', when=BASE - timedelta(days=400))
    instants = [BASE - timedelta(minutes=m) for m in (0, 0, 1, 2, 5, 60, 600, 6000, 60 * 24 * 3)]
    for i in range(170):
        when = rnd.choice(instants)
        r = rnd.random()
        if r < 0.4:
            _audit(admin, 'Contract', contract.pk, {'notes': {'old': 's', 'new': 's'}}, when)  # nothing
        elif r < 0.55:
            _audit(admin, 'Contract', contract.pk, {'notes': {'old': f'a{i}', 'new': f'b{i}'}}, when)
        elif r < 0.65:
            c = _contract(company, f'TH-MW{seed}-{i}', when=when)
            Contract.objects.filter(pk=c.pk).update(signed_date=timezone.localtime(when, TZ).date())
        else:
            _at(Note.objects.create(company=company, author=admin, text=f'n{i}'), when)

    def walk(size, insert_after=None):
        out, cursor, n = [], None, 0
        while True:
            q = {'page_size': size}
            if cursor:
                q['cursor'] = cursor
            d = _get(admin, company, **q)
            assert d['results'] or not d['has_more'] or n > 0, 'first page empty while history exists'
            out.extend(e['id'] for e in d['results'])
            n += 1
            if insert_after is not None and n == insert_after:
                # A newer event and one tying an instant already passed: neither may show up later.
                _at(Note.objects.create(company=company, author=admin, text='late newer'), BASE + timedelta(1))
                _at(Note.objects.create(company=company, author=admin, text='late tie'), instants[-1])
            if not d['has_more']:
                return out
            cursor = d['next_cursor']
            assert n < 2000

    reference = walk(100)
    assert len(reference) == len(set(reference))
    for size in (1, 2, 3, 5, 7, 25):
        assert walk(size) == reference, size
    keys = [(datetime.fromisoformat(e['occurred_at']), e['id']) for e in _all(admin, company, page_size=100)]
    assert keys == sorted(keys, reverse=True)
    before = set(reference)
    during = walk(3, insert_after=2)
    assert len(during) == len(set(during))
    assert set(during) - before <= {e['id'] for e in _all(admin, company) if e['detail'] == 'late tie'}


# ---------------------------------------------------------------- T1: scope and filters


def test_audit_scope_is_this_company_and_its_own_records_only(admin, company):
    other = _company('Northwind Test Bakery')
    mine = Contact.objects.create(company=company, name='Kanya Test', email='kanya@example.test')
    theirs = Contact.objects.create(company=other, name='Somchai Test', email='somchai@example.test')
    my_contract, their_contract = _contract(company, 'TH-SC1'), _contract(other, 'TH-SC2')
    my_quote, their_quote = _quote(company), _quote(other)
    my_opp = Opportunity.objects.create(company=company, name='Mine', owner=admin)
    their_opp = Opportunity.objects.create(company=other, name='Theirs', owner=admin)
    change = {'notes': {'old': 'a', 'new': 'b'}}
    for model, pk in (('Company', company.pk), ('Contact', mine.pk), ('Contract', my_contract.pk),
                      ('Quote', my_quote.pk), ('Opportunity', my_opp.pk)):
        _audit(admin, model, pk, change, BASE)
    for model, pk in (('Company', other.pk), ('Contact', theirs.pk), ('Contract', their_contract.pk),
                      ('Quote', their_quote.pk), ('Opportunity', their_opp.pk)):
        _audit(admin, model, pk, {'notes': {'old': 'secret', 'new': 'other company'}}, BASE)
    events = [e for e in _all(admin, company) if e['category'] == 'change']
    assert sorted(e['extra']['model'] for e in events) == ['Company', 'Contact', 'Contract', 'Opportunity', 'Quote']
    assert 'other company' not in str(events)


def test_secret_fields_never_show_even_when_audited(admin, company):
    contact = Contact.objects.create(company=company, name='Pim Test', email='pim@example.test')
    _audit(admin, 'Contact', contact.pk, {'unsubscribe_token': {'old': 'tok-old', 'new': 'tok-new'}}, BASE)
    _audit(admin, 'Contact', contact.pk, {'unsubscribe_token': {'old': 'tok-a', 'new': 'tok-b'},
                                          'title': {'old': '', 'new': 'GM'}}, BASE - timedelta(1))
    events = _all(admin, company)
    assert len(events) == 1 and [c['field'] for c in events[0]['changes']] == ['title']
    assert 'tok-' not in str(events)


def test_actor_filter_leaves_out_completed_tasks_whose_completer_is_unknown(admin, company):
    task = _at(Task.objects.create(company=company, created_by=admin, title='Check zones', status='Done'),
               BASE - timedelta(1))
    Task.objects.filter(pk=task.pk).update(completed_at=BASE)
    assert _types(_all(admin, company)) == ['task_completed', 'task_created']
    assert _types(_all(admin, company, actor=str(admin.pk))) == ['task_created']


def test_bounced_email_reads_as_failed(admin, company):
    EmailLog.objects.create(company=company, email_type='renewal', from_email='crm@example.test',
                            to_email='gm@example.test', subject='Renewal', body_html='', body_text='',
                            status='bounced', sent_at=BASE)
    [event] = _all(admin, company)
    assert event['type'] == 'email_failed' and event['title'] == 'Email failed: Renewal'


# ---------------------------------------------------------------- M3: what the regular API hides


def _ids(user, path, company):
    response = _client(user).get(path, {'company': company.pk, 'page_size': 1000})
    assert response.status_code == 200, (path, response.status_code)
    data = response.json()
    return {str(row['id']) for row in (data['results'] if isinstance(data, dict) else data)}


SOURCE_ENDPOINTS = [
    ('note', '/api/v1/notes/'),
    ('task_created', '/api/v1/tasks/'),
    ('email', '/api/v1/email-logs/'),
    ('quote_created', '/api/v1/quotes/'),
    ('contract_created', '/api/v1/contracts/'),
    ('invoice_issued', '/api/v1/invoices/'),
    ('ticket_opened', '/api/v1/tickets/'),
    ('opportunity_created', '/api/v1/opportunities/'),
]


@pytest.fixture
def two_sellers_history(company):
    """Two Sales users, each with their own opportunity, private notes and the rest."""
    sam = _user('sam.seller2', 'Sales', 'Sam', 'Seller')
    pat = _user('pat.seller', 'Sales', 'Pat', 'Other')
    sam_opp = Opportunity.objects.create(company=company, name='Sam Rooftop Deal', owner=sam)
    pat_opp = Opportunity.objects.create(company=company, name='Pat Secret Rollout', owner=pat)
    OpportunityActivity.objects.create(opportunity=pat_opp, user=pat, activity_type='Call', subject='Budget call',
                                       description='Client will pay up to 900k')
    OpportunityActivity.objects.create(opportunity=sam_opp, user=sam, activity_type='Call', subject='Intro',
                                       description='Friendly')
    Note.objects.create(company=company, author=pat, text='Pat private', is_private=True)
    Note.objects.create(company=company, author=sam, text='Sam private', is_private=True)
    Note.objects.create(company=company, author=pat, text='Public note')
    quote = _quote(company, created_by=pat, opportunity=pat_opp)
    QuoteActivity.objects.create(quote=quote, user=pat, activity_type='Sent', description='x')
    Task.objects.create(company=company, created_by=pat, title='Chase Pat deal', related_opportunity=pat_opp)
    contract = _contract(company, 'TH-VIS1', opportunity=pat_opp)
    Invoice.objects.create(company=company, contract=contract, invoice_number='INV-VIS-1', status='Sent',
                           issue_date=date(2026, 11, 1), due_date=date(2026, 12, 1), amount=Decimal('1'),
                           total_amount=Decimal('1'), currency='THB')
    EmailLog.objects.create(company=company, quote=quote, email_type='quote_send', from_email='crm@example.test',
                            to_email='gm@example.test', subject='Quote', body_html='', body_text='',
                            status='sent', sent_at=BASE)
    ticket = Ticket.objects.create(company=company, subject='Silent lobby', description='x', created_by=pat)
    TicketComment.objects.create(ticket=ticket, author=pat, text='Rebooted')
    CareTouch.objects.create(company=company, mailbox='care@example.test', occurred_at=BASE, kind='check_in',
                             summary='All good', source='send', idempotency_key=uuid.uuid4().hex,
                             recorded_by='cara', payload_sha256='0' * 64)
    return {'sam': sam, 'pat': pat, 'pat_opp': pat_opp, 'sam_opp': sam_opp}


@pytest.mark.parametrize('source_key,endpoint', SOURCE_ENDPOINTS)
@pytest.mark.parametrize('who', ['sam', 'pat', 'admin'])
def test_each_source_shows_exactly_what_its_endpoint_shows_the_same_user(
        company, two_sellers_history, admin, who, source_key, endpoint):
    user = admin if who == 'admin' else two_sellers_history[who]
    on_timeline = {e['id'].partition(':')[2] for e in _all(user, company) if e['id'].startswith(source_key + ':')}
    assert on_timeline == _ids(user, endpoint, company)


def test_sales_user_never_sees_another_owners_opportunity_anywhere(company, two_sellers_history):
    sam, pat_opp = two_sellers_history['sam'], two_sellers_history['pat_opp']
    events = _all(sam, company)
    text = json.dumps(events)
    assert 'Pat Secret Rollout' not in text and '900k' not in text and str(pat_opp.pk) not in text
    # The quote, task and contract linked to it still show (their own endpoints show them), without the link.
    assert {'quote_created', 'quote_sent', 'task_created', 'contract_created'} <= set(_types(events))
    assert _all(sam, company, q='Secret') == [] and _all(sam, company, q='900k') == []
    assert _all(sam, company, record=f'opportunity:{pat_opp.pk}') == []
    facets = _get(sam, company, facets=1)['facets']['types']
    assert facets['opportunity'] == 2  # Sam's own opportunity and its activity
    # Pat sees their own; Admin sees everything.
    assert '900k' in json.dumps(_all(two_sellers_history['pat'], company))


def test_visibility_reuses_the_viewsets_own_rule(monkeypatch, company, admin):
    """Narrow a viewset's get_queryset and the timeline follows, without a copy of the rule."""
    from crm_app.views import TicketViewSet
    Ticket.objects.create(company=company, subject='Mine', description='x', created_by=admin, assigned_to=admin)
    Ticket.objects.create(company=company, subject='Not mine', description='x', created_by=admin)
    original = TicketViewSet.get_queryset
    monkeypatch.setattr(TicketViewSet, 'get_queryset',
                        lambda self: original(self).filter(assigned_to=self.request.user))
    titles = [e['title'] for e in _all(admin, company)]
    assert titles == ['Ticket opened: Mine']


def test_agent_property_and_names(company):
    cira = _user('cira', 'Admin')
    person = _user('mo.person', 'Admin', 'Mo <mo@example.test>', '')
    address = _user('kim@example.test', 'Admin')
    filters = timeline.Filters()
    assert timeline.TimelineContext(company, cira, filters).is_agent is True
    assert timeline.TimelineContext(company, person, filters).is_agent is False
    assert timeline.actor_for_user(cira) == {'id': str(cira.pk), 'name': 'Cira', 'kind': 'agent'}
    assert timeline.actor_for_user(person)['name'] == 'mo.person'  # never a fragment of an address
    assert timeline.actor_for_user(address)['name'] == 'kim'


def test_extra_agent_usernames_setting(settings, company):
    helper = _user('scout', 'Admin', 'Scout', 'Helper')
    assert timeline.is_agent_account(helper) is False
    settings.AGENT_INBOX_AGENT_USERNAMES = ['scout']
    assert timeline.is_agent_account(helper) is True
    assert timeline.actor_for_user(helper)['kind'] == 'agent'


# ---------------------------------------------------------------- lows


def test_money_in_a_save_that_changed_the_currency_keeps_each_side(admin, company):
    contract = _contract(company, 'TH-CUR1')
    opp = Opportunity.objects.create(company=company, name='Plain number', owner=admin)
    _audit(admin, 'Contract', contract.pk, {'currency': {'old': 'USD', 'new': 'THB'},
                                            'value': {'old': '3000.00', 'new': '3500.00'}}, BASE)
    _audit(admin, 'Opportunity', opp.pk, {'expected_value': {'old': '1000.00', 'new': '2000.00'}}, BASE)
    events = {e['extra']['model']: e for e in _all(admin, company) if e['type'] == 'field_change'}
    value = next(c for c in events['Contract']['changes'] if c['field'] == 'value')
    assert (value['old_currency'], value['currency']) == ('USD', 'THB')
    expected = events['Opportunity']['changes'][0]
    assert expected['kind'] == 'number' and 'currency' not in expected


def test_deleted_user_is_not_the_system(admin, company):
    contract = _contract(company, 'TH-DEL1')
    _audit(None, 'Contract', contract.pk, {'notes': {'old': '', 'new': 'by a person since deleted'}}, BASE,
           additional={'view': 'ContractViewSet', 'timestamp': 'x'})
    _audit(None, 'Contract', contract.pk, {'notes': {'old': 'x', 'new': 'by a command'}},
           BASE - timedelta(1), additional={'source': 'reconcile_false_expiry'})
    actors = [e['actor'] for e in _all(admin, company) if e['category'] == 'change']
    assert actors == [timeline.DELETED_USER, timeline.SYSTEM_ACTOR]
