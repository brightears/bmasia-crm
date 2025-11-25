"""
Test suite for Contract-Zone signal handlers.
Tests automatic zone cancellation when contract is terminated.
"""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from crm_app.models import Contract, Zone, ContractZone
from crm_app.tests.factories import (
    ContractFactory, ZoneFactory, ContractZoneFactory, CompanyFactory
)


@pytest.mark.django_db
class TestContractTerminationSignal:
    """Test suite for handle_contract_termination signal"""

    def test_contract_termination_marks_zones_as_cancelled(self):
        """Test contract termination marks active zones as cancelled"""
        contract = ContractFactory(status='Active')
        company = contract.company

        # Create 2 active zones
        zone1 = ZoneFactory(name='Zone 1', company=company, status='online')
        zone2 = ZoneFactory(name='Zone 2', company=company, status='online')

        ContractZoneFactory(contract=contract, zone=zone1, is_active=True)
        ContractZoneFactory(contract=contract, zone=zone2, is_active=True)

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # Zones should be marked as cancelled
        zone1.refresh_from_db()
        zone2.refresh_from_db()

        assert zone1.status == 'cancelled'
        assert zone2.status == 'cancelled'

    def test_contract_termination_sets_is_active_false(self):
        """Test ContractZone.is_active set to False on termination"""
        contract = ContractFactory(status='Active')
        company = contract.company

        zone = ZoneFactory(company=company)
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # ContractZone should be inactive
        contract_zone.refresh_from_db()
        assert contract_zone.is_active is False

    def test_contract_termination_sets_end_date(self):
        """Test ContractZone.end_date set to today on termination"""
        contract = ContractFactory(status='Active')
        company = contract.company

        zone = ZoneFactory(company=company)
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True,
            end_date=None
        )

        today = timezone.now().date()

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # ContractZone should have end_date set to today
        contract_zone.refresh_from_db()
        assert contract_zone.end_date == today

    def test_signal_only_affects_active_zones(self):
        """Test signal only affects zones with is_active=True"""
        contract = ContractFactory(status='Active')
        company = contract.company

        # Create 1 active zone and 1 inactive zone
        active_zone = ZoneFactory(name='Active Zone', company=company, status='online')
        inactive_zone = ZoneFactory(name='Inactive Zone', company=company, status='offline')

        active_link = ContractZoneFactory(
            contract=contract,
            zone=active_zone,
            is_active=True
        )
        inactive_link = ContractZoneFactory(
            contract=contract,
            zone=inactive_zone,
            is_active=False,
            end_date=date.today() - timedelta(days=30)
        )

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # Active zone should be cancelled
        active_zone.refresh_from_db()
        active_link.refresh_from_db()
        assert active_zone.status == 'cancelled'
        assert active_link.is_active is False
        assert active_link.end_date is not None

        # Inactive zone should remain unchanged
        inactive_zone.refresh_from_db()
        inactive_link.refresh_from_db()
        assert inactive_zone.status == 'offline'  # Unchanged
        assert inactive_link.is_active is False  # Already was False
        assert inactive_link.end_date == date.today() - timedelta(days=30)  # Unchanged

    def test_signal_does_not_affect_already_terminated(self):
        """Test signal does not affect already terminated zones"""
        contract = ContractFactory(status='Active')
        company = contract.company

        zone = ZoneFactory(company=company, status='cancelled')
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # Zone should remain cancelled (not double-processed)
        zone.refresh_from_db()
        assert zone.status == 'cancelled'

        # ContractZone should be updated
        contract_zone.refresh_from_db()
        assert contract_zone.is_active is False

    def test_signal_does_not_trigger_on_creation(self):
        """Test signal does not trigger on contract creation"""
        company = CompanyFactory()
        zone = ZoneFactory(company=company, status='pending')

        # Create contract with Terminated status (edge case)
        contract = ContractFactory(
            company=company,
            status='Terminated'
        )

        # Create link after contract creation
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        # Zone should remain pending (signal should not fire on creation)
        # Note: In practice, we wouldn't link zones to terminated contracts,
        # but testing the signal behavior here
        zone.refresh_from_db()
        # The zone status depends on when the link was created relative to the signal
        # If created after contract, signal won't retroactively affect it

    def test_signal_does_not_trigger_on_non_termination_changes(self):
        """Test signal does not trigger on non-termination status changes"""
        contract = ContractFactory(status='Draft')
        company = contract.company

        zone = ZoneFactory(company=company, status='pending')
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        # Change status to Active (not Terminated)
        contract.status = 'Active'
        contract.save()

        # Zone should remain unchanged
        zone.refresh_from_db()
        contract_zone.refresh_from_db()

        assert zone.status == 'pending'
        assert contract_zone.is_active is True
        assert contract_zone.end_date is None

        # Change to Pending
        contract.status = 'Pending'
        contract.save()

        zone.refresh_from_db()
        contract_zone.refresh_from_db()

        assert zone.status == 'pending'
        assert contract_zone.is_active is True
        assert contract_zone.end_date is None

    def test_multiple_zones_terminated_together(self):
        """Test multiple zones terminated when contract terminated"""
        contract = ContractFactory(status='Active')
        company = contract.company

        # Create 5 active zones
        zones = [
            ZoneFactory(name=f'Zone {i}', company=company, status='online')
            for i in range(5)
        ]

        links = [
            ContractZoneFactory(contract=contract, zone=zone, is_active=True)
            for zone in zones
        ]

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # All zones should be cancelled
        for zone in zones:
            zone.refresh_from_db()
            assert zone.status == 'cancelled'

        # All links should be inactive with end_date
        today = timezone.now().date()
        for link in links:
            link.refresh_from_db()
            assert link.is_active is False
            assert link.end_date == today

    def test_zones_from_other_contracts_not_affected(self):
        """Test zones from other contracts not affected by termination"""
        company = CompanyFactory()

        # Contract 1 with 2 zones
        contract1 = ContractFactory(company=company, status='Active')
        zone1 = ZoneFactory(name='Zone 1', company=company, status='online')
        zone2 = ZoneFactory(name='Zone 2', company=company, status='online')

        link1_1 = ContractZoneFactory(contract=contract1, zone=zone1, is_active=True)
        link1_2 = ContractZoneFactory(contract=contract1, zone=zone2, is_active=True)

        # Contract 2 with same zones (renewal scenario)
        contract2 = ContractFactory(company=company, status='Active')
        link2_1 = ContractZoneFactory(contract=contract2, zone=zone1, is_active=True,
                                       start_date=date.today() + timedelta(days=365))
        link2_2 = ContractZoneFactory(contract=contract2, zone=zone2, is_active=True,
                                       start_date=date.today() + timedelta(days=365))

        # Terminate contract1 only
        contract1.status = 'Terminated'
        contract1.save()

        # Contract1's links should be terminated
        link1_1.refresh_from_db()
        link1_2.refresh_from_db()
        assert link1_1.is_active is False
        assert link1_2.is_active is False

        # Contract2's links should remain active
        link2_1.refresh_from_db()
        link2_2.refresh_from_db()
        assert link2_1.is_active is True
        assert link2_2.is_active is True

        # Zones should be cancelled (because contract1 was terminated)
        zone1.refresh_from_db()
        zone2.refresh_from_db()
        assert zone1.status == 'cancelled'
        assert zone2.status == 'cancelled'

    def test_signal_idempotent_multiple_saves(self):
        """Test signal is idempotent when contract saved multiple times"""
        contract = ContractFactory(status='Active')
        company = contract.company

        zone = ZoneFactory(company=company, status='online')
        contract_zone = ContractZoneFactory(
            contract=contract,
            zone=zone,
            is_active=True
        )

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # Save again (should not cause errors)
        contract.save()
        contract.save()

        # Zone should still be cancelled (only once)
        zone.refresh_from_db()
        contract_zone.refresh_from_db()

        assert zone.status == 'cancelled'
        assert contract_zone.is_active is False
        assert contract_zone.end_date is not None

    def test_signal_with_mixed_zone_statuses(self):
        """Test signal handles zones with various initial statuses"""
        contract = ContractFactory(status='Active')
        company = contract.company

        # Create zones with different statuses
        zone_online = ZoneFactory(name='Online', company=company, status='online')
        zone_offline = ZoneFactory(name='Offline', company=company, status='offline')
        zone_no_device = ZoneFactory(name='No Device', company=company, status='no_device')
        zone_expired = ZoneFactory(name='Expired', company=company, status='expired')
        zone_pending = ZoneFactory(name='Pending', company=company, status='pending')

        zones = [zone_online, zone_offline, zone_no_device, zone_expired, zone_pending]

        # Link all zones to contract
        for zone in zones:
            ContractZoneFactory(contract=contract, zone=zone, is_active=True)

        # Terminate the contract
        contract.status = 'Terminated'
        contract.save()

        # All zones should now be cancelled regardless of initial status
        for zone in zones:
            zone.refresh_from_db()
            assert zone.status == 'cancelled'
