"""Dashboard money totals per currency.

The existing totals add contract values and invoice amounts of every currency together and stay as
they are. The new *_by_currency fields keep each document's own currency apart.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from crm_app.tests.factories import CompanyFactory, ContractFactory, InvoiceFactory, UserFactory

THAILAND = 'BMAsia (Thailand) Co., Ltd.'


def _stats(user, **params):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/v1/dashboard/stats/', params)
    assert response.status_code == 200, response.content
    return response.json()


@pytest.fixture
def admin():
    return UserFactory(role='Admin')


@pytest.fixture
def thailand_book():
    """A Thailand-entity customer with THB and USD documents side by side."""
    company = CompanyFactory(billing_entity=THAILAND)
    today = date.today()
    # Two new contracts starting this month, one per currency, both ending within 60 days.
    thb = ContractFactory(
        company=company, currency='THB', value=Decimal('108000.00'), lifecycle_type='new',
        start_date=today.replace(day=1), end_date=today + timedelta(days=30),
    )
    usd = ContractFactory(
        company=company, currency='USD', value=Decimal('2160.00'), lifecycle_type='new',
        start_date=today.replace(day=1), end_date=today + timedelta(days=30),
    )
    # Overdue invoices, one per currency.
    InvoiceFactory(
        contract=thb, company=company, currency='THB', status='Sent',
        amount=Decimal('50000.00'), tax_amount=Decimal('0.00'), total_amount=Decimal('50000.00'),
        issue_date=today - timedelta(days=60), due_date=today - timedelta(days=30),
    )
    InvoiceFactory(
        contract=usd, company=company, currency='USD', status='Sent',
        amount=Decimal('700.00'), tax_amount=Decimal('0.00'), total_amount=Decimal('700.00'),
        issue_date=today - timedelta(days=60), due_date=today - timedelta(days=30),
    )
    # A BMAsia Limited customer that the Thailand filter must leave out.
    other = CompanyFactory(billing_entity='BMAsia Limited')
    ContractFactory(company=other, currency='USD', value=Decimal('999.00'), lifecycle_type='new',
                    start_date=today.replace(day=1))
    return company


@pytest.mark.django_db
def test_existing_totals_are_unchanged_and_still_add_currencies_together(admin, thailand_book):
    data = _stats(admin, billing_entity=THAILAND)
    # 108,000 THB + 2,160 USD added as if one currency: this is what the page shows today.
    assert Decimal(data['monthly_revenue']) == Decimal('110160.00')
    assert Decimal(data['contracts_value']) == Decimal('110160.00')
    assert Decimal(data['pending_renewal_value']) == Decimal('110160.00')
    assert Decimal(data['total_overdue_amount']) == Decimal('50700.00')
    assert Decimal(data['new_revenue']) == Decimal('110160.00')
    assert Decimal(data['net_revenue']) == Decimal('110160.00')
    assert data['revenue_trend'][-1]['revenue'] == 110160.0


@pytest.mark.django_db
def test_per_currency_totals_keep_thb_and_usd_apart(admin, thailand_book):
    data = _stats(admin, billing_entity=THAILAND)
    both = [{'currency': 'THB', 'total': '108000.00'}, {'currency': 'USD', 'total': '2160.00'}]
    assert data['monthly_revenue_by_currency'] == both
    assert data['contracts_value_by_currency'] == both
    assert data['pending_renewal_value_by_currency'] == both
    assert data['new_revenue_by_currency'] == both
    assert data['renewal_revenue_by_currency'] == []
    assert data['net_revenue_by_currency'] == both
    assert data['total_overdue_amount_by_currency'] == [
        {'currency': 'THB', 'total': '50000.00'},
        {'currency': 'USD', 'total': '700.00'},
    ]


@pytest.mark.django_db
def test_trend_months_carry_per_currency_series(admin, thailand_book):
    this_month = _stats(admin, billing_entity=THAILAND)['revenue_trend'][-1]
    assert this_month['by_currency'] == [
        {'currency': 'THB', 'revenue': '108000.00', 'new_revenue': '108000.00', 'renewal_revenue': '0.00',
         'churned_revenue': '0.00', 'net_revenue': '108000.00'},
        {'currency': 'USD', 'revenue': '2160.00', 'new_revenue': '2160.00', 'renewal_revenue': '0.00',
         'churned_revenue': '0.00', 'net_revenue': '2160.00'},
    ]


@pytest.mark.django_db
def test_churn_is_subtracted_within_its_own_currency(admin, thailand_book):
    today = date.today()
    ContractFactory(
        company=thailand_book, currency='USD', value=Decimal('500.00'), status='Expired', is_active=False,
        start_date=today - timedelta(days=365), end_date=today.replace(day=1),
    )
    data = _stats(admin, billing_entity=THAILAND)
    assert data['churned_revenue_by_currency'] == [{'currency': 'USD', 'total': '500.00'}]
    assert data['net_revenue_by_currency'] == [
        {'currency': 'THB', 'total': '108000.00'},
        {'currency': 'USD', 'total': '1660.00'},
    ]
    # The old net figure subtracts 500 USD from a THB + USD sum.
    assert Decimal(data['net_revenue']) == Decimal('109660.00')


@pytest.mark.django_db
def test_entity_filter_still_applies_to_the_new_figures(admin, thailand_book):
    data = _stats(admin, billing_entity='BMAsia Limited')
    assert data['monthly_revenue_by_currency'] == [{'currency': 'USD', 'total': '999.00'}]
    assert data['total_overdue_amount_by_currency'] == []


@pytest.mark.django_db
def test_empty_book_returns_empty_lists(admin):
    data = _stats(admin, billing_entity=THAILAND)
    for key in ('contracts_value_by_currency', 'monthly_revenue_by_currency', 'net_revenue_by_currency',
                'total_overdue_amount_by_currency', 'pending_renewal_value_by_currency'):
        assert data[key] == []
    assert all(month['by_currency'] == [] for month in data['revenue_trend'])
