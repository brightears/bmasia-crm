"""
Cash Flow Statement Service for BMAsia CRM

Generates Cash Flow Statements using the Indirect Method.
Part of the Finance & Accounting Module - Phase 5.

Cash Flow Structure:
- OPERATING ACTIVITIES
  - Cash from customers (Invoice payments received)
  - Cash to suppliers (Operating expense payments)
  - Cash to employees (Salary payments)
  - Net Cash from Operations
- INVESTING ACTIVITIES
  - CapEx purchases (Capital expenditure payments)
  - Asset sales
  - Net Cash from Investing
- FINANCING ACTIVITIES
  - Loan proceeds/repayments
  - Equity injections
  - Dividends paid
  - Net Cash from Financing
- NET CHANGE IN CASH
- OPENING CASH BALANCE
- CLOSING CASH BALANCE

Usage:
    from crm_app.services.cash_flow_service import CashFlowService

    service = CashFlowService()
    cf = service.get_monthly_cash_flow(year=2026, month=1, billing_entity='bmasia_th', currency='THB')
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)


class CashFlowService:
    """
    Service for generating Cash Flow Statements.
    Uses the Indirect Method approach.
    """

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from crm_app.models import (
            Invoice, ExpenseEntry, ExpenseCategory, CashFlowSnapshot
        )
        self.Invoice = Invoice
        self.ExpenseEntry = ExpenseEntry
        self.ExpenseCategory = ExpenseCategory
        self.CashFlowSnapshot = CashFlowSnapshot

    def get_monthly_cash_flow(
        self,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate Cash Flow Statement for a single month.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            billing_entity: Filter by billing entity (bmasia_th, bmasia_hk)
            currency: Filter by currency (THB, USD)

        Returns:
            Complete cash flow statement dictionary
        """
        month_names = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        # Check for existing snapshot with overrides
        snapshot = self._get_snapshot(year, month, billing_entity, currency)

        # Get operating activities
        cash_from_customers, customer_count = self._get_cash_from_customers(
            year, month, billing_entity, currency, snapshot
        )
        cash_to_suppliers, supplier_count = self._get_cash_to_suppliers(
            year, month, billing_entity, currency, snapshot
        )
        cash_to_employees = self._get_cash_to_employees(
            year, month, billing_entity, currency, snapshot
        )
        other_operating = self._get_other_operating(snapshot)

        net_operating = (
            cash_from_customers -
            cash_to_suppliers -
            cash_to_employees +
            other_operating
        )

        # Get investing activities
        capex_purchases, capex_count = self._get_capex_purchases(
            year, month, billing_entity, currency, snapshot
        )
        asset_sales = self._get_asset_sales(snapshot)
        other_investing = self._get_other_investing(snapshot)

        net_investing = asset_sales - capex_purchases + other_investing

        # Get financing activities (always from snapshot - manual entry)
        financing = self._get_financing_activities(snapshot)
        net_financing = (
            financing['loan_proceeds'] -
            financing['loan_repayments'] +
            financing['equity_injections'] -
            financing['dividends_paid'] +
            financing['other']
        )

        # Calculate totals
        net_change = net_operating + net_investing + net_financing
        opening_balance = self._get_opening_balance(year, month, billing_entity, currency)
        closing_balance = opening_balance + net_change

        return {
            'period': {
                'year': year,
                'month': month,
                'month_name': month_names[month],
                'type': 'monthly'
            },
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'operating_activities': {
                'cash_from_customers': {
                    'count': customer_count,
                    'value': float(cash_from_customers)
                },
                'cash_to_suppliers': {
                    'count': supplier_count,
                    'value': float(cash_to_suppliers)
                },
                'cash_to_employees': {
                    'value': float(cash_to_employees)
                },
                'other': float(other_operating),
                'net_cash_from_operations': float(net_operating)
            },
            'investing_activities': {
                'capex_purchases': {
                    'count': capex_count,
                    'value': float(capex_purchases)
                },
                'asset_sales': float(asset_sales),
                'other': float(other_investing),
                'net_cash_from_investing': float(net_investing)
            },
            'financing_activities': {
                'loan_proceeds': float(financing['loan_proceeds']),
                'loan_repayments': float(financing['loan_repayments']),
                'equity_injections': float(financing['equity_injections']),
                'dividends_paid': float(financing['dividends_paid']),
                'other': float(financing['other']),
                'net_cash_from_financing': float(net_financing)
            },
            'net_change_in_cash': float(net_change),
            'opening_cash_balance': float(opening_balance),
            'closing_cash_balance': float(closing_balance)
        }

    def get_ytd_cash_flow(
        self,
        year: int,
        through_month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate Year-to-Date Cash Flow Statement.
        Aggregates monthly cash flows from January through the specified month.
        """
        month_names = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        # Initialize accumulators
        total_customers = {'count': 0, 'value': Decimal('0')}
        total_suppliers = {'count': 0, 'value': Decimal('0')}
        total_employees = Decimal('0')
        total_other_operating = Decimal('0')
        total_capex = {'count': 0, 'value': Decimal('0')}
        total_asset_sales = Decimal('0')
        total_other_investing = Decimal('0')
        total_financing = {
            'loan_proceeds': Decimal('0'),
            'loan_repayments': Decimal('0'),
            'equity_injections': Decimal('0'),
            'dividends_paid': Decimal('0'),
            'other': Decimal('0')
        }

        # Aggregate each month
        for month in range(1, through_month + 1):
            monthly = self.get_monthly_cash_flow(year, month, billing_entity, currency)

            # Operating
            total_customers['count'] += monthly['operating_activities']['cash_from_customers']['count']
            total_customers['value'] += Decimal(str(monthly['operating_activities']['cash_from_customers']['value']))
            total_suppliers['count'] += monthly['operating_activities']['cash_to_suppliers']['count']
            total_suppliers['value'] += Decimal(str(monthly['operating_activities']['cash_to_suppliers']['value']))
            total_employees += Decimal(str(monthly['operating_activities']['cash_to_employees']['value']))
            total_other_operating += Decimal(str(monthly['operating_activities']['other']))

            # Investing
            total_capex['count'] += monthly['investing_activities']['capex_purchases']['count']
            total_capex['value'] += Decimal(str(monthly['investing_activities']['capex_purchases']['value']))
            total_asset_sales += Decimal(str(monthly['investing_activities']['asset_sales']))
            total_other_investing += Decimal(str(monthly['investing_activities']['other']))

            # Financing
            total_financing['loan_proceeds'] += Decimal(str(monthly['financing_activities']['loan_proceeds']))
            total_financing['loan_repayments'] += Decimal(str(monthly['financing_activities']['loan_repayments']))
            total_financing['equity_injections'] += Decimal(str(monthly['financing_activities']['equity_injections']))
            total_financing['dividends_paid'] += Decimal(str(monthly['financing_activities']['dividends_paid']))
            total_financing['other'] += Decimal(str(monthly['financing_activities']['other']))

        # Calculate totals
        net_operating = (
            total_customers['value'] -
            total_suppliers['value'] -
            total_employees +
            total_other_operating
        )
        net_investing = (
            total_asset_sales -
            total_capex['value'] +
            total_other_investing
        )
        net_financing = (
            total_financing['loan_proceeds'] -
            total_financing['loan_repayments'] +
            total_financing['equity_injections'] -
            total_financing['dividends_paid'] +
            total_financing['other']
        )
        net_change = net_operating + net_investing + net_financing

        # Opening balance from January
        opening_balance = self._get_opening_balance(year, 1, billing_entity, currency)
        closing_balance = opening_balance + net_change

        return {
            'period': {
                'year': year,
                'through_month': through_month,
                'through_month_name': month_names[through_month],
                'type': 'ytd'
            },
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'operating_activities': {
                'cash_from_customers': {
                    'count': total_customers['count'],
                    'value': float(total_customers['value'])
                },
                'cash_to_suppliers': {
                    'count': total_suppliers['count'],
                    'value': float(total_suppliers['value'])
                },
                'cash_to_employees': {
                    'value': float(total_employees)
                },
                'other': float(total_other_operating),
                'net_cash_from_operations': float(net_operating)
            },
            'investing_activities': {
                'capex_purchases': {
                    'count': total_capex['count'],
                    'value': float(total_capex['value'])
                },
                'asset_sales': float(total_asset_sales),
                'other': float(total_other_investing),
                'net_cash_from_investing': float(net_investing)
            },
            'financing_activities': {
                'loan_proceeds': float(total_financing['loan_proceeds']),
                'loan_repayments': float(total_financing['loan_repayments']),
                'equity_injections': float(total_financing['equity_injections']),
                'dividends_paid': float(total_financing['dividends_paid']),
                'other': float(total_financing['other']),
                'net_cash_from_financing': float(net_financing)
            },
            'net_change_in_cash': float(net_change),
            'opening_cash_balance': float(opening_balance),
            'closing_cash_balance': float(closing_balance)
        }

    def get_monthly_trend(
        self,
        year: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Get monthly cash flow trend for charts.
        Returns summarized data for each month up to current month.
        """
        trends = []
        month_names = [
            '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ]
        current_month = date.today().month if date.today().year == year else 12

        for month in range(1, current_month + 1):
            cf = self.get_monthly_cash_flow(year, month, billing_entity, currency)
            trends.append({
                'month': month,
                'month_name': month_names[month],
                'operating': cf['operating_activities']['net_cash_from_operations'],
                'investing': cf['investing_activities']['net_cash_from_investing'],
                'financing': cf['financing_activities']['net_cash_from_financing'],
                'net_change': cf['net_change_in_cash'],
                'closing_balance': cf['closing_cash_balance']
            })

        return {
            'year': year,
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'months': trends
        }

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _get_snapshot(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str
    ) -> Optional['CashFlowSnapshot']:
        """Get existing snapshot if one exists."""
        try:
            filters = {'year': year, 'month': month}
            if billing_entity:
                filters['billing_entity'] = billing_entity
            if currency:
                filters['currency'] = currency

            return self.CashFlowSnapshot.objects.filter(**filters).first()
        except Exception:
            return None

    def _get_cash_from_customers(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['CashFlowSnapshot']
    ) -> Tuple[Decimal, int]:
        """
        Get cash received from customer invoice payments.
        Uses snapshot override if set, otherwise calculates from Invoice payments.
        """
        # Check for override
        if snapshot and snapshot.cash_from_customers is not None:
            return snapshot.cash_from_customers, 0

        # Calculate from invoices
        queryset = self.Invoice.objects.filter(
            status='Paid',
            paid_date__year=year,
            paid_date__month=month
        )

        if billing_entity:
            queryset = queryset.filter(contract__company__billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        result = queryset.aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )

        return result['total'] or Decimal('0'), result['count'] or 0

    def _get_cash_to_suppliers(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['CashFlowSnapshot']
    ) -> Tuple[Decimal, int]:
        """
        Get cash paid to suppliers (non-salary operating expenses).
        """
        # Check for override
        if snapshot and snapshot.cash_to_suppliers is not None:
            return snapshot.cash_to_suppliers, 0

        # Calculate from expenses (exclude salary-related)
        queryset = self.ExpenseEntry.objects.filter(
            status='paid',
            payment_date__year=year,
            payment_date__month=month,
            category__category_type__in=['opex_cogs', 'opex_gna', 'opex_sales']
        ).exclude(
            Q(category__name__icontains='salary') |
            Q(category__name__icontains='salaries') |
            Q(category__name__icontains='payroll') |
            Q(category__name__icontains='wage')
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        result = queryset.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )

        return result['total'] or Decimal('0'), result['count'] or 0

    def _get_cash_to_employees(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['CashFlowSnapshot']
    ) -> Decimal:
        """
        Get cash paid for salaries/payroll.
        """
        # Check for override
        if snapshot and snapshot.cash_to_employees is not None:
            return snapshot.cash_to_employees

        # Calculate from salary-related expenses
        queryset = self.ExpenseEntry.objects.filter(
            status='paid',
            payment_date__year=year,
            payment_date__month=month
        ).filter(
            Q(category__name__icontains='salary') |
            Q(category__name__icontains='salaries') |
            Q(category__name__icontains='payroll') |
            Q(category__name__icontains='wage')
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        result = queryset.aggregate(total=Sum('amount'))

        return result['total'] or Decimal('0')

    def _get_other_operating(self, snapshot: Optional['CashFlowSnapshot']) -> Decimal:
        """Get other operating cash flows from snapshot."""
        if snapshot:
            return snapshot.other_operating_cash or Decimal('0')
        return Decimal('0')

    def _get_capex_purchases(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['CashFlowSnapshot']
    ) -> Tuple[Decimal, int]:
        """
        Get cash paid for capital expenditures.
        """
        # Check for override
        if snapshot and snapshot.capex_purchases is not None:
            return snapshot.capex_purchases, 0

        # Calculate from CapEx expenses
        queryset = self.ExpenseEntry.objects.filter(
            status='paid',
            payment_date__year=year,
            payment_date__month=month,
            category__category_type='capex'
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        result = queryset.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )

        return result['total'] or Decimal('0'), result['count'] or 0

    def _get_asset_sales(self, snapshot: Optional['CashFlowSnapshot']) -> Decimal:
        """Get asset sales from snapshot (manual entry)."""
        if snapshot:
            return snapshot.asset_sales or Decimal('0')
        return Decimal('0')

    def _get_other_investing(self, snapshot: Optional['CashFlowSnapshot']) -> Decimal:
        """Get other investing cash flows from snapshot."""
        if snapshot:
            return snapshot.other_investing_cash or Decimal('0')
        return Decimal('0')

    def _get_financing_activities(self, snapshot: Optional['CashFlowSnapshot']) -> Dict:
        """Get all financing activities from snapshot (all manual entry)."""
        if snapshot:
            return {
                'loan_proceeds': snapshot.loan_proceeds or Decimal('0'),
                'loan_repayments': snapshot.loan_repayments or Decimal('0'),
                'equity_injections': snapshot.equity_injections or Decimal('0'),
                'dividends_paid': snapshot.dividends_paid or Decimal('0'),
                'other': snapshot.other_financing_cash or Decimal('0')
            }
        return {
            'loan_proceeds': Decimal('0'),
            'loan_repayments': Decimal('0'),
            'equity_injections': Decimal('0'),
            'dividends_paid': Decimal('0'),
            'other': Decimal('0')
        }

    def _get_opening_balance(
        self,
        year: int,
        month: int,
        billing_entity: str,
        currency: str
    ) -> Decimal:
        """
        Get opening cash balance for the period.
        Tries to get from snapshot, or calculates from prior period's closing.
        """
        # Try to get from this month's snapshot
        snapshot = self._get_snapshot(year, month, billing_entity, currency)
        if snapshot and snapshot.opening_cash_balance:
            return snapshot.opening_cash_balance

        # Try to get from previous month's closing
        if month == 1:
            # First month of year - check December of prior year
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        prev_snapshot = self._get_snapshot(prev_year, prev_month, billing_entity, currency)
        if prev_snapshot and prev_snapshot.opening_cash_balance:
            # Calculate closing from previous period
            prev_cf = self.get_monthly_cash_flow(prev_year, prev_month, billing_entity, currency)
            return Decimal(str(prev_cf['closing_cash_balance']))

        # Default to zero if no prior data
        return Decimal('0')
