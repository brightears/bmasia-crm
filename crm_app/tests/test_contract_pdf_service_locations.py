from datetime import date
from types import SimpleNamespace

from crm_app.views import ContractViewSet
from crm_app.views import _contract_total_contract_value, _duration_months


class FakeQuerySet(list):
    def all(self):
        return self

    def exists(self):
        return bool(self)


class FakeCompany:
    name = 'BMAsia Test Hotel'


class FakeContract:
    company = FakeCompany()
    property_name = 'Contract Property'
    show_zone_pricing_detail = False
    price_per_zone = None
    currency = 'USD'


class FakeServiceLocation:
    def __init__(self, location_name, platform, custom_service_name=''):
        self.location_name = location_name
        self.platform = platform
        self.custom_service_name = custom_service_name
        self.price = None


class FakeServiceLocations(list):
    def all(self):
        return self


def _plain_text(value):
    if hasattr(value, 'getPlainText'):
        return value.getPlainText()
    return value


def test_service_locations_table_splits_multiline_zone_names_and_keeps_running_numbering():
    table_flowable = ContractViewSet()._build_service_locations_table(
        FakeContract(),
        FakeQuerySet([
            FakeServiceLocation('Lobby\nPool Bar', 'soundtrack'),
            FakeServiceLocation('Spa', 'beatbreeze'),
            FakeServiceLocation('Rooftop\nGarden', 'custom', 'MP3'),
        ]),
    )

    table = table_flowable._content[0]
    rows = table._cellvalues

    assert [_plain_text(row[2]) for row in rows[1:]] == [
        'Zone 1: Lobby',
        'Zone 2: Pool Bar',
        'Zone 3: Spa',
        'Zone 4: Rooftop',
        'Zone 5: Garden',
    ]
    assert _plain_text(rows[1][1]) == 'Soundtrack Your Brand'
    assert _plain_text(rows[3][1]) == 'Beat Breeze'
    assert _plain_text(rows[4][1]) == 'MP3'


def test_multi_year_contract_value_not_multiplied_when_line_item_quantity_includes_term():
    contract = SimpleNamespace(
        billing_frequency='Annually',
        service_locations=FakeServiceLocations([FakeServiceLocation('Lobby', 'soundtrack')]),
    )
    line_items = [SimpleNamespace(quantity=2)]
    duration_months = _duration_months(date(2026, 8, 1), date(2028, 7, 31))

    assert duration_months == 24
    assert _contract_total_contract_value(720.0, duration_months, contract, line_items) == 720.0


def test_multi_year_contract_value_still_multiplies_annual_line_items():
    contract = SimpleNamespace(
        billing_frequency='Annually',
        service_locations=FakeServiceLocations([FakeServiceLocation('Lobby', 'soundtrack')]),
    )
    line_items = [SimpleNamespace(quantity=1)]
    duration_months = _duration_months(date(2026, 8, 1), date(2028, 7, 31))

    assert _contract_total_contract_value(360.0, duration_months, contract, line_items) == 720.0
