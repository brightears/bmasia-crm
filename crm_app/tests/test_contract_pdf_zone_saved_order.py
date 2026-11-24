"""Service-location rows print in their saved order (Theo defect D9).

The contract's zone table used to put every Soundtrack Your Brand row first,
then Beat Breeze, then custom products, and numbered the zones in that grouped
order. A contract saved as four Beat Breeze rows, one Soundtrack row and two
more Beat Breeze rows therefore printed the Soundtrack row as Zone 1.

Rows now follow the saved sort order and the zone numbers follow the rows.
The Service cell is merged only across adjacent rows of the same service, so
interleaved rows each show their own service name. Contracts whose saved order
was already grouped, and single-service contracts, print as before. Rows that
share a sort_order keep the former grouping as their tie-break.

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
from crm_app.views import ContractViewSet


class FakeQuerySet(list):
    def all(self):
        return self

    def exists(self):
        return bool(self)


class FakeCompany:
    name = 'Example Bay Resort Company'


class FakeContract:
    def __init__(self, *, pricing=False):
        self.company = FakeCompany()
        self.property_name = 'Example Bay Resort'
        self.show_zone_pricing_detail = pricing
        self.price_per_zone = Decimal('9000.00') if pricing else None
        self.currency = 'THB'


class FakeServiceLocation:
    def __init__(self, sort_order, location_name, platform, custom_service_name='', price=None):
        self.sort_order = sort_order
        self.location_name = location_name
        self.platform = platform
        self.custom_service_name = custom_service_name
        self.price = price


def _plain(value):
    if hasattr(value, 'getPlainText'):
        return value.getPlainText()
    return value


def _table(flowable):
    # Tables of up to 15 zones come wrapped in KeepTogether.
    return flowable._content[0] if hasattr(flowable, '_content') else flowable


def _build(locations, *, pricing=False):
    flowable = ContractViewSet()._build_service_locations_table(
        FakeContract(pricing=pricing), FakeQuerySet(locations),
    )
    table = _table(flowable)
    return table._cellvalues, sorted(_span_commands(table))


def _span_commands(table):
    # ReportLab keeps SPAN commands in _spanCmds after setStyle.
    return [(tuple(cmd[1]), tuple(cmd[2])) for cmd in table._spanCmds]


def _zones(rows):
    return [_plain(row[2]) for row in rows[1:]]


def _services(rows):
    return [_plain(row[1]) for row in rows[1:]]


def _bb(sort_order, name, price=None):
    """Beat Breeze stored the way Cira saves it: a custom row named Beat Breeze."""
    return FakeServiceLocation(sort_order, name, 'custom', 'Beat Breeze', price)


# --- mixed, interleaved -----------------------------------------------------

def _interleaved_rows():
    return [
        _bb(1, 'Courtyard Restaurant'),
        _bb(2, 'Garden Coffee House'),
        _bb(3, 'Saffron Room'),
        _bb(4, 'Trattoria Rossa'),
        FakeServiceLocation(5, 'Kumo Sushi Bar', 'soundtrack', price=Decimal('10500.00')),
        _bb(6, 'Pool Bar'),
        _bb(7, 'Example Bay Resort - Hotel Lobby'),
    ]


def test_interleaved_rows_print_in_saved_order_with_matching_zone_numbers():
    rows, spans = _build(_interleaved_rows(), pricing=True)

    assert _zones(rows) == [
        'Zone 1: Courtyard Restaurant',
        'Zone 2: Garden Coffee House',
        'Zone 3: Saffron Room',
        'Zone 4: Trattoria Rossa',
        'Zone 5: Kumo Sushi Bar',
        'Zone 6: Pool Bar',
        'Zone 7: Example Bay Resort - Hotel Lobby',
    ]
    # Each run of the same service shows its own name once.
    assert _services(rows) == [
        'Beat Breeze', '', '', '',
        'Soundtrack Your Brand',
        'Beat Breeze', '',
    ]
    # Prices stay with their row.
    assert [row[3] for row in rows[1:]] == [
        'THB 9,000.00', 'THB 9,000.00', 'THB 9,000.00', 'THB 9,000.00',
        'THB 10,500.00',
        'THB 9,000.00', 'THB 9,000.00',
    ]
    assert spans == [
        ((0, 1), (0, 7)),   # Property, all rows
        ((1, 1), (1, 4)),   # Beat Breeze, rows 1-4
        ((1, 6), (1, 7)),   # Beat Breeze, rows 6-7; row 5 is not merged
    ]


def test_interleaved_multiline_location_keeps_running_numbers_within_its_run():
    rows, spans = _build([
        FakeServiceLocation(1, 'Lobby\nLounge', 'soundtrack'),
        FakeServiceLocation(2, 'Spa', 'beatbreeze'),
        FakeServiceLocation(3, 'Rooftop', 'soundtrack'),
    ])

    assert _zones(rows) == ['Zone 1: Lobby', 'Zone 2: Lounge', 'Zone 3: Spa', 'Zone 4: Rooftop']
    assert _services(rows) == ['Soundtrack Your Brand', '', 'Beat Breeze', 'Soundtrack Your Brand']
    assert spans == [((0, 1), (0, 4)), ((1, 1), (1, 2))]


def test_large_interleaved_table_labels_each_run_without_spans():
    locations = [FakeServiceLocation(i, f'Room {i}', 'beatbreeze') for i in range(1, 9)]
    locations.append(FakeServiceLocation(9, 'Ballroom', 'soundtrack'))
    locations += [FakeServiceLocation(i, f'Room {i}', 'beatbreeze') for i in range(10, 18)]
    flowable = ContractViewSet()._build_service_locations_table(FakeContract(), FakeQuerySet(locations))

    table = _table(flowable)
    rows = table._cellvalues
    assert len(rows) == 18  # header + 17 zones, so the table may split across pages
    assert _zones(rows)[8] == 'Zone 9: Ballroom'
    services = _services(rows)
    assert services[0] == 'Beat Breeze'
    assert services[8] == 'Soundtrack Your Brand'
    assert services[9] == 'Beat Breeze'
    assert [s for s in services if s] == ['Beat Breeze', 'Soundtrack Your Brand', 'Beat Breeze']
    assert _span_commands(table) == []


# --- already grouped, and single service: same output as before -------------

def test_grouped_saved_order_prints_as_before():
    rows, spans = _build([
        FakeServiceLocation(1, 'Lobby', 'soundtrack'),
        FakeServiceLocation(2, 'Restaurant', 'soundtrack'),
        FakeServiceLocation(3, 'Pool\nGym', 'beatbreeze'),
        FakeServiceLocation(4, 'Spa', 'beatbreeze'),
        FakeServiceLocation(5, 'Kids Club', 'custom', 'MP3'),
    ])

    assert _zones(rows) == [
        'Zone 1: Lobby', 'Zone 2: Restaurant', 'Zone 3: Pool',
        'Zone 4: Gym', 'Zone 5: Spa', 'Zone 6: Kids Club',
    ]
    assert _services(rows) == ['Soundtrack Your Brand', '', 'Beat Breeze', '', '', 'MP3']
    assert spans == [((0, 1), (0, 6)), ((1, 1), (1, 2)), ((1, 3), (1, 5))]


@pytest.mark.parametrize('platform,custom_name,label', [
    ('soundtrack', '', 'Soundtrack Your Brand'),
    ('beatbreeze', '', 'Beat Breeze'),
    ('custom', 'Beat Breeze', 'Beat Breeze'),
    ('custom', 'License Inclusive Music', 'Beat Breeze'),
])
def test_single_service_contract_prints_as_before(platform, custom_name, label):
    rows, spans = _build([
        FakeServiceLocation(1, 'Lobby', platform, custom_name),
        FakeServiceLocation(2, 'Bar\nTerrace', platform, custom_name),
        FakeServiceLocation(3, 'Spa', platform, custom_name),
    ])

    assert _zones(rows) == ['Zone 1: Lobby', 'Zone 2: Bar', 'Zone 3: Terrace', 'Zone 4: Spa']
    assert _services(rows) == [label, '', '', '']
    assert spans == [((0, 1), (0, 4)), ((1, 1), (1, 4))]


def test_single_zone_contract_prints_as_before():
    rows, spans = _build([FakeServiceLocation(0, 'Lobby', 'soundtrack')])

    assert _zones(rows) == ['Zone 1: Lobby']
    assert _services(rows) == ['Soundtrack Your Brand']
    assert spans == []


def test_rows_sharing_a_sort_order_keep_the_former_grouping():
    # Rows saved without distinct positions (all 0) come from the database in
    # platform-name order (beatbreeze, custom, soundtrack). They keep the old
    # Soundtrack / Beat Breeze / custom grouping, so these documents do not move.
    rows, spans = _build([
        FakeServiceLocation(0, 'Pool', 'beatbreeze'),
        FakeServiceLocation(0, 'Kids Club', 'custom', 'MP3'),
        FakeServiceLocation(0, 'Garden', 'custom', 'Beat Breeze'),
        FakeServiceLocation(0, 'Terrace', 'custom', 'MP3'),
        FakeServiceLocation(0, 'Lobby', 'soundtrack'),
        FakeServiceLocation(0, 'Restaurant', 'soundtrack'),
    ])

    assert _zones(rows) == [
        'Zone 1: Lobby', 'Zone 2: Restaurant', 'Zone 3: Pool',
        'Zone 4: Kids Club', 'Zone 5: Terrace', 'Zone 6: Garden',
    ]
    assert _services(rows) == ['Soundtrack Your Brand', '', 'Beat Breeze', 'MP3', '', 'Beat Breeze']
    assert spans == [((0, 1), (0, 6)), ((1, 1), (1, 2)), ((1, 4), (1, 5))]


# --- the whole contract PDF --------------------------------------------------

@pytest.mark.django_db
def test_rendered_contract_lists_interleaved_zones_in_saved_order():
    User.objects.create_user(
        username='zone-order-reviewer', email='zone-order@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )
    company = Company.objects.create(
        name='Example Bay Resort', legal_entity_name='Example Bay Resort Co., Ltd.',
        city='Krabi', country='Thailand', billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number='DRAFT-ZONE-ORDER-01',
        contract_type='Annual', contract_category='standard', status='Draft',
        is_active=False, start_date=date(2026, 12, 1), end_date=date(2027, 11, 30),
        value=Decimal('64500.00'), price_per_zone=Decimal('9000.00'),
        show_zone_pricing_detail=True, tax_rate=Decimal('7'), currency='THB',
        billing_frequency='Annually', property_name='Example Bay Resort',
    )
    for loc in _interleaved_rows():
        contract.service_locations.create(
            location_name=loc.location_name, platform=loc.platform,
            custom_service_name=loc.custom_service_name, sort_order=loc.sort_order,
            price=loc.price,
        )

    with override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True):
        result = json.loads(generate_contract_pdf(str(contract.pk)))
    reader = PdfReader(BytesIO(base64.b64decode(result['content_b64'])))
    text = ' '.join(' '.join((page.extract_text() or '').split()) for page in reader.pages)

    positions = [text.index(f'Zone {n}:') for n in range(1, 8)]
    assert positions == sorted(positions)
    assert 'Zone 5: Kumo Sushi Bar' in text
    assert 'Zone 1: Courtyard' in text
    zone_table = text[text.index('Zone 1:') - 40:text.index('Zone 7:')]
    assert zone_table.count('Beat Breeze') == 2
    assert zone_table.count('Soundtrack Your Brand') == 1
    assert text.index('Zone 4:') < text.index('Soundtrack Your Brand', text.index('Zone 1:')) < text.index('Zone 5:')
