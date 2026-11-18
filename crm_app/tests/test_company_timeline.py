"""Company timeline: GET /api/v1/companies/<id>/timeline/ (crm_app/timeline.py).

All names are invented. Companies are created without a music-service account
id so no post-save signal calls an outside API.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from crm_app import timeline
from crm_app.models import (
    AuditLog, CareTouch, Company, Contact, Contract, EmailLog, Invoice, Note, Opportunity,
    OpportunityActivity, Quote, QuoteActivity, Task, TaskComment, Ticket, TicketComment, User,
)

TZ = timezone.get_default_timezone()
BASE = timezone.make_aware(datetime(2026, 11, 10, 9, 30), TZ)


# ---------------------------------------------------------------- fixtures


def _user(username, role='Admin', first='', last=''):
    return User.objects.create(username=username, role=role, first_name=first, last_name=last,
                               email=f'{username}@example.test')


def _company(name='Lumen Bay Test Resort'):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited', country='Thailand')


def _at(obj, when, field='created_at'):
    type(obj).objects.filter(pk=obj.pk).update(**{field: when})
    setattr(obj, field, when)
    return obj


def _contract(company, number, when=BASE, **kw):
    kw.setdefault('status', 'Draft')
    c = Contract.objects.create(company=company, contract_number=number, start_date=date(2026, 1, 1),
                                end_date=date(2026, 12, 31), value=Decimal('108000'), currency='THB', **kw)
    return _at(c, when)


def _quote(company, when=BASE, **kw):
    q = Quote.objects.create(company=company, valid_from=date(2026, 1, 1), valid_until=date(2026, 2, 1),
                             total_value=Decimal('4450'), currency='USD', **kw)
    return _at(q, when)


def _audit(user, model_name, record_id, changes, when, action='UPDATE', additional=None):
    row = AuditLog.objects.create(user=user, action=action, model_name=model_name, record_id=str(record_id),
                                  changes=changes, additional_data=additional)
    return _at(row, when, 'timestamp')


@pytest.fixture
def admin():
    return _user('alex.demo', 'Admin', 'Alex', 'Demo')


@pytest.fixture
def sales():
    return _user('sam.seller', 'Sales', 'Sam', 'Seller')


@pytest.fixture
def company():
    return _company()


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _get(user, company, **params):
    response = _client(user).get(f'/api/v1/companies/{company.pk}/timeline/', params)
    assert response.status_code == 200, response.content
    return response.json()


def _all(user, company, page_size=100, **params):
    """Walk every page; return the events in order."""
    events, cursor, pages = [], None, 0
    while True:
        query = dict(params, page_size=page_size)
        if cursor:
            query['cursor'] = cursor
        data = _get(user, company, **query)
        events.extend(data['results'])
        pages += 1
        assert pages < 500
        if not data['has_more']:
            return events
        cursor = data['next_cursor']


def _types(events):
    return [e['type'] for e in events]


# ---------------------------------------------------------------- basics


def test_empty_company_has_no_events_and_zero_facets(admin, company):
    data = _get(admin, company, facets=1)
    assert data['results'] == []
    assert data['has_more'] is False and data['next_cursor'] is None
    assert set(data['facets']['types']) == set(timeline.CATEGORIES)
    assert all(n == 0 for n in data['facets']['types'].values())
    assert data['facets']['actors'] == []
    assert [c['key'] for c in data['categories']] == list(timeline.CATEGORIES)


def test_requires_sign_in_and_an_existing_company(company):
    assert APIClient().get(f'/api/v1/companies/{company.pk}/timeline/').status_code in (401, 403)
    user = _user('someone')
    assert _client(user).get(f'/api/v1/companies/{uuid.uuid4()}/timeline/').status_code == 404


@pytest.mark.parametrize('params', [
    {'types': 'note,bogus'}, {'from': '2026-13-01'}, {'from': '2026-11-10', 'to': '2026-11-01'},
    {'record': 'zone:' + str(uuid.uuid4())}, {'record': 'contract:not-a-uuid'}, {'actor': 'x'},
    {'cursor': 'not-a-cursor'}, {'page_size': 'ten'},
])
def test_bad_parameters_are_refused(admin, company, params):
    response = _client(admin).get(f'/api/v1/companies/{company.pk}/timeline/', params)
    assert response.status_code == 400
    assert 'error' in response.json()


def test_event_shape(admin, company):
    contact = Contact.objects.create(company=company, name='Mai Tan', email='mai@example.test')
    note = Note.objects.create(company=company, author=admin, contact=contact, note_type='Call',
                               title='Renewal call', text='Discussed the 2027 renewal.')
    _at(note, BASE)
    [event] = _get(admin, company)['results']
    assert event == {
        'id': f'note:{note.pk}', 'type': 'note', 'category': 'note',
        'occurred_at': BASE.isoformat(), 'precision': 'datetime',
        'title': 'Renewal call', 'detail': 'Discussed the 2027 renewal.',
        'actor': {'id': str(admin.pk), 'name': 'Alex Demo', 'kind': 'user'},
        'links': [{'type': 'contact', 'id': str(contact.pk), 'label': 'Mai Tan'}],
        'changes': [],
        'extra': {'note_type': 'Call', 'note_type_label': 'Phone Call', 'priority': 'Medium',
                  'is_private': False},
    }


def test_detail_and_title_are_capped(admin, company):
    opp = Opportunity.objects.create(company=company, name='Long one', owner=admin)
    OpportunityActivity.objects.create(opportunity=opp, user=admin, activity_type='Call', subject='T' * 200,
                                       description='x' * 5000)
    [event] = _get(admin, company, types='opportunity')['results'][:1]
    assert len(event['title']) == timeline.TITLE_MAX and event['title'].endswith('…')
    assert len(event['detail']) == timeline.DETAIL_MAX


# ---------------------------------------------------------------- ordering and paging


def _mixed_history(company, admin, when):
    """One event in several sources at exactly the same instant."""
    contact = Contact.objects.create(company=company, name='Ben Archer', email='ben@example.test')
    _at(Note.objects.create(company=company, author=admin, text='same instant'), when)
    _at(Task.objects.create(company=company, created_by=admin, title='Call back'), when)
    EmailLog.objects.create(company=company, contact=contact, email_type='manual', from_email='crm@example.test',
                            to_email='ben@example.test', subject='Hello', body_html='', body_text='',
                            status='sent', sent_at=when)
    CareTouch.objects.create(company=company, mailbox='care@example.test', occurred_at=when, kind='check_in',
                             summary='Quarterly check-in', source='send', idempotency_key=str(uuid.uuid4()),
                             recorded_by='cara', payload_sha256='0' * 64)
    _quote(company, when=when, created_by=admin)
    _contract(company, 'TH-CT26901', when=when)
    t = Ticket.objects.create(company=company, subject='Zone offline', description='Lobby is silent',
                              created_by=admin)
    _at(t, when)
    opp = Opportunity.objects.create(company=company, name='Add two zones', owner=admin)
    _at(opp, when)


def test_events_from_all_sources_are_newest_first_with_stable_ties(admin, company):
    _mixed_history(company, admin, BASE)
    later = Note.objects.create(company=company, author=admin, text='later')
    _at(later, BASE + timedelta(seconds=1))
    earlier = Note.objects.create(company=company, author=admin, text='earlier')
    _at(earlier, BASE - timedelta(microseconds=1))

    events = _get(admin, company)['results']
    keys = [(datetime.fromisoformat(e['occurred_at']), e['id']) for e in events]
    assert keys == sorted(keys, reverse=True)
    assert events[0]['detail'] == 'later' and events[-1]['detail'] == 'earlier'
    same = [e for e in events if datetime.fromisoformat(e['occurred_at']) == BASE]
    assert len({e['id'].split(':')[0] for e in same}) >= 8
    assert [e['id'] for e in same] == sorted((e['id'] for e in same), reverse=True)


@pytest.mark.parametrize('page_size', [1, 2, 3, 7])
def test_paging_through_identical_timestamps_returns_every_event_once(admin, company, page_size):
    _mixed_history(company, admin, BASE)
    for i in range(5):  # five notes at the same instant: ties inside one source too
        _at(Note.objects.create(company=company, author=admin, text=f'n{i}'), BASE)
    everything = _get(admin, company, page_size=100)['results']
    paged = _all(admin, company, page_size=page_size)
    assert [e['id'] for e in paged] == [e['id'] for e in everything]
    assert len({e['id'] for e in paged}) == len(paged)


def test_new_events_arriving_between_pages_do_not_shift_later_pages(admin, company):
    for i in range(10):
        _at(Note.objects.create(company=company, author=admin, text=f'old {i}'), BASE - timedelta(minutes=i))
    first = _get(admin, company, page_size=4)
    assert [e['detail'] for e in first['results']] == ['old 0', 'old 1', 'old 2', 'old 3']

    # New activity lands at the top, and one more at the very instant of the cursor.
    for i in range(3):
        _at(Note.objects.create(company=company, author=admin, text=f'new {i}'), BASE + timedelta(minutes=i + 1))
    EmailLog.objects.create(company=company, email_type='manual', from_email='crm@example.test',
                            to_email='x@example.test', subject='new mail', body_html='', body_text='',
                            status='sent', sent_at=timezone.now())

    rest, cursor = [], first['next_cursor']
    while cursor:
        page = _get(admin, company, page_size=4, cursor=cursor)
        rest.extend(e['detail'] for e in page['results'])
        cursor = page['next_cursor']
    assert rest == [f'old {i}' for i in range(4, 10)]


def test_date_only_events_sit_at_the_end_of_their_day_in_stage_order_and_page_correctly(admin, company):
    contract = _contract(company, 'TH-CT26902', status='Active',
                         when=timezone.make_aware(datetime(2026, 11, 10, 15, 30), TZ))  # created that afternoon
    Contract.objects.filter(pk=contract.pk).update(signed_date=date(2026, 11, 10), sent_date=date(2026, 11, 10))
    late = Note.objects.create(company=company, author=admin, text='late')
    _at(late, timezone.make_aware(datetime(2026, 11, 10, 23, 59, 59), TZ))
    next_morning = Note.objects.create(company=company, author=admin, text='next morning')
    _at(next_morning, timezone.make_aware(datetime(2026, 11, 11, 0, 0, 0), TZ))
    events = _get(admin, company)['results']
    # Newest first: next day, then the 10th's date-only facts (signed after sent), then its timed events.
    assert [e['detail'] or e['type'] for e in events] == [
        'next morning', 'contract_signed', 'contract_sent', 'late', 'contract_created']
    signed = events[1]
    assert signed['precision'] == 'date' and signed['date'] == '2026-11-10'
    end_of_day = timezone.make_aware(datetime(2026, 11, 11), TZ)
    assert end_of_day - timedelta(microseconds=10) < datetime.fromisoformat(signed['occurred_at']) < end_of_day
    for size in (1, 2, 3):
        assert [e['id'] for e in _all(admin, company, page_size=size)] == [e['id'] for e in events]


# ---------------------------------------------------------------- filters


def test_type_filter_and_facet_counts(admin, company):
    _mixed_history(company, admin, BASE)
    data = _get(admin, company, types='note,email', facets=1)
    assert {e['category'] for e in data['results']} == {'note', 'email'}
    types = data['facets']['types']
    # counts ignore the type filter so every chip shows its number
    assert types['note'] == 1 and types['email'] == 1 and types['care'] == 1 and types['ticket'] == 1
    assert types['quote'] == 1 and types['contract'] == 1 and types['opportunity'] == 1 and types['task'] == 1
    total = sum(types.values())
    assert total == len(_all(admin, company))


def test_date_range_filter_is_inclusive_for_times_and_dates(admin, company):
    day = lambda d, h=12: timezone.make_aware(datetime(2026, 11, d, h), TZ)  # noqa: E731
    for d in (8, 9, 10, 11):
        _at(Note.objects.create(company=company, author=admin, text=f'note {d}'), day(d))
    late = Note.objects.create(company=company, author=admin, text='late on the 10th')
    _at(late, timezone.make_aware(datetime(2026, 11, 10, 23, 59, 59), TZ))
    c = _contract(company, 'TH-CT26903', when=day(1))
    Contract.objects.filter(pk=c.pk).update(signed_date=date(2026, 11, 10))
    Contract.objects.filter(pk=c.pk).update(sent_date=date(2026, 11, 11))
    events = _all(admin, company, **{'from': '2026-11-09', 'to': '2026-11-10'})
    assert [e['detail'] or e['type'] for e in events] == [
        'contract_signed', 'late on the 10th', 'note 10', 'note 9']


def test_record_filter_keeps_one_contracts_events(admin, company):
    old = _contract(company, 'TH-CT25001', when=BASE - timedelta(days=400), status='Active')
    other = _contract(company, 'TH-CT26904', when=BASE - timedelta(days=10))
    renewal = _contract(company, 'TH-CT26905', when=BASE - timedelta(days=5), renewed_from=old)
    Invoice.objects.create(company=company, contract=old, invoice_number='INV-T-1', status='Sent',
                           issue_date=date(2025, 1, 5), due_date=date(2025, 2, 5), amount=Decimal('100'),
                           total_amount=Decimal('100'), currency='THB')
    Task.objects.create(company=company, created_by=admin, title='Chase signature', related_contract=old)
    Task.objects.create(company=company, created_by=admin, title='Unrelated task')
    EmailLog.objects.create(company=company, contract=old, email_type='renewal', from_email='crm@example.test',
                            to_email='x@example.test', subject='Renewal reminder', body_html='', body_text='',
                            status='sent', sent_at=BASE)
    _audit(admin, 'Contract', old.pk, {'end_date': {'old': '2025-12-31', 'new': '2026-12-31'}}, BASE)
    _audit(admin, 'Contract', other.pk, {'end_date': {'old': '2025-12-31', 'new': '2026-12-31'}}, BASE)

    events = _all(admin, company, record=f'contract:{old.pk}')
    ids = {link['id'] for e in events for link in e['links']}
    assert str(old.pk) in ids and str(other.pk) not in ids
    assert set(_types(events)) == {'contract_created', 'contract_renewal_created', 'invoice_issued',
                                   'task_created', 'email_sent', 'field_change'}
    assert any(e['id'] == f'contract_created:{renewal.pk}' for e in events)
    assert not any('Unrelated' in e['title'] for e in events)


def test_record_filter_cannot_reach_another_companys_records(admin, company):
    other_company = _company('Northwind Test Roasters')
    foreign = _contract(other_company, 'HK-CT26906')
    _audit(admin, 'Contract', foreign.pk, {'notes': {'old': '', 'new': 'secret plan'}}, BASE)
    assert _all(admin, company, record=f'contract:{foreign.pk}') == []
    assert _all(admin, company) == []


def test_actor_filter_and_actor_facets(admin, sales, company):
    _at(Note.objects.create(company=company, author=admin, text='by admin'), BASE)
    _at(Note.objects.create(company=company, author=sales, text='by sales'), BASE)
    _at(Task.objects.create(company=company, created_by=sales, title='Sales task'), BASE)
    CareTouch.objects.create(company=company, mailbox='care@example.test', occurred_at=BASE, kind='check_in',
                             summary='Care', source='send', idempotency_key='k1', recorded_by='cara',
                             payload_sha256='0' * 64)
    data = _get(admin, company, actor=str(sales.pk), facets=1)
    assert [e['actor']['name'] for e in data['results']] == ['Sam Seller', 'Sam Seller']
    assert data['facets']['types']['note'] == 1 and data['facets']['types']['care'] == 0
    actors = {a['name']: a['count'] for a in data['facets']['actors']}
    assert actors == {'Sam Seller': 2, 'Alex Demo': 1}


def test_free_text_search(admin, company):
    contact = Contact.objects.create(company=company, name='Kanya Lim', email='kanya@example.test')
    Note.objects.create(company=company, author=admin, title='Sound check', text='Lobby speakers buzzing')
    Note.objects.create(company=company, author=admin, title='Other', text='Nothing here')
    EmailLog.objects.create(company=company, contact=contact, email_type='manual', from_email='crm@example.test',
                            to_email='kanya@example.test', subject='Invoice reminder', body_html='BUZZING body',
                            body_text='BUZZING body', status='sent', sent_at=BASE)
    contract = _contract(company, 'TH-CT26907')
    _audit(admin, 'Contract', contract.pk, {'notes': {'old': '', 'new': 'Speakers buzzing in lobby'}}, BASE)
    hits = _all(admin, company, q='buzzing')
    assert sorted(_types(hits)) == ['field_change', 'note']  # email bodies are never searched or shown
    assert [e['title'] for e in _all(admin, company, q='kanya')] == ['Email sent: Invoice reminder']
    assert {e['type'] for e in _all(admin, company, q='TH-CT26907')} == {'contract_created', 'field_change'}


# ---------------------------------------------------------------- source adapters


def test_notes_privacy_and_automatic_email_notes(admin, sales, company):
    other = _user('pim.other', 'Sales')
    Note.objects.create(company=company, author=other, text='private to pim', is_private=True)
    Note.objects.create(company=company, author=sales, text='private to sam', is_private=True)
    Note.objects.create(company=company, author=None, note_type='Email', title='Email sent: Renewal',
                        text='automatic')
    Note.objects.create(company=company, author=admin, note_type='Email', title='Email sent: by hand',
                        text='typed by a person')
    seen_by_sales = {e['detail'] for e in _all(sales, company)}
    assert seen_by_sales == {'private to sam', 'typed by a person'}
    seen_by_admin = {e['detail'] for e in _all(admin, company)}
    assert seen_by_admin == {'private to pim', 'private to sam', 'typed by a person'}


def test_task_created_completed_and_comments(admin, sales, company):
    open_task = _at(Task.objects.create(company=company, created_by=admin, assigned_to=sales,
                                        title='Send renewal quote'), BASE - timedelta(days=2))
    done = _at(Task.objects.create(company=company, created_by=admin, title='Check zones', status='Done'),
               BASE - timedelta(days=1))
    Task.objects.filter(pk=done.pk).update(completed_at=BASE)
    comment = TaskComment.objects.create(task=open_task, user=sales, comment='Waiting for the GM')
    _at(comment, BASE + timedelta(hours=1))
    events = _all(admin, company)
    assert _types(events) == ['task_comment', 'task_completed', 'task_created', 'task_created']
    assert events[0]['actor']['name'] == 'Sam Seller' and events[0]['detail'] == 'Waiting for the GM'
    assert events[1]['actor'] is None and events[1]['title'] == 'Task completed: Check zones'
    assert events[3]['extra']['assigned_to'] == 'Sam Seller'
    assert events[3]['links'][0] == {'type': 'task', 'id': str(open_task.pk), 'label': 'Send renewal quote'}


def test_email_log_uses_send_time_and_never_exposes_the_body(admin, company):
    queued = EmailLog.objects.create(company=company, email_type='quote_send', from_email='crm@example.test',
                                     to_email='gm@example.test', subject='Your quote', body_html='<p>SECRET</p>',
                                     body_text='SECRET', status='pending')
    _at(queued, BASE - timedelta(hours=1))
    EmailLog.objects.create(company=company, email_type='renewal', from_email='crm@example.test',
                            to_email='gm@example.test', subject='Renewal', body_html='SECRET', body_text='SECRET',
                            status='failed', sent_at=BASE, error_message='SMTP refused')
    events = _all(admin, company)
    assert [(e['type'], e['title']) for e in events] == [
        ('email_failed', 'Email failed: Renewal'), ('email_sent', 'Email queued: Your quote')]
    assert events[1]['occurred_at'] == (BASE - timedelta(hours=1)).isoformat()
    payload = str(events)
    assert 'SECRET' not in payload and 'SMTP refused' not in payload and 'crm@example.test' not in payload
    assert events[0]['actor'] == timeline.SYSTEM_ACTOR
    assert events[0]['detail'] == 'To gm@example.test'  # no contact record, so the address the UI shows


def test_field_labels_read_as_words(admin, company):
    _audit(admin, 'Company', company.pk, {'address_line1': {'old': '', 'new': '88 Example Road'}}, BASE)
    [event] = _all(admin, company)
    assert event['changes'][0]['label'] == 'Address line 1'
    assert event['title'] == 'Company details updated: address line 1'


def test_care_touch_shows_only_what_the_care_card_shows(admin, company):
    CareTouch.objects.create(company=company, mailbox='care-mailbox@example.test', gmail_thread_id='THREAD-1',
                             gmail_message_id='MSG-1', occurred_at=BASE, kind='client_reply', outcome='request',
                             summary='Asked for a Christmas playlist', source='gmail_backfill',
                             idempotency_key='IDEM-1', recorded_by='cara', payload_sha256='f' * 64)
    [event] = _get(admin, company)['results']
    assert event['title'] == 'Asked for a Christmas playlist' and event['type'] == 'care_touch'
    assert event['extra'] == {'kind': 'client_reply', 'kind_label': 'Client reply', 'outcome': 'request',
                              'outcome_label': 'Request'}
    for hidden in ('care-mailbox', 'THREAD-1', 'MSG-1', 'IDEM-1', 'f' * 64, 'gmail_backfill'):
        assert hidden not in str(event)


def test_care_summary_write_fields_never_appear(admin, company):
    Company.objects.filter(pk=company.pk).update(care_summary='All good', care_summary_updated_by='cara',
                                                 care_summary_updated_at=BASE)
    _audit(admin, 'Company', company.pk, {'care_summary_updated_by': {'old': '', 'new': 'cara'},
                                          'care_summary_updated_at': {'old': None, 'new': BASE.isoformat()},
                                          'updated_at': {'old': 'a', 'new': 'b'}}, BASE)
    assert _all(admin, company) == []


def test_quote_lifecycle_from_activity_with_date_fallbacks(admin, company):
    quote = _quote(company, when=BASE - timedelta(days=10), created_by=admin)
    _at(QuoteActivity.objects.create(quote=quote, user=admin, activity_type='Created', description='x'),
        BASE - timedelta(days=10))
    _at(QuoteActivity.objects.create(quote=quote, user=admin, activity_type='Updated', description='x'),
        BASE - timedelta(days=9))
    _at(QuoteActivity.objects.create(quote=quote, user=admin, activity_type='Sent', description='x'),
        BASE - timedelta(days=8))
    # sent_date has a matching activity (no duplicate); accepted_date has none (imported quote).
    Quote.objects.filter(pk=quote.pk).update(status='Accepted', sent_date=date(2026, 11, 2),
                                             accepted_date=date(2026, 11, 5))
    events = _all(admin, company)
    assert _types(events) == ['quote_accepted', 'quote_sent', 'quote_created']
    accepted, sent, created = events
    assert accepted['precision'] == 'date' and accepted['actor'] is None
    assert sent['precision'] == 'datetime' and sent['actor']['name'] == 'Alex Demo'
    assert created['extra']['money'] == {'amount': '4450.00', 'currency': 'USD'}
    assert created['links'][0]['type'] == 'quote'


def test_contract_lifecycle_times(admin, company):
    old = _contract(company, 'TH-CT25002', when=BASE - timedelta(days=365), status='Active')
    Contract.objects.filter(pk=old.pk).update(sent_date=date(2025, 11, 12), signed_date=date(2025, 11, 20))
    new = _contract(company, 'TH-CT26908', when=BASE - timedelta(days=20), renewed_from=old)
    Contract.objects.filter(pk=new.pk).update(sent_date=date(2026, 11, 1))
    # The website marked the renewal Sent (audited, exact time), then it became Active.
    _audit(admin, 'Contract', new.pk, {'status': {'old': 'Draft', 'new': 'Sent'},
                                       'sent_date': {'old': None, 'new': '2026-11-01'},
                                       'contract_number': {'old': 'DRAFT-0001', 'new': 'TH-CT26908'},
                                       'updated_at': {'old': 'a', 'new': 'b'}},
           timezone.make_aware(datetime(2026, 11, 1, 14, 5), TZ))
    _audit(None, 'Contract', old.pk, {'status': {'before': 'Active', 'after': 'Renewed'}}, BASE,
           additional={'action': 'Predecessor closed: renewal successor became Active'})
    events = _all(admin, company)
    assert _types(events) == ['contract_status', 'contract_status', 'contract_renewal_created',
                              'contract_signed', 'contract_sent', 'contract_created']
    assert 'contract_sent:' + str(new.pk) not in [e['id'] for e in events]  # audited instead
    renewed, sent = events[0], events[1]
    assert renewed['title'] == 'Contract TH-CT25002: Active → Renewed'
    assert renewed['actor'] == timeline.SYSTEM_ACTOR
    assert renewed['extra']['reason'] == 'Predecessor closed: renewal successor became Active'
    assert sent['title'] == 'Contract TH-CT26908: Draft → Sent'
    assert sent['changes'] == [{'field': 'contract_number', 'label': 'Contract number', 'kind': 'text',
                                'old': 'DRAFT-0001', 'new': 'TH-CT26908'}]
    # The old term's sent_date has no audited status change, so it shows as a date-only event.
    assert events[4]['title'] == 'Contract TH-CT25002 sent' and events[4]['precision'] == 'date'


def test_contract_sent_date_shows_for_users_who_cannot_see_the_audit_log(admin, sales, company):
    c = _contract(company, 'TH-CT26909', when=BASE - timedelta(days=2))
    Contract.objects.filter(pk=c.pk).update(sent_date=date(2026, 11, 9))
    _audit(admin, 'Contract', c.pk, {'status': {'old': 'Draft', 'new': 'Sent'}}, BASE)
    assert 'contract_sent' not in _types(_all(admin, company))
    sales_view = _types(_all(sales, company))
    assert 'contract_sent' in sales_view and 'contract_status' not in sales_view


def test_invoices_issued_and_paid(admin, company):
    contract = _contract(company, 'TH-CT26910')
    common = dict(company=company, contract=contract, due_date=date(2026, 12, 1), amount=Decimal('5000'),
                  total_amount=Decimal('5350'), currency='THB')
    Invoice.objects.create(invoice_number='INV-T-DRAFT', status='Draft', issue_date=date(2026, 11, 1), **common)
    Invoice.objects.create(invoice_number='INV-T-PAID', status='Paid', issue_date=date(2026, 11, 2),
                           paid_date=date(2026, 11, 8), **common)
    events = [e for e in _all(admin, company) if e['category'] == 'invoice']
    assert [e['title'] for e in events] == ['Invoice INV-T-PAID paid', 'Invoice INV-T-PAID issued']
    assert events[0]['links'][0]['contract_id'] == str(contract.pk)
    assert events[0]['extra']['money'] == {'amount': '5000.00', 'currency': 'THB'}


def test_opportunity_created_activities_and_stage_changes(admin, company):
    opp = _at(Opportunity.objects.create(company=company, name='Rooftop bar upsell', owner=admin),
              BASE - timedelta(days=3))
    act = OpportunityActivity.objects.create(opportunity=opp, user=admin, activity_type='Demo',
                                             subject='Played the evening mix', description='GM liked it',
                                             outcome='Positive', next_steps='Send quote')
    _at(act, BASE - timedelta(days=2))
    _audit(admin, 'Opportunity', opp.pk, {'stage': {'old': 'Contacted', 'new': 'Quotation Sent'},
                                          'stage_changed_at': {'old': 'a', 'new': 'b'},
                                          'probability': {'old': 10, 'new': 50}}, BASE)
    events = _all(admin, company)
    assert _types(events) == ['opportunity_stage', 'opportunity_activity', 'opportunity_created']
    stage, activity, _ = events
    assert stage['title'] == 'Opportunity Rooftop bar upsell: Contacted → Quotation Sent'
    assert [c['field'] for c in stage['changes']] == ['probability']
    assert activity['title'] == 'Product Demo: Played the evening mix'
    assert activity['detail'] == 'GM liked it\n\nOutcome: Positive\n\nNext steps: Send quote'
    only_opp = _all(admin, company, record=f'opportunity:{opp.pk}')
    assert _types(only_opp) == _types(events)


def test_ticket_opened_comments_resolved_closed(admin, company):
    t = Ticket.objects.create(company=company, subject='Lobby silent', description='No music since 9am',
                              created_by=admin)
    _at(t, BASE - timedelta(hours=5))
    _at(TicketComment.objects.create(ticket=t, author=admin, text='Rebooted the player'),
        BASE - timedelta(hours=4))
    _at(TicketComment.objects.create(ticket=t, author=admin, text='Vendor called', is_internal=True),
        BASE - timedelta(hours=3))
    Ticket.objects.filter(pk=t.pk).update(resolved_at=BASE - timedelta(hours=2), closed_at=BASE)
    events = _all(admin, company)
    assert [e['title'] for e in events] == [
        'Ticket closed: Lobby silent', 'Ticket resolved: Lobby silent', 'Internal note on ticket: Lobby silent',
        'Reply on ticket: Lobby silent', 'Ticket opened: Lobby silent']
    assert events[2]['extra'] == {'is_internal': True}


# ---------------------------------------------------------------- audit grouping


def test_one_event_per_save_with_before_and_after_and_hidden_system_fields(admin, company):
    contact = Contact.objects.create(company=company, name='Olivia Park', email='olivia@example.test')
    contract = _contract(company, 'TH-CT26911', when=BASE - timedelta(days=50))
    _audit(admin, 'Contract', contract.pk, {
        'end_date': {'old': '2026-12-31', 'new': '2027-12-31'},
        'value': {'old': '100000.00', 'new': '108000.00'},
        'auto_renew': {'old': False, 'new': True},
        'contract_type': {'old': 'Annual', 'new': 'Custom'},
        'updated_at': {'old': '2026-11-01T00:00:00Z', 'new': '2026-11-10T00:00:00Z'},
        'days_until_expiry': {'old': 10, 'new': 400},
        'line_items': {'old': [{'x': 1}], 'new': [{'x': 2}]},
        'contacts': {'old': [], 'new': [1]},
    }, BASE)
    _audit(admin, 'Contract', contract.pk, {'updated_at': {'old': 'a', 'new': 'b'},
                                            'days_until_expiry': {'old': 1, 'new': 2}}, BASE)  # noise only
    _audit(admin, 'Contact', contact.pk, {'title': {'from': '', 'to': 'General Manager'}}, BASE - timedelta(1))
    changes = [e for e in _all(admin, company) if e['category'] == 'change']
    assert len(changes) == 2
    event = changes[0]
    assert event['title'] == 'TH-CT26911 updated: auto renew, contract type, end date …'
    assert event['changes'] == [
        {'field': 'auto_renew', 'label': 'Auto renew', 'kind': 'bool', 'old': 'No', 'new': 'Yes'},
        {'field': 'contract_type', 'label': 'Contract type', 'kind': 'text', 'old': 'Annual Subscription',
         'new': 'Custom Agreement'},
        {'field': 'end_date', 'label': 'End date', 'kind': 'date', 'old': '2026-12-31', 'new': '2027-12-31'},
        {'field': 'line_items', 'label': 'Line items', 'kind': 'collection', 'old': None, 'new': None},
        {'field': 'value', 'label': 'Value', 'kind': 'money', 'old': '100000.00', 'new': '108000.00',
         'currency': 'THB', 'old_currency': 'THB'},
    ]
    assert 'Changed End date from 2026-12-31 to 2027-12-31' in event['detail']
    assert event['links'] == [{'type': 'contract', 'id': str(contract.pk), 'label': 'TH-CT26911'}]
    assert changes[1]['title'] == 'Olivia Park updated: title'
    assert changes[1]['changes'][0]['new'] == 'General Manager'


def test_reference_changes_show_labels_and_users_never_email_addresses(admin, company):
    old_contact = Contact.objects.create(company=company, name='Hiro Ito', email='hiro@example.test')
    new_contact = Contact.objects.create(company=company, name='Uma Santos', email='uma@example.test')
    quote = _quote(company)
    owner = _user('new.owner@example.test', 'Sales')
    opp = Opportunity.objects.create(company=company, name='Spa zones', owner=admin)
    _audit(admin, 'Quote', quote.pk, {'contact': {'old': str(old_contact.pk), 'new': str(new_contact.pk)},
                                      'status': {'old': 'Draft', 'new': 'Sent'},
                                      'sent_date': {'old': None, 'new': '2026-11-10'}}, BASE)
    _audit(admin, 'Opportunity', opp.pk, {'owner': {'old': str(admin.pk), 'new': str(owner.pk)}}, BASE)
    events = [e for e in _all(admin, company) if e['category'] == 'change']
    by_model = {e['extra']['model']: e for e in events}
    assert by_model['Quote']['changes'] == [
        {'field': 'contact', 'label': 'Contact', 'kind': 'ref', 'old': 'Hiro Ito', 'new': 'Uma Santos'}]
    assert by_model['Opportunity']['changes'][0]['new'] == 'new.owner'
    assert 'example.test' not in str(events)


def test_audit_rows_created_and_deleted_records(admin, company):
    contact = Contact.objects.create(company=company, name='Rosa Reyes', email='rosa@example.test')
    _audit(admin, 'Contact', contact.pk, None, BASE - timedelta(hours=2), action='CREATE')
    gone = uuid.uuid4()
    _audit(admin, 'Contact', gone, None, BASE, action='DELETE',
           additional={'via': 'mcp', 'deleted': {'id': str(gone), 'model': 'Contact', 'name': 'Leo Chen',
                                                 'company_id': str(company.pk)}})
    _audit(admin, 'Contract', uuid.uuid4(), None, BASE, action='DELETE',
           additional={'deleted': {'company_id': str(uuid.uuid4())}})  # another company's record
    _audit(admin, 'Contact', contact.pk, None, BASE, action='VIEW')
    events = _all(admin, company)
    assert [(e['type'], e['title']) for e in events] == [
        ('record_deleted', 'Contact deleted: Leo Chen'), ('record_created', 'Contact added: Rosa Reyes')]
    assert events[0]['extra']['via'] == 'mcp' and events[0]['links'] == []


def test_agents_are_named_as_agents(company):
    cira = _user('cira', 'Admin')
    contract = _contract(company, 'TH-CT26912')
    _audit(cira, 'Contract', contract.pk, {'notes': {'old': '', 'new': 'Checked by Cira'}}, BASE,
           additional={'via': 'mcp'})
    [event] = [e for e in _all(cira, company) if e['category'] == 'change']
    assert event['actor'] == {'id': str(cira.pk), 'name': 'Cira', 'kind': 'agent'}


def test_field_changes_are_admin_only_like_the_audit_log_api(admin, sales, company):
    contract = _contract(company, 'TH-CT26913')
    _audit(admin, 'Contract', contract.pk, {'notes': {'old': '', 'new': 'x'}}, BASE)
    _audit(admin, 'Contract', contract.pk, {'status': {'old': 'Draft', 'new': 'Active'}}, BASE)
    assert _client(sales).get('/api/v1/audit-logs/').status_code == 403
    sales_types = _types(_all(sales, company))
    assert 'field_change' not in sales_types and 'contract_status' not in sales_types
    facets = _get(sales, company, facets=1)['facets']['types']
    assert facets['change'] == 0
    assert 'field_change' in _types(_all(admin, company))


# ---------------------------------------------------------------- registry


class _MemorySource(timeline.TimelineSource):
    """A non-database source, standing in for a future one such as captured mail."""

    key = 'zz_memory'
    category = 'email'

    def __init__(self, moments):
        self.moments = moments

    def _events(self, ctx):
        return [timeline.TimelineEvent(id=f'{self.key}:{i:04d}', type='captured_mail', category=self.category,
                                       occurred_at=m, title=f'Captured {i}') for i, m in enumerate(self.moments)]

    def fetch(self, ctx, cursor, limit):
        events = sorted(self._events(ctx), key=lambda e: e.sort_key, reverse=True)
        if cursor is not None:
            events = [e for e in events if e.sort_key < (cursor.occurred_at, cursor.event_id)]
        page = events[:limit]
        return timeline.SourceResult(page, page[-1].sort_key if len(events) > limit else None)

    def facet_rows(self, ctx):
        return [(None, len(self.moments))]


class _AgentActivityStandIn(timeline.RowSource):
    """An ORM source registered the way agent_inbox's Activity adapter will be."""

    key = 'agent_activity'
    category = 'note'
    model = Note
    actor_field = 'author'
    search_fields = ('text',)
    record_paths = {'contact': 'contact'}

    def extra_q(self, ctx):
        return Q_tags_agent

    def to_event(self, row, ctx):
        return self.event(row, ctx, type='agent_activity', title=f'Agent logged: {row.text}',
                          actor=timeline.actor_for_user(row.author))


from django.db.models import Q  # noqa: E402

Q_tags_agent = Q(tags='agent-activity')


@pytest.fixture
def extra_sources():
    added = []

    def add(source):
        timeline.registry.register(source)
        added.append(source.key)
        return source

    yield add
    for key in added:
        timeline.registry.unregister(key)


def test_a_new_source_can_be_registered_and_is_merged_and_paged(admin, company, extra_sources):
    for i in range(3):
        _at(Note.objects.create(company=company, author=admin, text=f'note {i}'), BASE - timedelta(minutes=i))
    extra_sources(_MemorySource([BASE - timedelta(minutes=i, seconds=30) for i in range(3)] + [BASE]))
    extra_sources(_AgentActivityStandIn())
    _at(Note.objects.create(company=company, author=admin, text='called the GM', tags='agent-activity'),
        BASE + timedelta(minutes=5))
    events = _all(admin, company, page_size=2)
    titles = [e['title'] for e in events]
    # The stand-in reads the notes table, so the note source shows the same row too.
    assert set(titles[:2]) == {'Agent logged: called the GM', 'General note'}
    assert titles.count('Agent logged: called the GM') == 1
    assert sum(t.startswith('Captured') for t in titles) == 4
    keys = [(datetime.fromisoformat(e['occurred_at']), e['id']) for e in events]
    assert keys == sorted(keys, reverse=True) and len(set(keys)) == len(keys)
    assert _get(admin, company, facets=1)['facets']['types']['email'] == 4
    # Type filters apply to registered sources too.
    assert all(e['category'] == 'note' for e in _all(admin, company, types='note'))


def test_registry_rejects_bad_keys_duplicates_and_unknown_categories():
    class Bad(timeline.TimelineSource):
        key, category = 'Bad-Key', 'note'

    with pytest.raises(ValueError):
        timeline.registry.register(Bad())

    class Dup(timeline.TimelineSource):
        key, category = 'note', 'note'

    with pytest.raises(ValueError):
        timeline.registry.register(Dup())

    class Cat(timeline.TimelineSource):
        key, category = 'new_thing', 'nonsense'

    with pytest.raises(ValueError):
        timeline.registry.register(Cat())


def test_cursor_round_trip():
    cursor = timeline.Cursor(BASE, f'note:{uuid.uuid4()}')
    assert timeline.Cursor.decode(cursor.encode()) == cursor
    with pytest.raises(ValueError):
        timeline.Cursor.decode('e30')  # "{}"


# ---------------------------------------------------------------- performance


def _seed_history(company, admin, n):
    """n events in each of the busiest sources, spread over two years."""
    contact = Contact.objects.create(company=company, name='Grace Hart', email=f'grace{n}@example.test')
    start = BASE - timedelta(days=730)
    step = timedelta(days=730) / max(n, 1)
    Note.objects.bulk_create([Note(company=company, author=admin, contact=contact, text=f'n{i}') for i in range(n)])
    EmailLog.objects.bulk_create([
        EmailLog(company=company, contact=contact, email_type='manual', from_email='crm@example.test',
                 to_email='g@example.test', subject=f's{i}', body_html='', body_text='', status='sent',
                 sent_at=start + step * i, tracking_token=uuid.uuid4().hex) for i in range(n)])
    CareTouch.objects.bulk_create([
        CareTouch(company=company, mailbox='care@example.test', occurred_at=start + step * i, kind='check_in',
                  summary=f'c{i}', source='send', idempotency_key=uuid.uuid4().hex, recorded_by='cara',
                  payload_sha256='0' * 64) for i in range(n)])
    contracts = Contract.objects.bulk_create([
        Contract(company=company, contract_number=f'T-{n}-{i}', start_date=date(2025, 1, 1), value=Decimal('1'),
                 currency='THB', status='Active', sent_date=(start + step * i).date()) for i in range(max(1, n // 10))])
    AuditLog.objects.bulk_create([
        AuditLog(user=admin, action='UPDATE', model_name='Contract', record_id=str(contracts[i % len(contracts)].pk),
                 changes={'notes': {'old': '', 'new': f'v{i}'}}) for i in range(n)])
    tasks = Task.objects.bulk_create([Task(company=company, created_by=admin, title=f't{i}')
                                     for i in range(max(1, n // 2))])
    TaskComment.objects.bulk_create([TaskComment(task=tasks[i % len(tasks)], user=admin, comment=f'tc{i}')
                                     for i in range(n // 2)])


def _page_queries(user, company, **params):
    client = _client(user)
    url = f'/api/v1/companies/{company.pk}/timeline/'
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url, params)
    assert response.status_code == 200
    return len(ctx.captured_queries), response.json()


# One query per registered source (26), the four label maps the audit adapters
# share (contacts, contracts, quotes, opportunities) and the company lookup.
# Field changes that name a user add one user lookup. Registering a new source
# adds exactly one; anything else means a per-row query crept in.
QUERIES_PER_PAGE = 31
MAX_QUERIES_PER_PAGE = QUERIES_PER_PAGE + 1


def test_query_count_per_page_is_fixed_whatever_the_history(admin):
    small, large = _company('Small Test Co'), _company('Large Test Co')
    _seed_history(small, admin, 5)
    _seed_history(large, admin, 600)
    n_small, _ = _page_queries(admin, small)
    n_large, page = _page_queries(admin, large)
    assert n_small == n_large == QUERIES_PER_PAGE
    n_next, _ = _page_queries(admin, large, cursor=page['next_cursor'])
    assert n_next == n_large
    n_facets, _ = _page_queries(admin, large, facets=1)
    assert n_facets <= 2 * MAX_QUERIES_PER_PAGE


def test_thousands_of_events_page_in_order_without_loading_everything(admin):
    company = _company('Busy Test Hotel')
    _seed_history(company, admin, 700)  # about 3,000 events across six sources
    expected = sum(_get(admin, company, facets=1)['facets']['types'].values())
    assert expected > 3000
    seen, cursor, last_key, pages = set(), None, None, 0
    while True:
        params = {'page_size': 100}
        if cursor:
            params['cursor'] = cursor
        n, data = _page_queries(admin, company, **params)
        assert n <= MAX_QUERIES_PER_PAGE
        for event in data['results']:
            key = (datetime.fromisoformat(event['occurred_at']), event['id'])
            assert last_key is None or key < last_key
            last_key = key
            seen.add(event['id'])
        pages += 1
        if not data['has_more']:
            break
        cursor = data['next_cursor']
    assert len(seen) == expected
    assert pages >= expected // 100
