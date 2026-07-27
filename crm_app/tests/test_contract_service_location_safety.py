"""Regression coverage for contract product rows and PDF pricing safety."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework import serializers

from crm_app.mcp import _COLLECTION_MAP, delete_record
from crm_app.models import ContractServiceLocation
from crm_app.serializers import (
    ContractSerializer,
    ContractServiceLocationSerializer,
)
from crm_app.services.contract_service_locations import (
    service_location_pricing_mismatch,
)
from crm_app.tests.factories import ContractFactory
from crm_app.views import ContractViewSet


@pytest.fixture(scope="session")
def django_db_setup(
    request,
    django_test_environment,
    django_db_blocker,
    django_db_use_migrations,
    django_db_keepdb,
    django_db_createdb,
    django_db_modify_db_settings,
):
    """Use a real isolated DB despite the legacy suite's no-op session fixture."""
    from django.test.utils import setup_databases, teardown_databases
    from pytest_django.fixtures import _disable_migrations

    if not django_db_use_migrations:
        _disable_migrations()

    setup_args = {}
    if django_db_keepdb and not django_db_createdb:
        setup_args["keepdb"] = True

    with django_db_blocker.unblock():
        db_config = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            **setup_args,
        )
    yield
    if not django_db_keepdb:
        with django_db_blocker.unblock():
            teardown_databases(
                db_config,
                verbosity=request.config.option.verbose,
            )


def _flat_contract(zone_names=("Lobby", "Pool")):
    contract = ContractFactory(
        value=Decimal("580.00"),
        currency="USD",
        price_per_zone=Decimal("290.00"),
        show_zone_pricing_detail=True,
        discount_percentage=Decimal("0.00"),
    )
    locations = [
        ContractServiceLocation.objects.create(
            contract=contract,
            location_name=name,
            platform="soundtrack",
            sort_order=index,
        )
        for index, name in enumerate(zone_names)
    ]
    return contract, locations


@pytest.mark.django_db
def test_contract_service_type_is_writable_and_persists():
    contract, _ = _flat_contract()
    serializer = ContractSerializer(
        contract,
        data={"service_type": "beat_breeze_yearly"},
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    contract.refresh_from_db()
    assert contract.service_type == "beat_breeze_yearly"


@pytest.mark.django_db
def test_partial_nested_update_by_id_preserves_omitted_siblings():
    contract, locations = _flat_contract()
    serializer = ContractSerializer(
        contract,
        data={
            "service_locations": [
                {
                    "id": str(locations[0].id),
                    "platform": "beatbreeze",
                }
            ]
        },
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()

    assert contract.service_locations.count() == 2
    locations[0].refresh_from_db()
    locations[1].refresh_from_db()
    assert locations[0].platform == "beatbreeze"
    assert locations[1].platform == "soundtrack"


@pytest.mark.django_db
def test_foreign_location_id_fails_and_rolls_back_all_row_changes():
    contract, locations = _flat_contract()
    other_contract, other_locations = _flat_contract(("Other", "Other 2"))
    serializer = ContractSerializer(
        contract,
        data={
            "service_locations": [
                {
                    "id": str(locations[0].id),
                    "platform": "beatbreeze",
                },
                {
                    "id": str(other_locations[0].id),
                    "platform": "beatbreeze",
                },
            ]
        },
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    with pytest.raises(serializers.ValidationError):
        serializer.save()

    locations[0].refresh_from_db()
    other_locations[0].refresh_from_db()
    assert locations[0].platform == "soundtrack"
    assert other_locations[0].contract_id == other_contract.id
    assert other_locations[0].platform == "soundtrack"


@pytest.mark.django_db
def test_explicit_replace_updates_creates_and_deletes_atomically():
    contract, locations = _flat_contract()
    serializer = ContractSerializer(
        contract,
        data={
            "replace_service_locations": True,
            "service_locations": [
                {
                    "id": str(locations[0].id),
                    "location_name": "Lobby renamed",
                    "platform": "beatbreeze",
                    "sort_order": 0,
                },
                {
                    "location_name": "Gym",
                    "platform": "beatbreeze",
                    "sort_order": 1,
                },
            ],
        },
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()

    rows = list(contract.service_locations.order_by("sort_order"))
    assert [(row.location_name, row.platform) for row in rows] == [
        ("Lobby renamed", "beatbreeze"),
        ("Gym", "beatbreeze"),
    ]
    assert not ContractServiceLocation.objects.filter(id=locations[1].id).exists()


@pytest.mark.django_db
def test_price_zone_mismatch_rejects_write_and_rolls_back():
    contract, locations = _flat_contract()
    payload = [
        {
            "id": str(location.id),
            "location_name": location.location_name,
            "platform": location.platform,
            "sort_order": location.sort_order,
        }
        for location in locations
    ]
    payload.append({
        "location_name": "Unexpected sixth-priced zone",
        "platform": "beatbreeze",
        "sort_order": 2,
    })

    serializer = ContractSerializer(
        contract,
        data={
            "replace_service_locations": True,
            "service_locations": payload,
        },
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    with pytest.raises(serializers.ValidationError, match="does not reconcile"):
        serializer.save()

    assert contract.service_locations.count() == 2
    assert service_location_pricing_mismatch(contract) is None


@pytest.mark.django_db
def test_pdf_is_blocked_when_total_and_zone_prices_disagree():
    contract, _ = _flat_contract()
    contract.value = Decimal("1450.00")
    contract.save(update_fields=["value"])

    view = ContractViewSet()
    view.get_object = lambda: contract
    response = view.pdf(SimpleNamespace())

    assert response.status_code == 409
    assert response.data["evidence"] == {
        "zone_count": 2,
        "expected_value": "580.00",
        "actual_value": "1450.00",
        "currency": "USD",
    }


@pytest.mark.django_db
def test_direct_service_location_update_is_discoverable_and_safe():
    contract, locations = _flat_contract()
    serializer = ContractServiceLocationSerializer(
        locations[0],
        data={"platform": "beatbreeze"},
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()

    locations[0].refresh_from_db()
    assert locations[0].platform == "beatbreeze"
    assert "servicelocation" in _COLLECTION_MAP
    assert "Standalone service-location deletion is blocked" in delete_record(
        "servicelocation",
        str(locations[0].id),
    )
