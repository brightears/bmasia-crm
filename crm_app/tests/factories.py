"""
Factory classes for creating test data using factory_boy.
Used across all test modules for consistent test data generation.
"""
import factory
from factory import fuzzy
from factory.django import DjangoModelFactory
from datetime import date, timedelta
from decimal import Decimal

from crm_app.models import (
    User, Company, Contact, Opportunity, Contract,
    ContractZone, Zone, Invoice
)


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'testuser{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False


class CompanyFactory(DjangoModelFactory):
    """Factory for creating test companies"""
    class Meta:
        model = Company
        django_get_or_create = ('name',)

    name = factory.Faker('company')
    industry = fuzzy.FuzzyChoice(['Hotels', 'Restaurants', 'Bars', 'Retail Fashion'])
    country = fuzzy.FuzzyChoice(['Thailand', 'Singapore', 'USA', 'UK'])
    city = factory.Faker('city')
    address_line1 = factory.Faker('street_address')
    address_line2 = factory.Faker('secondary_address')
    website = factory.Faker('url')
    billing_entity = 'BMAsia Limited'
    soundtrack_account_id = factory.Sequence(lambda n: f'SA-{n:06d}')
    location_count = 1
    music_zone_count = 1


class ContactFactory(DjangoModelFactory):
    """Factory for creating test contacts"""
    class Meta:
        model = Contact

    company = factory.SubFactory(CompanyFactory)
    name = factory.Faker('name')
    email = factory.Faker('email')
    phone = '+66812345678'  # Valid Thai phone number
    title = fuzzy.FuzzyChoice(['Manager', 'Director', 'Owner', 'VP'])
    is_primary = False
    contact_type = 'Other'


class OpportunityFactory(DjangoModelFactory):
    """Factory for creating test opportunities"""
    class Meta:
        model = Opportunity

    company = factory.SubFactory(CompanyFactory)
    name = factory.Faker('catch_phrase')
    stage = fuzzy.FuzzyChoice(['Contacted', 'Quotation Sent', 'Contract Sent', 'Won', 'Lost'])
    expected_value = fuzzy.FuzzyDecimal(1000.0, 50000.0, 2)
    probability = fuzzy.FuzzyInteger(0, 100)
    expected_close_date = factory.LazyFunction(lambda: date.today() + timedelta(days=30))
    owner = factory.SubFactory(UserFactory)


class ContractFactory(DjangoModelFactory):
    """Factory for creating test contracts"""
    class Meta:
        model = Contract

    company = factory.SubFactory(CompanyFactory)
    opportunity = factory.SubFactory(OpportunityFactory)
    contract_number = factory.Sequence(lambda n: f'CTR-2025-{n:04d}')
    contract_type = fuzzy.FuzzyChoice(['New', 'Renewal', 'Amendment'])
    status = 'Active'
    start_date = factory.LazyFunction(lambda: date.today())
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=365))
    value = fuzzy.FuzzyDecimal(5000.0, 100000.0, 2)
    currency = 'USD'
    auto_renew = False
    renewal_period_months = 12
    is_active = True
    payment_terms = '30 days'
    billing_frequency = 'Monthly'
    discount_percentage = Decimal('0.00')


class ZoneFactory(DjangoModelFactory):
    """Factory for creating test zones"""
    class Meta:
        model = Zone

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f'Zone {n}')
    platform = fuzzy.FuzzyChoice(['soundtrack', 'beatbreeze'])
    status = fuzzy.FuzzyChoice(['online', 'offline', 'no_device', 'expired', 'pending'])
    soundtrack_zone_id = factory.Sequence(lambda n: f'SZ-{n:06d}')
    device_name = factory.Faker('word')


class ContractZoneFactory(DjangoModelFactory):
    """Factory for creating test contract-zone relationships"""
    class Meta:
        model = ContractZone

    contract = factory.SubFactory(ContractFactory)
    zone = factory.SubFactory(ZoneFactory)
    start_date = factory.LazyAttribute(lambda obj: obj.contract.start_date)
    end_date = None
    is_active = True
    notes = factory.Faker('sentence')


class InvoiceFactory(DjangoModelFactory):
    """Factory for creating test invoices"""
    class Meta:
        model = Invoice

    contract = factory.SubFactory(ContractFactory)
    invoice_number = factory.Sequence(lambda n: f'INV-2025-{n:04d}')
    status = 'Draft'
    issue_date = factory.LazyFunction(lambda: date.today())
    due_date = factory.LazyFunction(lambda: date.today() + timedelta(days=30))
    amount = fuzzy.FuzzyDecimal(1000.0, 10000.0, 2)
    tax_amount = factory.LazyAttribute(lambda obj: obj.amount * Decimal('0.07'))
    discount_amount = Decimal('0.00')
    total_amount = factory.LazyAttribute(
        lambda obj: obj.amount + obj.tax_amount - obj.discount_amount
    )
    currency = 'USD'
