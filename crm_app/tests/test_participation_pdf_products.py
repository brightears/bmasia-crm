from crm_app.views import ContractViewSet


class FakeQuerySet(list):
    def all(self):
        return self

    def exists(self):
        return bool(self)


class FakeServiceLocation:
    def __init__(self, platform, custom_service_name=''):
        self.platform = platform
        self.custom_service_name = custom_service_name


class FakeZone:
    def __init__(self, platform):
        self.platform = platform


class FakeContract:
    def __init__(self, service_locations):
        self.service_locations = FakeQuerySet(service_locations)


def test_hilton_participation_section_8_uses_beat_breeze_service_locations():
    contract = FakeContract([
        FakeServiceLocation('beatbreeze'),
        FakeServiceLocation('beatbreeze'),
    ])

    description = ContractViewSet()._participation_products_price_description(
        contract,
        FakeQuerySet([]),
    )

    assert description == 'Beat Breeze Services - 2 Zone(s)'


def test_hilton_participation_section_8_keeps_soundtrack_default_for_syb_zones():
    contract = FakeContract([])

    description = ContractViewSet()._participation_products_price_description(
        contract,
        FakeQuerySet([FakeZone('soundtrack')]),
    )

    assert description == 'Music Streaming Services - 1 Zone(s)'
