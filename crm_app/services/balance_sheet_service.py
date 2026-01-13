"""
Balance Sheet Service for BMAsia CRM

Generates Balance Sheets for quarterly financial reporting.
Part of the Finance & Accounting Module - Phase 6.

Balance Sheet Structure:
- ASSETS
  - Current Assets
    - Cash & Bank (from CashFlowSnapshot closing balance or calculate)
    - Accounts Receivable (from Invoice where status in Sent, Overdue)
    - Other Current Assets (manual entry)
  - Fixed Assets
    - Gross Fixed Assets (cumulative CapEx from ExpenseEntry)
    - Less: Accumulated Depreciation
    - Net Fixed Assets
  - TOTAL ASSETS

- LIABILITIES
  - Current Liabilities
    - Accounts Payable (from ExpenseEntry where status in pending, approved)
    - Accrued Expenses (manual entry)
    - Other Current Liabilities (manual entry)
  - Long-term Liabilities
    - Long-term Debt (manual entry)
    - Other Long-term Liabilities (manual entry)
  - TOTAL LIABILITIES

- EQUITY
  - Share Capital (manual entry)
  - Additional Paid-in Capital (manual entry)
  - Retained Earnings (cumulative P&L net profit)
  - Other Equity (manual entry)
  - TOTAL EQUITY

ACCOUNTING EQUATION: Assets = Liabilities + Equity

Depreciation Rates (Thailand/HK tax rules):
- Computer Equipment: 3 years (33.33% per year)
- Office Equipment: 5 years (20% per year)

Usage:
    from crm_app.services.balance_sheet_service import BalanceSheetService

    service = BalanceSheetService()
    bs = service.get_quarterly_balance_sheet(year=2026, quarter=1, billing_entity='bmasia_th', currency='THB')
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
from django.db.models import Sum, Q

logger = logging.getLogger(__name__)


class BalanceSheetService:
    """
    Service for generating Balance Sheet statements.
    """

    # Depreciation rates by asset category (annual percentage)
    DEPRECIATION_RATES = {
        'computer': Decimal('0.3333'),  # 3-year useful life (33.33%)
        'office': Decimal('0.20'),       # 5-year useful life (20%)
        'default': Decimal('0.20'),      # Default to 5 years
    }

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from crm_app.models import (
            Invoice, ExpenseEntry, ExpenseCategory,
            CashFlowSnapshot, BalanceSheetSnapshot
        )
        self.Invoice = Invoice
        self.ExpenseEntry = ExpenseEntry
        self.ExpenseCategory = ExpenseCategory
        self.CashFlowSnapshot = CashFlowSnapshot
        self.BalanceSheetSnapshot = BalanceSheetSnapshot

    def get_quarterly_balance_sheet(
        self,
        year: int,
        quarter: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate Balance Sheet for a specific quarter.

        Args:
            year: Year (e.g., 2026)
            quarter: Quarter (1-4)
            billing_entity: Filter by billing entity (bmasia_th, bmasia_hk)
            currency: Filter by currency (THB, USD)

        Returns:
            Complete balance sheet dictionary with:
            - period info
            - assets (current + fixed)
            - liabilities (current + long-term)
            - equity
            - is_balanced check
        """
        quarter_names = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
        quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}

        # Get as_of_date (last day of quarter)
        end_month = quarter_months[quarter][1]
        if end_month == 12:
            as_of_date = date(year, 12, 31)
        else:
            # Last day of end_month
            next_month_first = date(year, end_month + 1, 1)
            as_of_date = date(next_month_first.year, next_month_first.month, 1)
            from datetime import timedelta
            as_of_date = as_of_date - timedelta(days=1)

        # Check for existing snapshot with overrides
        snapshot = self._get_snapshot(year, quarter, billing_entity, currency)

        # =======================================================================
        # ASSETS
        # =======================================================================

        # Current Assets
        cash_and_bank = self._get_cash_and_bank(
            year, quarter, billing_entity, currency, snapshot
        )
        accounts_receivable, ar_details = self._get_accounts_receivable(
            year, quarter, billing_entity, currency, snapshot
        )
        other_current_assets = self._get_other_current_assets(snapshot)

        total_current_assets = cash_and_bank + accounts_receivable + other_current_assets

        # Fixed Assets
        gross_fixed_assets, capex_details = self._get_gross_fixed_assets(
            year, quarter, billing_entity, currency, snapshot
        )
        accumulated_depreciation = self._get_accumulated_depreciation(
            year, quarter, billing_entity, currency, snapshot
        )
        net_fixed_assets = gross_fixed_assets - accumulated_depreciation

        total_assets = total_current_assets + net_fixed_assets

        # =======================================================================
        # LIABILITIES
        # =======================================================================

        # Current Liabilities
        accounts_payable, ap_details = self._get_accounts_payable(
            year, quarter, billing_entity, currency, snapshot
        )
        accrued_expenses = self._get_accrued_expenses(snapshot)
        other_current_liabilities = self._get_other_current_liabilities(snapshot)

        total_current_liabilities = accounts_payable + accrued_expenses + other_current_liabilities

        # Long-term Liabilities
        long_term_debt = self._get_long_term_debt(snapshot)
        other_long_term_liabilities = self._get_other_long_term_liabilities(snapshot)

        total_long_term_liabilities = long_term_debt + other_long_term_liabilities
        total_liabilities = total_current_liabilities + total_long_term_liabilities

        # =======================================================================
        # EQUITY
        # =======================================================================

        share_capital = self._get_share_capital(snapshot)
        additional_paid_in_capital = self._get_additional_paid_in_capital(snapshot)
        retained_earnings = self._get_retained_earnings(
            year, quarter, billing_entity, currency, snapshot
        )
        other_equity = self._get_other_equity(snapshot)

        total_equity = share_capital + additional_paid_in_capital + retained_earnings + other_equity

        # =======================================================================
        # BALANCE CHECK
        # =======================================================================

        total_liabilities_and_equity = total_liabilities + total_equity
        is_balanced = abs(total_assets - total_liabilities_and_equity) < Decimal('0.01')

        return {
            'period': {
                'year': year,
                'quarter': quarter,
                'quarter_name': quarter_names[quarter],
                'as_of_date': as_of_date.isoformat(),
                'type': 'quarterly'
            },
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'assets': {
                'current_assets': {
                    'cash_and_bank': float(cash_and_bank),
                    'accounts_receivable': {
                        'total': float(accounts_receivable),
                        'details': ar_details
                    },
                    'other_current_assets': float(other_current_assets),
                    'total': float(total_current_assets)
                },
                'fixed_assets': {
                    'gross_fixed_assets': {
                        'total': float(gross_fixed_assets),
                        'details': capex_details
                    },
                    'accumulated_depreciation': float(accumulated_depreciation),
                    'net_fixed_assets': float(net_fixed_assets)
                },
                'total_assets': float(total_assets)
            },
            'liabilities': {
                'current_liabilities': {
                    'accounts_payable': {
                        'total': float(accounts_payable),
                        'details': ap_details
                    },
                    'accrued_expenses': float(accrued_expenses),
                    'other_current_liabilities': float(other_current_liabilities),
                    'total': float(total_current_liabilities)
                },
                'long_term_liabilities': {
                    'long_term_debt': float(long_term_debt),
                    'other_long_term_liabilities': float(other_long_term_liabilities),
                    'total': float(total_long_term_liabilities)
                },
                'total_liabilities': float(total_liabilities)
            },
            'equity': {
                'share_capital': float(share_capital),
                'additional_paid_in_capital': float(additional_paid_in_capital),
                'retained_earnings': float(retained_earnings),
                'other_equity': float(other_equity),
                'total_equity': float(total_equity)
            },
            'total_liabilities_and_equity': float(total_liabilities_and_equity),
            'is_balanced': is_balanced,
            'balance_difference': float(total_assets - total_liabilities_and_equity)
        }

    def get_quarterly_trend(
        self,
        year: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Get quarterly balance sheet trend for charts.
        Returns summarized data for each quarter up to current quarter.
        """
        trends = []
        quarter_names = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}

        # Determine current quarter
        today = date.today()
        if today.year == year:
            current_quarter = (today.month - 1) // 3 + 1
        else:
            current_quarter = 4

        for quarter in range(1, current_quarter + 1):
            bs = self.get_quarterly_balance_sheet(year, quarter, billing_entity, currency)
            trends.append({
                'quarter': quarter,
                'quarter_name': quarter_names[quarter],
                'total_assets': bs['assets']['total_assets'],
                'total_liabilities': bs['liabilities']['total_liabilities'],
                'total_equity': bs['equity']['total_equity'],
                'current_ratio': round(
                    bs['assets']['current_assets']['total'] /
                    bs['liabilities']['current_liabilities']['total']
                    if bs['liabilities']['current_liabilities']['total'] > 0 else 0,
                    2
                ),
                'is_balanced': bs['is_balanced']
            })

        return {
            'year': year,
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'quarters': trends
        }

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _get_snapshot(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str
    ) -> Optional['BalanceSheetSnapshot']:
        """Get existing snapshot if one exists."""
        try:
            filters = {'year': year, 'quarter': quarter}
            if billing_entity:
                filters['billing_entity'] = billing_entity
            if currency:
                filters['currency'] = currency

            return self.BalanceSheetSnapshot.objects.filter(**filters).first()
        except Exception:
            return None

    def _get_quarter_end_month(self, quarter: int) -> int:
        """Get the ending month number for a quarter."""
        return {1: 3, 2: 6, 3: 9, 4: 12}[quarter]

    def _get_cash_and_bank(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Decimal:
        """
        Get cash and bank balance.
        Uses snapshot override if set, otherwise from CashFlowSnapshot closing balance.
        """
        # Check for override
        if snapshot and snapshot.cash_and_bank is not None:
            return snapshot.cash_and_bank

        # Get from CashFlowSnapshot for the last month of the quarter
        end_month = self._get_quarter_end_month(quarter)

        try:
            filters = {'year': year, 'month': end_month}
            if billing_entity:
                filters['billing_entity'] = billing_entity
            if currency:
                filters['currency'] = currency

            cf_snapshot = self.CashFlowSnapshot.objects.filter(**filters).first()
            if cf_snapshot and cf_snapshot.opening_cash_balance:
                # Calculate closing balance from CashFlowService
                from crm_app.services.cash_flow_service import CashFlowService
                cf_service = CashFlowService()
                cf = cf_service.get_monthly_cash_flow(year, end_month, billing_entity, currency)
                return Decimal(str(cf['closing_cash_balance']))
        except Exception as e:
            logger.warning(f"Error getting cash balance from CashFlowSnapshot: {e}")

        return Decimal('0')

    def _get_accounts_receivable(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Tuple[Decimal, Dict]:
        """
        Get accounts receivable (outstanding customer invoices).
        Uses snapshot override if set, otherwise calculates from Invoice.
        """
        details = {
            'sent': {'count': 0, 'value': 0},
            'overdue': {'count': 0, 'value': 0}
        }

        # Check for override
        if snapshot and snapshot.accounts_receivable is not None:
            return snapshot.accounts_receivable, details

        # Calculate from invoices with status Sent or Overdue
        # As of the quarter end date
        end_month = self._get_quarter_end_month(quarter)
        if end_month == 12:
            as_of_date = date(year, 12, 31)
        else:
            from datetime import timedelta
            next_month = date(year, end_month + 1, 1)
            as_of_date = next_month - timedelta(days=1)

        queryset = self.Invoice.objects.filter(
            issue_date__lte=as_of_date,
            status__in=['Sent', 'Overdue']
        )

        if billing_entity:
            queryset = queryset.filter(contract__company__billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        # Get totals by status
        for status in ['Sent', 'Overdue']:
            status_qs = queryset.filter(status=status)
            agg = status_qs.aggregate(total=Sum('total_amount'))
            count = status_qs.count()
            value = agg['total'] or Decimal('0')

            key = status.lower()
            details[key] = {'count': count, 'value': float(value)}

        total_ar = Decimal(str(details['sent']['value'])) + Decimal(str(details['overdue']['value']))
        return total_ar, details

    def _get_other_current_assets(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get other current assets from snapshot (manual entry)."""
        if snapshot:
            return snapshot.other_current_assets or Decimal('0')
        return Decimal('0')

    def _get_gross_fixed_assets(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Tuple[Decimal, Dict]:
        """
        Get gross fixed assets (cumulative CapEx purchases).
        Uses snapshot override if set, otherwise calculates from ExpenseEntry.
        """
        details = {
            'computer_equipment': {'count': 0, 'value': 0},
            'office_equipment': {'count': 0, 'value': 0},
            'other': {'count': 0, 'value': 0}
        }

        # Check for override
        if snapshot and snapshot.gross_fixed_assets is not None:
            return snapshot.gross_fixed_assets, details

        # Calculate from CapEx expenses up to quarter end
        end_month = self._get_quarter_end_month(quarter)
        if end_month == 12:
            as_of_date = date(year, 12, 31)
        else:
            from datetime import timedelta
            next_month = date(year, end_month + 1, 1)
            as_of_date = next_month - timedelta(days=1)

        queryset = self.ExpenseEntry.objects.filter(
            expense_date__lte=as_of_date,
            category__category_type='capex',
            status__in=['approved', 'paid']
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        # Categorize by asset type (based on category name)
        computer_keywords = ['computer', 'laptop', 'server', 'software', 'it equipment']
        office_keywords = ['office', 'furniture', 'fixture']

        total = Decimal('0')

        for expense in queryset:
            cat_name = expense.category.name.lower() if expense.category else ''
            amount = expense.amount or Decimal('0')

            if any(kw in cat_name for kw in computer_keywords):
                details['computer_equipment']['count'] += 1
                details['computer_equipment']['value'] = float(
                    Decimal(str(details['computer_equipment']['value'])) + amount
                )
            elif any(kw in cat_name for kw in office_keywords):
                details['office_equipment']['count'] += 1
                details['office_equipment']['value'] = float(
                    Decimal(str(details['office_equipment']['value'])) + amount
                )
            else:
                details['other']['count'] += 1
                details['other']['value'] = float(
                    Decimal(str(details['other']['value'])) + amount
                )

            total += amount

        return total, details

    def _get_accumulated_depreciation(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Decimal:
        """
        Calculate accumulated depreciation on fixed assets.
        Uses straight-line depreciation based on Thailand/HK tax rules.

        Depreciation rates:
        - Computer equipment: 3 years (33.33% per year)
        - Office equipment: 5 years (20% per year)
        """
        # Check for override
        if snapshot and snapshot.accumulated_depreciation is not None:
            return snapshot.accumulated_depreciation

        # Calculate from CapEx expenses
        end_month = self._get_quarter_end_month(quarter)
        if end_month == 12:
            as_of_date = date(year, 12, 31)
        else:
            from datetime import timedelta
            next_month = date(year, end_month + 1, 1)
            as_of_date = next_month - timedelta(days=1)

        queryset = self.ExpenseEntry.objects.filter(
            expense_date__lte=as_of_date,
            category__category_type='capex',
            status__in=['approved', 'paid']
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        computer_keywords = ['computer', 'laptop', 'server', 'software', 'it equipment']

        total_depreciation = Decimal('0')

        for expense in queryset:
            purchase_date = expense.expense_date
            amount = expense.amount or Decimal('0')
            cat_name = expense.category.name.lower() if expense.category else ''

            # Determine depreciation rate
            if any(kw in cat_name for kw in computer_keywords):
                annual_rate = self.DEPRECIATION_RATES['computer']
            else:
                annual_rate = self.DEPRECIATION_RATES['office']

            # Calculate months of depreciation
            # From purchase date to as_of_date
            if purchase_date > as_of_date:
                continue

            # Calculate full years and remaining months
            months_held = (as_of_date.year - purchase_date.year) * 12 + (as_of_date.month - purchase_date.month)
            if months_held < 0:
                months_held = 0

            # Monthly depreciation = annual rate / 12
            monthly_rate = annual_rate / 12
            total_depreciation_rate = min(monthly_rate * months_held, Decimal('1.0'))  # Cap at 100%

            asset_depreciation = amount * total_depreciation_rate
            total_depreciation += asset_depreciation

        return total_depreciation.quantize(Decimal('0.01'))

    def _get_accounts_payable(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Tuple[Decimal, Dict]:
        """
        Get accounts payable (outstanding vendor payments).
        Uses snapshot override if set, otherwise calculates from ExpenseEntry.
        """
        details = {
            'pending': {'count': 0, 'value': 0},
            'approved': {'count': 0, 'value': 0}
        }

        # Check for override
        if snapshot and snapshot.accounts_payable is not None:
            return snapshot.accounts_payable, details

        # Calculate from expenses with status pending or approved (unpaid)
        end_month = self._get_quarter_end_month(quarter)
        if end_month == 12:
            as_of_date = date(year, 12, 31)
        else:
            from datetime import timedelta
            next_month = date(year, end_month + 1, 1)
            as_of_date = next_month - timedelta(days=1)

        queryset = self.ExpenseEntry.objects.filter(
            expense_date__lte=as_of_date,
            status__in=['pending', 'approved']
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        # Get totals by status
        for status in ['pending', 'approved']:
            status_qs = queryset.filter(status=status)
            agg = status_qs.aggregate(total=Sum('amount'))
            count = status_qs.count()
            value = agg['total'] or Decimal('0')

            details[status] = {'count': count, 'value': float(value)}

        total_ap = Decimal(str(details['pending']['value'])) + Decimal(str(details['approved']['value']))
        return total_ap, details

    def _get_accrued_expenses(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get accrued expenses from snapshot (manual entry)."""
        if snapshot:
            return snapshot.accrued_expenses or Decimal('0')
        return Decimal('0')

    def _get_other_current_liabilities(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get other current liabilities from snapshot (manual entry)."""
        if snapshot:
            return snapshot.other_current_liabilities or Decimal('0')
        return Decimal('0')

    def _get_long_term_debt(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get long-term debt from snapshot (manual entry)."""
        if snapshot:
            return snapshot.long_term_debt or Decimal('0')
        return Decimal('0')

    def _get_other_long_term_liabilities(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get other long-term liabilities from snapshot (manual entry)."""
        if snapshot:
            return snapshot.other_long_term_liabilities or Decimal('0')
        return Decimal('0')

    def _get_share_capital(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get share capital from snapshot (manual entry)."""
        if snapshot:
            return snapshot.share_capital or Decimal('0')
        return Decimal('0')

    def _get_additional_paid_in_capital(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get additional paid-in capital from snapshot (manual entry)."""
        if snapshot:
            return snapshot.additional_paid_in_capital or Decimal('0')
        return Decimal('0')

    def _get_retained_earnings(
        self,
        year: int,
        quarter: int,
        billing_entity: str,
        currency: str,
        snapshot: Optional['BalanceSheetSnapshot']
    ) -> Decimal:
        """
        Get retained earnings (cumulative net profit from P&L).
        Uses snapshot override if set, otherwise calculates from P&L service.
        """
        # Check for override
        if snapshot and snapshot.retained_earnings is not None:
            return snapshot.retained_earnings

        # Calculate cumulative net profit from P&L
        try:
            from crm_app.services.profit_loss_service import ProfitLossService
            pl_service = ProfitLossService()

            # Get YTD P&L through end of quarter
            end_month = self._get_quarter_end_month(quarter)
            pl = pl_service.get_ytd_profit_loss(year, end_month, billing_entity, currency)

            return Decimal(str(pl['net_profit']))
        except Exception as e:
            logger.warning(f"Error calculating retained earnings from P&L: {e}")
            return Decimal('0')

    def _get_other_equity(self, snapshot: Optional['BalanceSheetSnapshot']) -> Decimal:
        """Get other equity from snapshot (manual entry)."""
        if snapshot:
            return snapshot.other_equity or Decimal('0')
        return Decimal('0')
