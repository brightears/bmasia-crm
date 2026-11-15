from decimal import Decimal

import pytest

from crm_app.serializers import CompanySerializer
from crm_app.tests.factories import CompanyFactory, ContractFactory


@pytest.mark.django_db
def test_active_contract_value_is_reported_per_currency():
    company = CompanyFactory()
    ContractFactory(company=company, currency='THB', value=Decimal('108000.00'), is_active=True)
    ContractFactory(company=company, currency='THB', value=Decimal('2000.50'), is_active=True)
    ContractFactory(company=company, currency='USD', value=Decimal('2160.00'), is_active=True)
    ContractFactory(company=company, currency='USD', value=Decimal('9999.00'), is_active=False)

    assert company.active_contract_value_by_currency == [
        {'currency': 'THB', 'total': '110000.50'},
        {'currency': 'USD', 'total': '2160.00'},
    ]
    # The old field still adds the currencies together, unchanged for existing callers.
    assert company.total_contract_value == Decimal('112160.50')


@pytest.mark.django_db
def test_company_without_active_contracts_has_an_empty_list():
    company = CompanyFactory()
    ContractFactory(company=company, currency='USD', value=Decimal('500.00'), is_active=False)
    assert company.active_contract_value_by_currency == []


@pytest.mark.django_db
def test_serializer_exposes_the_per_currency_totals_read_only():
    company = CompanyFactory()
    ContractFactory(company=company, currency='USD', value=Decimal('720.00'), is_active=True)
    data = CompanySerializer(company).data
    assert data['active_contract_value_by_currency'] == [{'currency': 'USD', 'total': '720.00'}]

    serializer = CompanySerializer(
        company, data={'active_contract_value_by_currency': [{'currency': 'THB', 'total': '1'}]}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    assert 'active_contract_value_by_currency' not in serializer.validated_data
