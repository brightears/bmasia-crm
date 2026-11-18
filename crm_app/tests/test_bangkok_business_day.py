"""Dates the CRM stamps or compares against "today" use the Bangkok day, not the UTC date.

Each check runs at three instants:
- 00:30 in Bangkok on 1 January 2027: the UTC date is still 31 December 2026, so a
  UTC-date stamp lands on the previous day, month and year;
- 00:30 in Bangkok on an ordinary day (19 November 2026): the UTC date is the 18th;
- 23:30 in Bangkok on 31 December 2026: both dates agree, so nothing may move forward.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from crm_app.admin import QuoteAdmin
from crm_app.dates import business_today
from crm_app.models import (
    ContractZone, DocumentSequence, KBArticle, Quote, Ticket,
)
from crm_app.services.ar_aging_service import ARAgingService
from crm_app.services.contract_lifecycle import handover_end_date
from crm_app.tests.factories import (
    CompanyFactory, ContractFactory, ContractZoneFactory, InvoiceFactory, OpportunityFactory,
    UserFactory, ZoneFactory,
)

BANGKOK_DAYS = [
    pytest.param(("2026-12-31T17:30:00+00:00", date(2027, 1, 1)), id="00:30-bangkok-new-year"),
    pytest.param(("2026-11-18T17:30:00+00:00", date(2026, 11, 19)), id="00:30-bangkok"),
    pytest.param(("2026-12-31T16:30:00+00:00", date(2026, 12, 31)), id="23:30-bangkok"),
]


@pytest.fixture(params=BANGKOK_DAYS)
def bangkok_day(request):
    """Freeze the clock at the instant and give the Bangkok date the CRM must use."""
    instant, expected = request.param
    with freeze_time(datetime.fromisoformat(instant)):
        yield expected


@pytest.fixture
def admin_user():
    return UserFactory(role='Admin', is_staff=True, is_superuser=True)


@pytest.fixture
def api(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


def _term(company=None, **kw):
    """An Active term that started long ago and ends well after every frozen instant."""
    values = dict(status='Active', start_date=date(2026, 1, 1), end_date=date(2027, 12, 31))
    values.update(kw)
    return ContractFactory(**({'company': company} if company else {}), **values)


def _link(contract):
    return ContractZoneFactory(contract=contract, zone=ZoneFactory(company=contract.company),
                               is_active=True, start_date=date(2026, 1, 1), end_date=None)


def _quote(company, **kw):
    values = dict(company=company, status='Draft', valid_from=date(2026, 10, 1), valid_until=date(2027, 3, 31),
                  subtotal=Decimal('100.00'), total_value=Decimal('100.00'), currency='USD')
    values.update(kw)
    return Quote.objects.create(**values)


def _admin_request(user):
    request = RequestFactory().post('/admin/crm_app/quote/')
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def test_the_helper_is_the_bangkok_day(bangkok_day):
    assert business_today() == bangkok_day


# --- contract and zone-link end dates ---------------------------------------------------

def test_cancelling_a_contract_ends_its_zone_links_on_the_bangkok_day(bangkok_day):
    contract = _term()
    links = [_link(contract), _link(contract)]
    contract.status = 'Cancelled'
    contract.save()
    for link in links:
        link.refresh_from_db()
        assert (link.is_active, link.end_date) == (False, bangkok_day)


def test_removing_a_zone_ends_the_link_on_the_bangkok_day(bangkok_day, api):
    contract = _term()
    link = _link(contract)
    response = api.post(f'/api/v1/contracts/{contract.id}/remove-zone/', {'zone_id': str(link.zone_id)},
                        format='json')
    assert response.status_code == 200, response.content
    link.refresh_from_db()
    assert (link.is_active, link.end_date) == (False, bangkok_day)


def test_replacing_zones_ends_old_links_on_the_bangkok_day(bangkok_day, api):
    contract = _term()
    old = _link(contract)
    new_zone = ZoneFactory(company=contract.company)
    response = api.put(f'/api/v1/contracts/{contract.id}/update-zones/', {'zone_ids': [str(new_zone.id)]},
                       format='json')
    assert response.status_code == 200, response.content
    old.refresh_from_db()
    assert (old.is_active, old.end_date) == (False, bangkok_day)
    assert ContractZone.objects.get(contract=contract, zone=new_zone).is_active


def test_a_handover_without_a_successor_start_ends_on_the_bangkok_day(bangkok_day):
    assert handover_end_date(date(2026, 1, 1), None) == bangkok_day


# --- contract dates and numbering ---------------------------------------------------------

def test_sending_a_contract_stamps_the_bangkok_day_and_year(bangkok_day):
    contract = _term(status='Draft', contract_number='')
    assert contract.contract_number.startswith('DRAFT-')
    contract.status = 'Sent'
    contract.save()
    assert contract.sent_date == bangkok_day
    assert contract.contract_number.endswith(f"CT{bangkok_day:%y}001")


def test_document_numbers_carry_the_bangkok_year(bangkok_day):
    assert DocumentSequence.get_next_number('TH', 'QT') == f"TH-QT{bangkok_day:%y}001"


def test_renewal_notice_is_dated_the_bangkok_day(bangkok_day, api):
    contract = _term()
    response = api.post(f'/api/v1/contracts/{contract.id}/send_renewal_notice/')
    assert response.status_code == 200, response.content
    contract.refresh_from_db()
    assert contract.renewal_notice_date == bangkok_day


def test_days_until_expiry_counts_from_the_bangkok_day(bangkok_day):
    contract = _term(end_date=bangkok_day)
    assert contract.days_until_expiry == 0
    assert contract.is_expiring_soon is True
    assert _term(end_date=bangkok_day - timedelta(days=1)).is_expiring_soon is False


# --- quotes -------------------------------------------------------------------------------

@pytest.mark.parametrize('status, field', [
    ('Sent', 'sent_date'), ('Accepted', 'accepted_date'),
    ('Rejected', 'rejected_date'), ('Expired', 'expired_date'),
])
def test_quote_status_dates_are_the_bangkok_day(bangkok_day, status, field):
    quote = _quote(CompanyFactory())
    quote.status = status
    quote.save()
    assert getattr(quote, field) == bangkok_day
    assert quote.quote_number.endswith(f"QT{bangkok_day:%y}001")


@pytest.mark.parametrize('action, field', [('accept', 'accepted_date'), ('reject', 'rejected_date')])
def test_quote_accept_and_reject_actions_stamp_the_bangkok_day(bangkok_day, api, action, field):
    quote = _quote(CompanyFactory(), status='Sent', sent_date=date(2026, 10, 1))
    response = api.post(f'/api/v1/quotes/{quote.id}/{action}/')
    assert response.status_code == 200, response.content
    quote.refresh_from_db()
    assert getattr(quote, field) == bangkok_day


@pytest.mark.parametrize('admin_action, field', [
    ('mark_as_sent', 'sent_date'), ('mark_as_accepted', 'accepted_date'), ('mark_as_rejected', 'rejected_date'),
])
def test_quote_admin_actions_stamp_the_bangkok_day(bangkok_day, admin_user, admin_action, field):
    quote = _quote(CompanyFactory())
    getattr(QuoteAdmin(Quote, AdminSite()), admin_action)(_admin_request(admin_user), Quote.objects.filter(pk=quote.pk))
    quote.refresh_from_db()
    assert getattr(quote, field) == bangkok_day


def test_quote_expiry_counts_from_the_bangkok_day(bangkok_day, api):
    company = CompanyFactory()
    last_day = _quote(company, status='Sent', valid_until=bangkok_day)
    lapsed = _quote(company, status='Sent', valid_until=bangkok_day - timedelta(days=1))
    assert (last_day.is_expired, last_day.days_until_expiry) == (False, 0)
    assert (lapsed.is_expired, lapsed.days_until_expiry) == (True, -1)
    response = api.get('/api/v1/quotes/expiring_soon/')
    assert response.status_code == 200, response.content
    ids = {row['id'] for row in response.json()}
    assert str(last_day.id) in ids and str(lapsed.id) not in ids


# --- invoices, follow-ups and reports -------------------------------------------------------

def test_invoice_days_overdue_count_from_the_bangkok_day(bangkok_day):
    company = CompanyFactory()
    due_today = InvoiceFactory(company=company, status='Sent', due_date=bangkok_day)
    due_yesterday = InvoiceFactory(company=company, status='Sent', due_date=bangkok_day - timedelta(days=1))
    assert (due_today.days_overdue, due_yesterday.days_overdue) == (0, 1)


def test_invoice_next_number_uses_the_bangkok_year(bangkok_day, api):
    response = api.get('/api/v1/invoices/next-number/', {'entity': 'BMAsia (Thailand) Co., Ltd.'})
    assert response.status_code == 200, response.content
    assert response.json()['invoice_number'].startswith(f"INV-TH-{bangkok_day.year}-")


def test_ar_aging_defaults_to_the_bangkok_day(bangkok_day):
    assert ARAgingService().get_ar_aging_report()['as_of_date'] == bangkok_day.isoformat()


def test_opportunity_follow_up_is_overdue_only_after_the_bangkok_day(bangkok_day):
    assert not OpportunityFactory(follow_up_date=bangkok_day).is_overdue
    assert OpportunityFactory(follow_up_date=bangkok_day - timedelta(days=1)).is_overdue


def test_days_in_stage_counts_bangkok_days(bangkok_day):
    opportunity = OpportunityFactory()
    # Changed 40 minutes ago: at 00:30 in Bangkok that was yesterday (23:50), at 23:30 it was today.
    opportunity.stage_changed_at = timezone.now() - timedelta(minutes=40)
    assert opportunity.days_in_stage == (1 if timezone.localtime().hour == 0 else 0)


def test_dashboard_month_is_the_bangkok_month(bangkok_day, api):
    company = CompanyFactory(billing_entity='BMAsia (Thailand) Co., Ltd.')
    first_of_month = bangkok_day.replace(day=1)
    _term(company, currency='THB', value=Decimal('108000.00'), lifecycle_type='new',
          start_date=first_of_month, end_date=bangkok_day + timedelta(days=200))
    _term(company, currency='THB', value=Decimal('5000.00'), lifecycle_type='new',
          start_date=first_of_month - timedelta(days=1), end_date=bangkok_day + timedelta(days=200))
    response = api.get('/api/v1/dashboard/stats/', {'billing_entity': 'BMAsia (Thailand) Co., Ltd.'})
    assert response.status_code == 200, response.content
    data = response.json()
    assert Decimal(data['monthly_revenue']) == Decimal('108000.00')
    assert Decimal(data['previous_month_revenue']) == Decimal('5000.00')


# --- support numbering --------------------------------------------------------------------

def test_ticket_and_article_numbers_carry_the_bangkok_date(bangkok_day):
    ticket = Ticket.objects.create(company=CompanyFactory(), subject='Zone offline', description='x')
    assert ticket.ticket_number.startswith(f"T-{bangkok_day:%Y%m%d}-")
    article = KBArticle(title='How to restart a player', content='x')
    assert article._generate_article_number().startswith(f"KB-{bangkok_day:%Y%m%d}-")
