"""
Test suite for Contract-Zone relationship models.
Tests ContractZone model and integration with Contract and Zone models.
"""
import pytest
from datetime import date, timedelta
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from crm_app.models import ContractZone, Contract, Zone
from crm_app.tests.factories import (
    ContractFactory, ZoneFactory, ContractZoneFactory, CompanyFactory
)


@pytest.mark.django_db
class TestContractZoneModel:
    """Test suite for ContractZone model"""

    def test_create_contract_zone(self):
        """Test creating a ContractZone linking contract to zone"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)

        contract_zone = ContractZone.objects.create(
            contract=contract,
            zone=zone,
            start_date=contract.start_date
        )

        assert contract_zone.id is not None
        assert contract_zone.contract == contract
        assert contract_zone.zone == zone
        assert contract_zone.start_date == contract.start_date

    def test_is_active_defaults_to_true(self):
        """Test is_active field defaults to True"""
        contract_zone = ContractZoneFactory()
        assert contract_zone.is_active is True

    def test_start_date_is_required(self):
        """Test start_date is a required field"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)

        with pytest.raises(IntegrityError):
            ContractZone.objects.create(
                contract=contract,
                zone=zone,
                start_date=None  # This should fail
            )

    def test_end_date_is_optional(self):
        """Test end_date is optional (null=True, blank=True)"""
        contract_zone = ContractZoneFactory(end_date=None)
        assert contract_zone.end_date is None

        # Can also set end_date
        end_date = date.today() + timedelta(days=30)
        contract_zone.end_date = end_date
        contract_zone.save()
        assert contract_zone.end_date == end_date

    def test_notes_field_blank(self):
        """Test notes field can be blank"""
        contract_zone = ContractZoneFactory(notes='')
        assert contract_zone.notes == ''

        # Can also set notes
        contract_zone.notes = 'Test note'
        contract_zone.save()
        assert contract_zone.notes == 'Test note'

    def test_str_method_active(self):
        """Test str() method output for active relationship"""
        contract = ContractFactory(contract_number='CTR-001')
        zone = ZoneFactory(name='Lobby Bar', company=contract.company)
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        expected = "Lobby Bar on CTR-001 (active)"
        assert str(contract_zone) == expected

    def test_str_method_ended(self):
        """Test str() method output for ended relationship"""
        contract = ContractFactory(contract_number='CTR-002')
        zone = ZoneFactory(name='Pool Area', company=contract.company)
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=False,
            end_date=date.today()
        )

        expected = "Pool Area on CTR-002 (ended)"
        assert str(contract_zone) == expected

    def test_unique_together_constraint(self):
        """Test unique_together constraint (contract + zone + start_date)"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)
        start_date = date.today()

        # Create first link
        ContractZone.objects.create(
            contract=contract,
            zone=zone,
            start_date=start_date
        )

        # Try to create duplicate - should fail
        with pytest.raises(IntegrityError):
            ContractZone.objects.create(
                contract=contract,
                zone=zone,
                start_date=start_date
            )

    def test_unique_together_allows_different_dates(self):
        """Test unique_together allows same contract+zone with different start dates"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)

        # Create first link
        link1 = ContractZone.objects.create(
            contract=contract,
            zone=zone,
            start_date=date.today()
        )

        # Create second link with different start_date - should succeed
        link2 = ContractZone.objects.create(
            contract=contract,
            zone=zone,
            start_date=date.today() + timedelta(days=365)
        )

        assert link1.id != link2.id

    def test_cascade_delete_contract(self):
        """Test CASCADE on_delete for contract (deleting contract deletes link)"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)
        contract_zone = ContractZoneFactory(contract=contract, zone=zone)

        contract_zone_id = contract_zone.id
        contract.delete()

        # ContractZone should be deleted
        assert not ContractZone.objects.filter(id=contract_zone_id).exists()

    def test_protect_delete_zone(self):
        """Test PROTECT on_delete for zone (cannot delete zone with active links)"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)
        ContractZoneFactory(contract=contract, zone=zone, is_active=True)

        # Try to delete zone - should fail with ProtectedError
        with pytest.raises(ProtectedError):
            zone.delete()

    def test_can_delete_zone_after_removing_links(self):
        """Test zone can be deleted after all links are removed"""
        contract = ContractFactory()
        zone = ZoneFactory(company=contract.company)
        contract_zone = ContractZoneFactory(contract=contract, zone=zone)

        # Remove the link
        contract_zone.delete()

        # Now zone can be deleted
        zone.delete()
        assert not Zone.objects.filter(id=zone.id).exists()


@pytest.mark.django_db
class TestContractModelZoneIntegration:
    """Test suite for Contract model zone-related methods"""

    def test_get_active_zones_returns_only_active(self):
        """Test Contract.get_active_zones() returns only active zones"""
        contract = ContractFactory()
        company = contract.company

        # Create 3 zones: 2 active, 1 inactive
        zone1 = ZoneFactory(name='Zone 1', company=company)
        zone2 = ZoneFactory(name='Zone 2', company=company)
        zone3 = ZoneFactory(name='Zone 3', company=company)

        ContractZoneFactory(contract=contract, zone=zone1, is_active=True)
        ContractZoneFactory(contract=contract, zone=zone2, is_active=True)
        ContractZoneFactory(contract=contract, zone=zone3, is_active=False)

        active_zones = contract.get_active_zones()

        assert active_zones.count() == 2
        assert zone1 in active_zones
        assert zone2 in active_zones
        assert zone3 not in active_zones

    def test_get_historical_zones_without_date(self):
        """Test Contract.get_historical_zones() without date returns all zones"""
        contract = ContractFactory()
        company = contract.company

        zone1 = ZoneFactory(name='Zone 1', company=company)
        zone2 = ZoneFactory(name='Zone 2', company=company)
        zone3 = ZoneFactory(name='Zone 3', company=company)

        ContractZoneFactory(contract=contract, zone=zone1, is_active=True)
        ContractZoneFactory(contract=contract, zone=zone2, is_active=False)
        ContractZoneFactory(contract=contract, zone=zone3, is_active=True)

        all_zones = contract.get_historical_zones()

        assert all_zones.count() == 3
        assert zone1 in all_zones
        assert zone2 in all_zones
        assert zone3 in all_zones

    def test_get_historical_zones_with_as_of_date(self):
        """Test Contract.get_historical_zones() with as_of_date parameter"""
        contract = ContractFactory(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31)
        )
        company = contract.company

        # Zone 1: Active Jan-Jun 2024
        zone1 = ZoneFactory(name='Zone 1', company=company)
        ContractZoneFactory(
            contract=contract,
            zone=zone1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            is_active=False
        )

        # Zone 2: Active Jul-Dec 2024
        zone2 = ZoneFactory(name='Zone 2', company=company)
        ContractZoneFactory(
            contract=contract,
            zone=zone2,
            start_date=date(2024, 7, 1),
            end_date=None,
            is_active=True
        )

        # Query zones as of March 2024 - should only get zone1
        zones_march = contract.get_historical_zones(as_of_date=date(2024, 3, 15))
        assert zones_march.count() == 1
        assert zone1 in zones_march
        assert zone2 not in zones_march

        # Query zones as of August 2024 - should only get zone2
        zones_august = contract.get_historical_zones(as_of_date=date(2024, 8, 15))
        assert zones_august.count() == 1
        assert zone2 in zones_august
        assert zone1 not in zones_august

    def test_get_zone_count(self):
        """Test Contract.get_zone_count() returns correct count"""
        contract = ContractFactory()
        company = contract.company

        # Initially no zones
        assert contract.get_zone_count() == 0

        # Add 3 active zones
        for i in range(3):
            zone = ZoneFactory(name=f'Zone {i}', company=company)
            ContractZoneFactory(contract=contract, zone=zone, is_active=True)

        assert contract.get_zone_count() == 3

        # Add 2 inactive zones (should not count)
        for i in range(2):
            zone = ZoneFactory(name=f'Inactive Zone {i}', company=company)
            ContractZoneFactory(contract=contract, zone=zone, is_active=False)

        assert contract.get_zone_count() == 3

    def test_multiple_zones_linked_to_one_contract(self):
        """Test multiple zones can be linked to one contract"""
        contract = ContractFactory()
        company = contract.company

        zones = [ZoneFactory(name=f'Zone {i}', company=company) for i in range(5)]

        for zone in zones:
            ContractZoneFactory(contract=contract, zone=zone, is_active=True)

        active_zones = contract.get_active_zones()
        assert active_zones.count() == 5

        for zone in zones:
            assert zone in active_zones

    def test_contract_with_no_zones_returns_empty_queryset(self):
        """Test contract with no zones returns empty queryset"""
        contract = ContractFactory()

        active_zones = contract.get_active_zones()
        assert active_zones.count() == 0

        all_zones = contract.get_historical_zones()
        assert all_zones.count() == 0

        assert contract.get_zone_count() == 0


@pytest.mark.django_db
class TestZoneModelContractIntegration:
    """Test suite for Zone model contract-related methods"""

    def test_get_active_contract_returns_current_contract(self):
        """Test Zone.get_active_contract() returns current contract"""
        company = CompanyFactory()
        zone = ZoneFactory(company=company)
        contract = ContractFactory(company=company)

        ContractZoneFactory(contract=contract, zone=zone, is_active=True)

        active_contract = zone.get_active_contract()
        assert active_contract == contract

    def test_get_active_contract_returns_none_when_no_active(self):
        """Test Zone.get_active_contract() returns None when no active contract"""
        company = CompanyFactory()
        zone = ZoneFactory(company=company)
        contract = ContractFactory(company=company)

        # Create inactive link
        ContractZoneFactory(contract=contract, zone=zone, is_active=False)

        active_contract = zone.get_active_contract()
        assert active_contract is None

    def test_get_active_contract_none_when_no_contracts(self):
        """Test Zone.get_active_contract() returns None when zone has no contracts"""
        zone = ZoneFactory()

        active_contract = zone.get_active_contract()
        assert active_contract is None

    def test_mark_as_cancelled_sets_status(self):
        """Test Zone.mark_as_cancelled() sets status to 'cancelled'"""
        zone = ZoneFactory(status='online')
        assert zone.status == 'online'

        zone.mark_as_cancelled()

        zone.refresh_from_db()
        assert zone.status == 'cancelled'

    def test_get_contract_history_returns_all_contracts(self):
        """Test Zone.get_contract_history() returns all contracts ordered by start_date"""
        company = CompanyFactory()
        zone = ZoneFactory(company=company)

        # Create 3 contracts at different times
        contract1 = ContractFactory(company=company, contract_number='CTR-001')
        link1 = ContractZoneFactory(
            contract=contract1,
            zone=zone,
            start_date=date(2022, 1, 1),
            end_date=date(2022, 12, 31),
            is_active=False
        )

        contract2 = ContractFactory(company=company, contract_number='CTR-002')
        link2 = ContractZoneFactory(
            contract=contract2,
            zone=zone,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            is_active=False
        )

        contract3 = ContractFactory(company=company, contract_number='CTR-003')
        link3 = ContractZoneFactory(
            contract=contract3,
            zone=zone,
            start_date=date(2024, 1, 1),
            is_active=True
        )

        history = zone.get_contract_history()

        # Should have 3 links
        assert history.count() == 3

        # Should be ordered by start_date descending (most recent first)
        history_list = list(history)
        assert history_list[0] == link3  # 2024
        assert history_list[1] == link2  # 2023
        assert history_list[2] == link1  # 2022

    def test_zone_linked_to_multiple_contracts_over_time(self):
        """Test zone can be linked to multiple contracts over time"""
        company = CompanyFactory()
        zone = ZoneFactory(name='Lobby Bar', company=company)

        # Contract 1: 2023
        contract1 = ContractFactory(
            company=company,
            contract_number='CTR-2023-001',
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31)
        )
        link1 = ContractZoneFactory(
            contract=contract1,
            zone=zone,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            is_active=False
        )

        # Contract 2: 2024 (renewal)
        contract2 = ContractFactory(
            company=company,
            contract_number='CTR-2024-001',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31)
        )
        link2 = ContractZoneFactory(
            contract=contract2,
            zone=zone,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_active=False
        )

        # Contract 3: 2025 (current)
        contract3 = ContractFactory(
            company=company,
            contract_number='CTR-2025-001',
            start_date=date(2025, 1, 1)
        )
        link3 = ContractZoneFactory(
            contract=contract3,
            zone=zone,
            start_date=date(2025, 1, 1),
            is_active=True
        )

        # Check contract history
        history = zone.get_contract_history()
        assert history.count() == 3

        # Check active contract is the most recent
        active_contract = zone.get_active_contract()
        assert active_contract == contract3

        # Verify all contracts are in history
        contracts = [link.contract for link in history]
        assert contract1 in contracts
        assert contract2 in contracts
        assert contract3 in contracts
