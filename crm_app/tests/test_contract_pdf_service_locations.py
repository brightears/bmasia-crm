from crm_app.views import ContractViewSet


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
