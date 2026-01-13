"""
Profit & Loss Statement Service for BMAsia CRM

Generates P&L statements by combining revenue and expense data.
Part of the Finance & Accounting Module - Phase 4.

P&L Structure:
- Revenue (New + Renewal + Add-ons - Churn)
- Cost of Goods Sold (COGS)
- Gross Profit = Revenue - COGS
- Operating Expenses
  - G&A (General & Administrative)
  - Sales & Marketing
- Operating Income = Gross Profit - Operating Expenses
- Net Profit = Operating Income (simplified, no taxes/interest for now)

Usage:
    from crm_app.services.profit_loss_service import ProfitLossService

    service = ProfitLossService()

    # Get P&L for a month
    pl = service.get_monthly_profit_loss(year=2026, month=1, billing_entity='bmasia_th', currency='THB')

    # Get YTD P&L
    pl_ytd = service.get_ytd_profit_loss(year=2026, month=6, billing_entity='bmasia_th', currency='THB')
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Optional, List
from django.db.models import Sum, Count, Q

logger = logging.getLogger(__name__)


class ProfitLossService:
    """
    Service for generating Profit & Loss statements.
    """

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from crm_app.models import (
            Contract, Invoice, ExpenseEntry, ExpenseCategory,
            MonthlyRevenueSnapshot
        )
        self.Contract = Contract
        self.Invoice = Invoice
        self.ExpenseEntry = ExpenseEntry
        self.ExpenseCategory = ExpenseCategory
        self.MonthlyRevenueSnapshot = MonthlyRevenueSnapshot

    def get_monthly_profit_loss(
        self,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate P&L statement for a single month.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            billing_entity: Filter by billing entity (bmasia_th, bmasia_hk)
            currency: Filter by currency (THB, USD)

        Returns:
            {
                "period": {"year": 2026, "month": 1, "month_name": "January"},
                "billing_entity": "bmasia_th",
                "currency": "THB",
                "revenue": {
                    "new": {"count": 5, "value": 200000},
                    "renewal": {"count": 10, "value": 450000},
                    "addon": {"count": 2, "value": 50000},
                    "churn": {"count": 1, "value": -30000},
                    "total": 670000
                },
                "cogs": {
                    "categories": [...],
                    "total": 180000
                },
                "gross_profit": 490000,
                "gross_margin": 73.1,
                "operating_expenses": {
                    "gna": {"categories": [...], "total": 335000},
                    "sales_marketing": {"categories": [...], "total": 130000},
                    "total": 465000
                },
                "operating_income": 25000,
                "operating_margin": 3.7,
                "net_profit": 25000,
                "net_margin": 3.7
            }
        """
        month_names = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        # Get revenue data
        revenue = self._get_revenue_data(year, month, billing_entity, currency)

        # Get expense data by category type
        cogs = self._get_expense_by_type('opex_cogs', year, month, billing_entity, currency)
        gna = self._get_expense_by_type('opex_gna', year, month, billing_entity, currency)
        sales_marketing = self._get_expense_by_type('opex_sales', year, month, billing_entity, currency)

        # Calculate totals
        total_revenue = float(revenue['total'])
        total_cogs = float(cogs['total'])
        gross_profit = total_revenue - total_cogs

        total_opex = float(gna['total']) + float(sales_marketing['total'])
        operating_income = gross_profit - total_opex
        net_profit = operating_income  # Simplified: no taxes/interest

        # Calculate margins
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        operating_margin = (operating_income / total_revenue * 100) if total_revenue > 0 else 0
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

        return {
            'period': {
                'year': year,
                'month': month,
                'month_name': month_names[month],
                'type': 'monthly'
            },
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'revenue': {
                'new': {'count': revenue['new_count'], 'value': float(revenue['new_value'])},
                'renewal': {'count': revenue['renewal_count'], 'value': float(revenue['renewal_value'])},
                'addon': {'count': revenue['addon_count'], 'value': float(revenue['addon_value'])},
                'churn': {'count': revenue['churn_count'], 'value': float(revenue['churn_value'])},
                'total': total_revenue
            },
            'cogs': {
                'categories': cogs['categories'],
                'total': total_cogs
            },
            'gross_profit': gross_profit,
            'gross_margin': round(gross_margin, 1),
            'operating_expenses': {
                'gna': {
                    'categories': gna['categories'],
                    'total': float(gna['total'])
                },
                'sales_marketing': {
                    'categories': sales_marketing['categories'],
                    'total': float(sales_marketing['total'])
                },
                'total': total_opex
            },
            'operating_income': operating_income,
            'operating_margin': round(operating_margin, 1),
            'net_profit': net_profit,
            'net_margin': round(net_margin, 1)
        }

    def get_ytd_profit_loss(
        self,
        year: int,
        through_month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate Year-to-Date P&L statement.

        Args:
            year: Year (e.g., 2026)
            through_month: Include months 1 through this month
            billing_entity: Filter by billing entity
            currency: Filter by currency

        Returns:
            Same structure as get_monthly_profit_loss but with YTD totals
        """
        # Initialize accumulators
        total_revenue = {
            'new_count': 0, 'new_value': Decimal('0'),
            'renewal_count': 0, 'renewal_value': Decimal('0'),
            'addon_count': 0, 'addon_value': Decimal('0'),
            'churn_count': 0, 'churn_value': Decimal('0'),
            'total': Decimal('0')
        }
        total_cogs = {'categories': {}, 'total': Decimal('0')}
        total_gna = {'categories': {}, 'total': Decimal('0')}
        total_sales = {'categories': {}, 'total': Decimal('0')}

        # Aggregate each month
        for month in range(1, through_month + 1):
            revenue = self._get_revenue_data(year, month, billing_entity, currency)
            cogs = self._get_expense_by_type('opex_cogs', year, month, billing_entity, currency)
            gna = self._get_expense_by_type('opex_gna', year, month, billing_entity, currency)
            sales = self._get_expense_by_type('opex_sales', year, month, billing_entity, currency)

            # Accumulate revenue
            total_revenue['new_count'] += revenue['new_count']
            total_revenue['new_value'] += revenue['new_value']
            total_revenue['renewal_count'] += revenue['renewal_count']
            total_revenue['renewal_value'] += revenue['renewal_value']
            total_revenue['addon_count'] += revenue['addon_count']
            total_revenue['addon_value'] += revenue['addon_value']
            total_revenue['churn_count'] += revenue['churn_count']
            total_revenue['churn_value'] += revenue['churn_value']
            total_revenue['total'] += revenue['total']

            # Accumulate expenses by category
            self._accumulate_expenses(total_cogs, cogs)
            self._accumulate_expenses(total_gna, gna)
            self._accumulate_expenses(total_sales, sales)

        # Calculate totals
        rev_total = float(total_revenue['total'])
        cogs_total = float(total_cogs['total'])
        gross_profit = rev_total - cogs_total

        opex_total = float(total_gna['total']) + float(total_sales['total'])
        operating_income = gross_profit - opex_total
        net_profit = operating_income

        # Calculate margins
        gross_margin = (gross_profit / rev_total * 100) if rev_total > 0 else 0
        operating_margin = (operating_income / rev_total * 100) if rev_total > 0 else 0
        net_margin = (net_profit / rev_total * 100) if rev_total > 0 else 0

        return {
            'period': {
                'year': year,
                'through_month': through_month,
                'type': 'ytd'
            },
            'billing_entity': billing_entity or 'all',
            'currency': currency or 'all',
            'revenue': {
                'new': {'count': total_revenue['new_count'], 'value': float(total_revenue['new_value'])},
                'renewal': {'count': total_revenue['renewal_count'], 'value': float(total_revenue['renewal_value'])},
                'addon': {'count': total_revenue['addon_count'], 'value': float(total_revenue['addon_value'])},
                'churn': {'count': total_revenue['churn_count'], 'value': float(total_revenue['churn_value'])},
                'total': rev_total
            },
            'cogs': {
                'categories': self._format_accumulated_categories(total_cogs['categories']),
                'total': cogs_total
            },
            'gross_profit': gross_profit,
            'gross_margin': round(gross_margin, 1),
            'operating_expenses': {
                'gna': {
                    'categories': self._format_accumulated_categories(total_gna['categories']),
                    'total': float(total_gna['total'])
                },
                'sales_marketing': {
                    'categories': self._format_accumulated_categories(total_sales['categories']),
                    'total': float(total_sales['total'])
                },
                'total': opex_total
            },
            'operating_income': operating_income,
            'operating_margin': round(operating_margin, 1),
            'net_profit': net_profit,
            'net_margin': round(net_margin, 1)
        }

    def get_comparative_profit_loss(
        self,
        year: int,
        month: int,
        compare_year: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Generate P&L comparison between two periods (YoY).

        Returns current period, prior period, and variance.
        """
        current = self.get_monthly_profit_loss(year, month, billing_entity, currency)
        prior = self.get_monthly_profit_loss(compare_year, month, billing_entity, currency)

        def calc_variance(current_val, prior_val):
            diff = current_val - prior_val
            pct = ((diff / prior_val) * 100) if prior_val != 0 else 0
            return {'amount': diff, 'percentage': round(pct, 1)}

        return {
            'current': current,
            'prior': prior,
            'variance': {
                'revenue': calc_variance(current['revenue']['total'], prior['revenue']['total']),
                'cogs': calc_variance(current['cogs']['total'], prior['cogs']['total']),
                'gross_profit': calc_variance(current['gross_profit'], prior['gross_profit']),
                'operating_expenses': calc_variance(
                    current['operating_expenses']['total'],
                    prior['operating_expenses']['total']
                ),
                'net_profit': calc_variance(current['net_profit'], prior['net_profit'])
            }
        }

    def get_monthly_trend(
        self,
        year: int,
        billing_entity: str = None,
        currency: str = None
    ) -> List[Dict]:
        """
        Get monthly P&L trend for a full year.

        Returns list of monthly summaries for trend charts.
        """
        trends = []
        current_month = date.today().month if date.today().year == year else 12

        for month in range(1, current_month + 1):
            pl = self.get_monthly_profit_loss(year, month, billing_entity, currency)
            trends.append({
                'month': month,
                'month_name': pl['period']['month_name'],
                'revenue': pl['revenue']['total'],
                'cogs': pl['cogs']['total'],
                'gross_profit': pl['gross_profit'],
                'operating_expenses': pl['operating_expenses']['total'],
                'net_profit': pl['net_profit'],
                'gross_margin': pl['gross_margin'],
                'net_margin': pl['net_margin']
            })

        return trends

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _get_revenue_data(
        self,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Get revenue data for a month.
        First tries MonthlyRevenueSnapshot, then calculates from contracts.
        """
        # Try to get from snapshots first
        snapshots = self.MonthlyRevenueSnapshot.objects.filter(
            year=year,
            month=month
        )

        if billing_entity:
            snapshots = snapshots.filter(billing_entity=billing_entity)
        if currency:
            snapshots = snapshots.filter(currency=currency)

        if snapshots.exists():
            return self._aggregate_snapshots(snapshots)

        # Fall back to calculating from contracts
        return self._calculate_revenue_from_contracts(year, month, billing_entity, currency)

    def _aggregate_snapshots(self, snapshots) -> Dict:
        """Aggregate revenue from snapshot records."""
        result = {
            'new_count': 0, 'new_value': Decimal('0'),
            'renewal_count': 0, 'renewal_value': Decimal('0'),
            'addon_count': 0, 'addon_value': Decimal('0'),
            'churn_count': 0, 'churn_value': Decimal('0'),
            'total': Decimal('0')
        }

        for snapshot in snapshots:
            if snapshot.category == 'new':
                result['new_count'] += snapshot.contract_count
                result['new_value'] += snapshot.contracted_value
            elif snapshot.category == 'renewal':
                result['renewal_count'] += snapshot.contract_count
                result['renewal_value'] += snapshot.contracted_value
            elif snapshot.category == 'addon':
                result['addon_count'] += snapshot.contract_count
                result['addon_value'] += snapshot.contracted_value
            elif snapshot.category == 'churn':
                result['churn_count'] += snapshot.contract_count
                result['churn_value'] += snapshot.contracted_value

        result['total'] = (
            result['new_value'] + result['renewal_value'] +
            result['addon_value'] + result['churn_value']  # churn is already negative
        )

        return result

    def _calculate_revenue_from_contracts(
        self,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """Calculate revenue directly from contracts when no snapshots exist."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        base_query = self.Contract.objects.filter(
            lifecycle_effective_date__gte=month_start,
            lifecycle_effective_date__lte=month_end
        )

        if billing_entity:
            base_query = base_query.filter(company__billing_entity=billing_entity)
        if currency:
            base_query = base_query.filter(currency=currency)

        result = {
            'new_count': 0, 'new_value': Decimal('0'),
            'renewal_count': 0, 'renewal_value': Decimal('0'),
            'addon_count': 0, 'addon_value': Decimal('0'),
            'churn_count': 0, 'churn_value': Decimal('0'),
            'total': Decimal('0')
        }

        for lifecycle_type in ['new', 'renewal', 'addon', 'churn']:
            contracts = base_query.filter(lifecycle_type=lifecycle_type)
            agg = contracts.aggregate(
                count=Count('id'),
                value=Sum('value')
            )
            count = agg['count'] or 0
            value = agg['value'] or Decimal('0')

            if lifecycle_type == 'churn':
                value = -abs(value)

            result[f'{lifecycle_type}_count'] = count
            result[f'{lifecycle_type}_value'] = value

        result['total'] = (
            result['new_value'] + result['renewal_value'] +
            result['addon_value'] + result['churn_value']
        )

        return result

    def _get_expense_by_type(
        self,
        category_type: str,
        year: int,
        month: int,
        billing_entity: str = None,
        currency: str = None
    ) -> Dict:
        """
        Get expense totals for a category type (opex_cogs, opex_gna, opex_sales).

        Returns breakdown by individual category within the type.
        """
        queryset = self.ExpenseEntry.objects.filter(
            expense_date__year=year,
            expense_date__month=month,
            category__category_type=category_type,
            status__in=['approved', 'paid']  # Only count approved/paid expenses
        )

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)
        if currency:
            queryset = queryset.filter(currency=currency)

        # Group by category
        categories = []
        category_totals = queryset.values(
            'category__id',
            'category__name',
            'category__full_path'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('category__name')

        total = Decimal('0')
        for cat in category_totals:
            cat_total = cat['total'] or Decimal('0')
            categories.append({
                'category_id': str(cat['category__id']),
                'category_name': cat['category__name'],
                'full_path': cat['category__full_path'],
                'amount': float(cat_total),
                'count': cat['count']
            })
            total += cat_total

        return {
            'categories': categories,
            'total': total
        }

    def _accumulate_expenses(self, accumulator: Dict, monthly: Dict):
        """Accumulate monthly expense data into YTD totals."""
        accumulator['total'] += Decimal(str(monthly['total']))

        for cat in monthly['categories']:
            cat_id = cat['category_id']
            if cat_id not in accumulator['categories']:
                accumulator['categories'][cat_id] = {
                    'category_id': cat_id,
                    'category_name': cat['category_name'],
                    'full_path': cat.get('full_path', cat['category_name']),
                    'amount': Decimal('0'),
                    'count': 0
                }
            accumulator['categories'][cat_id]['amount'] += Decimal(str(cat['amount']))
            accumulator['categories'][cat_id]['count'] += cat['count']

    def _format_accumulated_categories(self, categories_dict: Dict) -> List[Dict]:
        """Convert accumulated categories dict to list format."""
        return [
            {
                'category_id': cat['category_id'],
                'category_name': cat['category_name'],
                'full_path': cat['full_path'],
                'amount': float(cat['amount']),
                'count': cat['count']
            }
            for cat in sorted(categories_dict.values(), key=lambda x: x['category_name'])
        ]
