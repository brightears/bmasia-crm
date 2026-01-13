"""
Revenue Tracking Service for BMAsia CRM

Handles automatic contract lifecycle classification and revenue event tracking.
Part of the Finance & Accounting Module - Phase 1.

Lifecycle Types:
- new: First contract for a company
- renewal: Contract that follows an expired/renewed previous contract
- addon: Zones added to an existing active contract (mid-contract expansion)
- churn: Contract terminated or cancelled

Usage:
    from crm_app.services.revenue_tracking_service import RevenueTrackingService

    # Auto-classify a single contract
    service = RevenueTrackingService()
    service.classify_contract(contract)

    # Classify all unclassified contracts
    service.classify_all_contracts()

    # Generate monthly snapshot for a period
    service.generate_monthly_snapshot(year=2026, month=1)
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List, Dict
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class RevenueTrackingService:
    """
    Service for automatic contract lifecycle classification and revenue tracking.
    """

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from crm_app.models import (
            Contract, ContractZone, MonthlyRevenueSnapshot,
            MonthlyRevenueTarget, ContractRevenueEvent
        )
        self.Contract = Contract
        self.ContractZone = ContractZone
        self.MonthlyRevenueSnapshot = MonthlyRevenueSnapshot
        self.MonthlyRevenueTarget = MonthlyRevenueTarget
        self.ContractRevenueEvent = ContractRevenueEvent

    # =========================================================================
    # CONTRACT LIFECYCLE CLASSIFICATION
    # =========================================================================

    def classify_contract(self, contract, force: bool = False) -> str:
        """
        Determine and set the lifecycle type for a single contract.

        Args:
            contract: Contract instance to classify
            force: If True, reclassify even if manually set

        Returns:
            The determined lifecycle type ('new', 'renewal', 'addon', 'churn')
        """
        # Skip if manually set (unless forced)
        if contract.lifecycle_type_manually_set and not force:
            logger.debug(f"Skipping {contract.contract_number}: manually set")
            return contract.lifecycle_type

        lifecycle_type = self._determine_lifecycle_type(contract)

        # Update contract if changed
        if contract.lifecycle_type != lifecycle_type:
            contract.lifecycle_type = lifecycle_type
            contract.lifecycle_effective_date = self._get_effective_date(contract, lifecycle_type)
            contract.save(update_fields=['lifecycle_type', 'lifecycle_effective_date', 'updated_at'])
            logger.info(f"Classified {contract.contract_number} as '{lifecycle_type}'")

        return lifecycle_type

    def _determine_lifecycle_type(self, contract) -> str:
        """
        Core logic for determining contract lifecycle type.

        Decision tree:
        1. If status is Terminated → churn
        2. If no prior contracts for company → new
        3. If follows an expired/renewed contract → renewal
        4. If zones were added mid-term → addon (handled separately)
        5. Default → new
        """
        # Check for churn first
        if contract.status in ['Terminated']:
            return 'churn'

        # Get prior contracts for this company (excluding current)
        prior_contracts = self.Contract.objects.filter(
            company=contract.company,
            start_date__lt=contract.start_date
        ).exclude(id=contract.id).order_by('-end_date')

        if not prior_contracts.exists():
            # First contract for this company
            return 'new'

        # Check if this is a renewal of a prior contract
        most_recent = prior_contracts.first()

        # Renewal conditions:
        # 1. Prior contract ended (Expired/Renewed) and this one started around same time
        # 2. OR prior contract was terminated and this is a "win-back"
        if most_recent:
            # Allow 90 day gap for renewal classification
            gap_days = (contract.start_date - most_recent.end_date).days

            if most_recent.status in ['Expired', 'Renewed', 'Active'] and -30 <= gap_days <= 90:
                return 'renewal'

            # If there's an active contract and this is new, it could be an expansion
            # But we treat zone additions separately via events
            active_contracts = self.Contract.objects.filter(
                company=contract.company,
                status='Active',
                start_date__lte=contract.start_date,
                end_date__gte=contract.start_date
            ).exclude(id=contract.id)

            if active_contracts.exists():
                # There's already an active contract - this might be additional scope
                # But we classify the contract itself as new
                return 'new'

        # Default to new for any other case
        return 'new'

    def _get_effective_date(self, contract, lifecycle_type: str) -> date:
        """
        Determine the effective date for the lifecycle type.

        - new/renewal: contract start_date
        - churn: contract end_date (or termination date)
        - addon: will be set when zone is added
        """
        if lifecycle_type == 'churn':
            return contract.end_date or date.today()
        return contract.start_date

    def classify_all_contracts(self, force: bool = False) -> Dict[str, int]:
        """
        Classify all contracts that don't have a lifecycle type set.

        Args:
            force: If True, reclassify all contracts (except manually set ones)

        Returns:
            Dict with counts per lifecycle type
        """
        if force:
            contracts = self.Contract.objects.filter(lifecycle_type_manually_set=False)
        else:
            contracts = self.Contract.objects.filter(lifecycle_type='')

        results = {'new': 0, 'renewal': 0, 'addon': 0, 'churn': 0}

        for contract in contracts:
            lifecycle_type = self.classify_contract(contract, force=force)
            if lifecycle_type in results:
                results[lifecycle_type] += 1

        logger.info(f"Classified {sum(results.values())} contracts: {results}")
        return results

    # =========================================================================
    # ZONE ADDITION TRACKING (Add-ons)
    # =========================================================================

    def track_zone_addition(
        self,
        contract,
        zones: List,
        added_by=None,
        value_increase: Decimal = None,
        notes: str = ''
    ):
        """
        Track zone addition to an active contract as an add-on event.

        This creates a ContractRevenueEvent to record the expansion.

        Args:
            contract: Contract the zones are being added to
            zones: List of Zone instances being added
            added_by: User who added the zones
            value_increase: Optional value increase from adding zones
            notes: Optional notes about the addition
        """
        if not zones:
            return

        zone_count = len(zones)

        # Create revenue event
        event = self.ContractRevenueEvent.objects.create(
            contract=contract,
            event_type='addon_zones',
            event_date=date.today(),
            zone_count_change=zone_count,
            contract_value_change=value_increase or Decimal('0'),
            monthly_value_change=self._calculate_monthly_value(value_increase, contract),
            notes=notes or f"Added {zone_count} zone(s): {', '.join(z.name for z in zones)}",
            created_by=added_by
        )

        logger.info(f"Tracked zone addition: {zone_count} zones to {contract.contract_number}")
        return event

    def track_zone_removal(
        self,
        contract,
        zones: List,
        removed_by=None,
        value_decrease: Decimal = None,
        notes: str = ''
    ):
        """
        Track zone removal from a contract.
        """
        if not zones:
            return

        zone_count = len(zones)

        event = self.ContractRevenueEvent.objects.create(
            contract=contract,
            event_type='removal_zones',
            event_date=date.today(),
            zone_count_change=-zone_count,
            contract_value_change=-(value_decrease or Decimal('0')),
            monthly_value_change=-self._calculate_monthly_value(value_decrease, contract),
            notes=notes or f"Removed {zone_count} zone(s): {', '.join(z.name for z in zones)}",
            created_by=removed_by
        )

        logger.info(f"Tracked zone removal: {zone_count} zones from {contract.contract_number}")
        return event

    def _calculate_monthly_value(self, total_value: Optional[Decimal], contract) -> Decimal:
        """Calculate monthly value from total contract value change."""
        if not total_value:
            return Decimal('0')

        # Calculate contract duration in months
        if contract.start_date and contract.end_date:
            days = (contract.end_date - contract.start_date).days
            months = max(1, days / 30)
            return Decimal(str(round(float(total_value) / months, 2)))

        return total_value / 12  # Default to annual

    # =========================================================================
    # REVENUE EVENT CREATION
    # =========================================================================

    def create_contract_event(
        self,
        contract,
        event_type: str,
        event_date: date = None,
        value_change: Decimal = None,
        zone_count_change: int = 0,
        expected_payment_date: date = None,
        actual_payment_date: date = None,
        payment_amount: Decimal = None,
        notes: str = '',
        created_by=None
    ):
        """
        Create a revenue event for a contract.

        Event types:
        - new_contract: New contract signed
        - renewal: Contract renewed
        - addon_zones: Zones added
        - removal_zones: Zones removed
        - value_increase: Value increased
        - value_decrease: Value decreased
        - payment_received: Payment received
        - payment_overdue: Payment overdue
        - churn: Contract churned/canceled
        - reactivation: Contract reactivated
        """
        event = self.ContractRevenueEvent.objects.create(
            contract=contract,
            event_type=event_type,
            event_date=event_date or date.today(),
            contract_value_change=value_change or Decimal('0'),
            monthly_value_change=self._calculate_monthly_value(value_change, contract),
            zone_count_change=zone_count_change,
            expected_payment_date=expected_payment_date,
            actual_payment_date=actual_payment_date,
            payment_amount=payment_amount,
            notes=notes,
            created_by=created_by
        )

        logger.info(f"Created {event_type} event for {contract.contract_number}")
        return event

    def create_new_contract_event(self, contract, created_by=None):
        """Create event for a new contract being signed."""
        zone_count = contract.zones.count()

        return self.create_contract_event(
            contract=contract,
            event_type='new_contract',
            event_date=contract.start_date,
            value_change=contract.value,
            zone_count_change=zone_count,
            notes=f"New contract signed: {contract.contract_number}",
            created_by=created_by
        )

    def create_renewal_event(self, contract, prior_contract=None, created_by=None):
        """Create event for a contract renewal."""
        zone_count = contract.zones.count()
        value_change = contract.value

        if prior_contract:
            value_change = contract.value - prior_contract.value

        return self.create_contract_event(
            contract=contract,
            event_type='renewal',
            event_date=contract.start_date,
            value_change=value_change,
            zone_count_change=zone_count,
            notes=f"Contract renewed from {prior_contract.contract_number if prior_contract else 'unknown'}",
            created_by=created_by
        )

    def create_churn_event(self, contract, created_by=None):
        """Create event for contract churn/cancellation."""
        zone_count = contract.zones.count()

        return self.create_contract_event(
            contract=contract,
            event_type='churn',
            event_date=contract.end_date or date.today(),
            value_change=-contract.value,
            zone_count_change=-zone_count,
            notes=f"Contract cancelled/churned: {contract.contract_number}",
            created_by=created_by
        )

    # =========================================================================
    # MONTHLY SNAPSHOT GENERATION
    # =========================================================================

    def generate_monthly_snapshot(
        self,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None,
        force: bool = False
    ) -> List:
        """
        Generate or update monthly revenue snapshots for a given month.

        Calculates actual values from contracts and creates snapshot records.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            billing_entity: Optional filter by billing entity
            currency: Optional filter by currency
            force: If True, recalculate even if already exists

        Returns:
            List of created/updated MonthlyRevenueSnapshot instances
        """
        from crm_app.models import Company

        # Date range for this month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        snapshots = []

        # Determine entities and currencies to process
        entities = [billing_entity] if billing_entity else ['bmasia_th', 'bmasia_hk']
        currencies = [currency] if currency else ['THB', 'USD']
        categories = ['new', 'renewal', 'addon', 'churn']

        for entity in entities:
            for curr in currencies:
                for category in categories:
                    snapshot = self._generate_category_snapshot(
                        year, month, month_start, month_end,
                        category, entity, curr, force
                    )
                    if snapshot:
                        snapshots.append(snapshot)

        logger.info(f"Generated {len(snapshots)} snapshots for {year}-{month:02d}")
        return snapshots

    def _generate_category_snapshot(
        self,
        year: int,
        month: int,
        month_start: date,
        month_end: date,
        category: str,
        billing_entity: str,
        currency: str,
        force: bool
    ) -> Optional['MonthlyRevenueSnapshot']:
        """Generate snapshot for a specific category/entity/currency combination."""

        # Check if snapshot exists and is manually overridden
        existing = self.MonthlyRevenueSnapshot.objects.filter(
            year=year,
            month=month,
            category=category,
            billing_entity=billing_entity,
            currency=currency
        ).first()

        if existing and existing.is_manually_overridden and not force:
            logger.debug(f"Skipping {category}/{billing_entity}/{currency}: manually overridden")
            return existing

        # Build base query for contracts
        contracts = self.Contract.objects.filter(
            currency=currency,
            company__billing_entity=billing_entity,
            lifecycle_type=category
        )

        # Filter by date based on category
        if category == 'churn':
            # Churn: contracts that ended this month
            contracts = contracts.filter(
                lifecycle_effective_date__gte=month_start,
                lifecycle_effective_date__lte=month_end
            )
        else:
            # New/Renewal/Addon: contracts that started this month
            contracts = contracts.filter(
                lifecycle_effective_date__gte=month_start,
                lifecycle_effective_date__lte=month_end
            )

        # Calculate totals
        totals = contracts.aggregate(
            total_count=Count('id'),
            total_value=Sum('value')
        )

        contract_count = totals['total_count'] or 0
        contracted_value = totals['total_value'] or Decimal('0')

        # For churn, make value negative
        if category == 'churn':
            contracted_value = -abs(contracted_value)

        # Calculate cash received (from paid invoices in this period)
        # This is simplified - in production would query Invoice model
        cash_received = Decimal('0')  # TODO: Calculate from invoices

        # Create or update snapshot
        snapshot, created = self.MonthlyRevenueSnapshot.objects.update_or_create(
            year=year,
            month=month,
            category=category,
            billing_entity=billing_entity,
            currency=currency,
            defaults={
                'contract_count': contract_count,
                'contracted_value': contracted_value,
                'cash_received': cash_received,
            }
        )

        action = "Created" if created else "Updated"
        logger.debug(f"{action} snapshot: {year}-{month:02d} {category}/{billing_entity}/{currency}")

        return snapshot

    def generate_snapshots_for_year(self, year: int, force: bool = False) -> List:
        """Generate monthly snapshots for an entire year."""
        all_snapshots = []

        for month in range(1, 13):
            snapshots = self.generate_monthly_snapshot(year, month, force=force)
            all_snapshots.extend(snapshots)

        return all_snapshots

    # =========================================================================
    # YEAR-OVER-YEAR COMPARISON
    # =========================================================================

    def get_yoy_comparison(
        self,
        year: int,
        billing_entity: str = None,
        currency: str = 'USD'
    ) -> Dict:
        """
        Get year-over-year comparison data.

        Returns:
            Dict with 'current_year', 'prior_year', and 'change' data
        """
        prior_year = year - 1

        def get_year_totals(y: int) -> Dict:
            query = self.MonthlyRevenueSnapshot.objects.filter(
                year=y,
                currency=currency
            )
            if billing_entity:
                query = query.filter(billing_entity=billing_entity)

            totals = query.values('category').annotate(
                total_contracts=Sum('contract_count'),
                total_value=Sum('contracted_value'),
                total_cash=Sum('cash_received')
            )

            return {item['category']: item for item in totals}

        current = get_year_totals(year)
        prior = get_year_totals(prior_year)

        categories = ['new', 'renewal', 'addon', 'churn']
        result = {
            'current_year': year,
            'prior_year': prior_year,
            'categories': {}
        }

        for cat in categories:
            curr_data = current.get(cat, {'total_contracts': 0, 'total_value': 0, 'total_cash': 0})
            prior_data = prior.get(cat, {'total_contracts': 0, 'total_value': 0, 'total_cash': 0})

            curr_value = curr_data.get('total_value') or 0
            prior_value = prior_data.get('total_value') or 0

            change_pct = 0
            if prior_value and prior_value != 0:
                change_pct = ((curr_value - prior_value) / abs(prior_value)) * 100

            result['categories'][cat] = {
                'current': curr_data,
                'prior': prior_data,
                'change_value': curr_value - prior_value,
                'change_percent': round(change_pct, 1)
            }

        return result

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    @transaction.atomic
    def initialize_from_existing_contracts(self, created_by=None) -> Dict:
        """
        Initialize lifecycle types and create events for all existing contracts.

        Use this when setting up the finance module for the first time.

        Returns:
            Dict with summary of operations performed
        """
        results = {
            'contracts_classified': 0,
            'events_created': 0,
            'errors': []
        }

        # First, classify all contracts
        classification = self.classify_all_contracts(force=True)
        results['contracts_classified'] = sum(classification.values())

        # Then, create initial events for each contract
        for contract in self.Contract.objects.all():
            try:
                if contract.lifecycle_type == 'new':
                    self.create_new_contract_event(contract, created_by)
                elif contract.lifecycle_type == 'renewal':
                    self.create_renewal_event(contract, created_by=created_by)
                elif contract.lifecycle_type == 'churn':
                    self.create_churn_event(contract, created_by)
                # addon events are created when zones are added

                results['events_created'] += 1
            except Exception as e:
                results['errors'].append(f"{contract.contract_number}: {str(e)}")
                logger.error(f"Error creating event for {contract.contract_number}: {e}")

        logger.info(f"Initialized finance tracking: {results}")
        return results


# Convenience function for one-time initialization
def initialize_finance_module(created_by=None):
    """
    Initialize the finance module for all existing data.

    Run this once when first setting up the Finance Module.

    Usage:
        from crm_app.services.revenue_tracking_service import initialize_finance_module
        initialize_finance_module()
    """
    service = RevenueTrackingService()
    return service.initialize_from_existing_contracts(created_by)
