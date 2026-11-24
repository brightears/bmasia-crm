"""A zone saved at price 0 prints as included, not at the contract's price per zone.

The zone table read ``loc.price or contract.price_per_zone``, so a row saved
with price 0 (a zone included at no charge) printed the contract's
price_per_zone. The pricing check counts that row as 0, so the contract passed
and the printed rows added up to more than the contract value.

A stored 0 now prints "Included", the label the quotation uses for
complimentary items. Only a row with no price of its own (null) falls back to
price_per_zone. Rows with their own non-zero price print as before.

All names here are made up.
"""
import base64
import json
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.test import override_settings
from pypdf import PdfReader

from crm_app.mcp import generate_contract_pdf
from crm_app.models import Company, Contract, User
from crm_app.services.contract_service_locations import service_location_pricing_mismatch
from crm_app.views import ContractViewSet


class FakeQuerySet(list):
    def all(self):
        return self

    def exists(self):
        return bool(self)


class FakeCompany:
    name = 'Example Garden Hotel Company'


class FakeContract:
    def __init__(self, price_per_zone):
        self.company = FakeCompany()
        self.property_name = 'Example Garden Hotel'
        self.show_zone_pricing_detail = True
        self.price_per_zone = price_per_zone
        self.currency = 'THB'


class FakeServiceLocation:
    def __init__(self, sort_order, location_name, price, platform='soundtrack'):
        self.sort_order = sort_order
        self.location_name = location_name
        self.platform = platform
        self.custom_service_name = ''
        self.price = price


def _table(flowable):
    # Tables of up to 15 zones come wrapped in KeepTogether.
    return flowable._content[0] if hasattr(flowable, '_content') else flowable


def _price_cells(locations, *, price_per_zone):
    flowable = ContractViewSet()._build_service_locations_table(
        FakeContract(price_per_zone), FakeQuerySet(locations),
    )
    rows = _table(flowable)._cellvalues
    assert rows[0][-1] == 'Price/Zone'
    return [row[-1] for row in rows[1:]]


def _printed_total(cells):
    total = Decimal('0')
    for cell in cells:
        if cell == 'Included':
            continue
        currency, amount = cell.split(' ', 1)
        assert currency == 'THB'
        total += Decimal(amount.replace(',', ''))
    return total


def _review_rows():
    """The reviewed case: a Lobby at 0 next to price_per_zone 9,000; value 21,000."""
    return [
        FakeServiceLocation(0, 'Lobby', Decimal('0.00')),
        FakeServiceLocation(1, 'Restaurant', None),
        FakeServiceLocation(2, 'Pool Bar', Decimal('12000.00')),
    ]


# --- the zone table ----------------------------------------------------------

def test_zero_price_zone_prints_included_and_rows_sum_to_the_contract_value():
    cells = _price_cells(_review_rows(), price_per_zone=Decimal('9000.00'))

    assert cells == ['Included', 'THB 9,000.00', 'THB 12,000.00']
    assert _printed_total(cells) == Decimal('21000.00')


def test_zero_price_zone_prints_included_when_the_contract_has_no_price_per_zone():
    cells = _price_cells([
        FakeServiceLocation(0, 'Lobby', Decimal('12000.00')),
        FakeServiceLocation(1, 'Restaurant', Decimal('12000.00')),
        FakeServiceLocation(2, 'Back Office', Decimal('0')),
    ], price_per_zone=None)

    assert cells == ['THB 12,000.00', 'THB 12,000.00', 'Included']
    assert _printed_total(cells) == Decimal('24000.00')


def test_null_price_still_falls_back_to_price_per_zone():
    cells = _price_cells([
        FakeServiceLocation(0, 'Lobby', None),
        FakeServiceLocation(1, 'Restaurant', None),
    ], price_per_zone=Decimal('9000.00'))

    assert cells == ['THB 9,000.00', 'THB 9,000.00']


def test_null_price_without_price_per_zone_still_prints_blank():
    cells = _price_cells([
        FakeServiceLocation(0, 'Lobby', Decimal('10500.00')),
        FakeServiceLocation(1, 'Restaurant', None),
    ], price_per_zone=None)

    assert cells == ['THB 10,500.00', '']


def test_normal_priced_rows_are_unchanged():
    cells = _price_cells([
        FakeServiceLocation(0, 'Lobby', Decimal('10500.00')),
        FakeServiceLocation(1, 'Restaurant', Decimal('9000.00')),
        FakeServiceLocation(2, 'Pool Bar', Decimal('0.50')),
    ], price_per_zone=Decimal('9000.00'))

    assert cells == ['THB 10,500.00', 'THB 9,000.00', 'THB 0.50']


@pytest.mark.parametrize('price_per_zone, price, expected', [
    (Decimal('9000.00'), None, 'THB 9,000.00'),
    (Decimal('9000.00'), Decimal('0'), 'Included'),
    (Decimal('9000.00'), Decimal('0.00'), 'Included'),
    (Decimal('9000.00'), Decimal('7500.00'), 'THB 7,500.00'),
    (None, None, ''),
    (None, Decimal('0.00'), 'Included'),
    (Decimal('0.00'), None, ''),
])
def test_price_cell_rules(price_per_zone, price, expected):
    loc = FakeServiceLocation(0, 'Lobby', price)
    assert ContractViewSet._service_location_price_label(FakeContract(price_per_zone), loc) == expected


# --- the whole contract PDF --------------------------------------------------

@pytest.mark.django_db
def test_rendered_contract_prints_the_zero_price_zone_as_included():
    User.objects.create_user(
        username='zero-price-reviewer', email='zero-price@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )
    company = Company.objects.create(
        name='Example Garden Hotel', legal_entity_name='Example Garden Hotel Co., Ltd.',
        city='Chiang Mai', country='Thailand', billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number='DRAFT-ZERO-PRICE-01',
        contract_type='Annual', contract_category='standard', status='Draft',
        is_active=False, start_date=date(2026, 12, 1), end_date=date(2027, 11, 30),
        value=Decimal('21000.00'), price_per_zone=Decimal('9000.00'),
        show_zone_pricing_detail=True, tax_rate=Decimal('7'), currency='THB',
        billing_frequency='Annually', property_name='Example Garden Hotel',
    )
    for loc in _review_rows():
        contract.service_locations.create(
            location_name=loc.location_name, platform=loc.platform,
            sort_order=loc.sort_order, price=loc.price,
        )

    # The pricing check reads the stored 0 as 0, so the contract reconciles.
    assert service_location_pricing_mismatch(contract) is None

    with override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True):
        result = json.loads(generate_contract_pdf(str(contract.pk)))
    reader = PdfReader(BytesIO(base64.b64decode(result['content_b64'])))
    text = ' '.join(' '.join((page.extract_text() or '').split()) for page in reader.pages)

    zone_table = text[text.index('Zone 1:'):text.index('Zone 3:') + 40]
    assert 'Zone 1: Lobby Included' in zone_table
    assert 'Zone 2: Restaurant THB 9,000.00' in zone_table
    assert 'Zone 3: Pool Bar THB 12,000.00' in zone_table
    assert zone_table.count('THB 9,000.00') == 1
    assert 'THB 21,000.00' in text
