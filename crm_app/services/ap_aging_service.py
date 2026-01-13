"""
Accounts Payable Aging Service for BMAsia CRM

Calculates AP aging buckets from unpaid expense entries.
Part of the Finance & Accounting Module - Phase 3.

Aging Buckets:
- Current: Not yet due (due_date >= today)
- 1-30 days: 1-30 days past due
- 31-60 days: 31-60 days past due
- 61-90 days: 61-90 days past due
- 90+ days: Over 90 days past due

Usage:
    from crm_app.services.ap_aging_service import APAgingService

    service = APAgingService()

    # Get full AP aging report
    report = service.get_ap_aging_report(as_of_date=date.today())

    # Get summary totals by bucket
    summary = service.get_ap_summary()
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


class APAgingService:
    """
    Service for Accounts Payable aging calculations.
    """

    # Aging bucket definitions (days past due)
    AGING_BUCKETS = [
        ('current', 'Current', 0, 0),      # Not yet due
        ('1_30', '1-30 Days', 1, 30),
        ('31_60', '31-60 Days', 31, 60),
        ('61_90', '61-90 Days', 61, 90),
        ('90_plus', '90+ Days', 91, 9999),
    ]

    def __init__(self):
        # Lazy imports to avoid circular dependencies
        from crm_app.models import ExpenseEntry, ExpenseCategory, Vendor
        self.ExpenseEntry = ExpenseEntry
        self.ExpenseCategory = ExpenseCategory
        self.Vendor = Vendor

    def get_outstanding_expenses(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ):
        """
        Get all outstanding (unpaid) expense entries.

        Args:
            as_of_date: Date to calculate aging from (default: today)
            currency: Filter by currency (USD, THB)
            billing_entity: Filter by billing entity (bmasia_th, bmasia_hk)

        Returns:
            QuerySet of ExpenseEntry objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Outstanding = pending, approved (not paid, draft, cancelled)
        queryset = self.ExpenseEntry.objects.filter(
            status__in=['pending', 'approved']
        ).select_related(
            'category',
            'vendor'
        )

        if currency:
            queryset = queryset.filter(currency=currency)

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)

        return queryset.order_by('vendor__name', 'due_date')

    def calculate_aging_bucket(self, due_date: date, as_of_date: date = None) -> str:
        """
        Determine which aging bucket an expense belongs to.

        Args:
            due_date: Expense due date
            as_of_date: Date to calculate from (default: today)

        Returns:
            Bucket key: 'current', '1_30', '31_60', '61_90', or '90_plus'
        """
        if as_of_date is None:
            as_of_date = date.today()

        # If no due date, treat as current
        if due_date is None:
            return 'current'

        if due_date >= as_of_date:
            return 'current'

        days_overdue = (as_of_date - due_date).days

        if days_overdue <= 30:
            return '1_30'
        elif days_overdue <= 60:
            return '31_60'
        elif days_overdue <= 90:
            return '61_90'
        else:
            return '90_plus'

    def get_ap_aging_report(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ) -> Dict:
        """
        Generate full AP aging report with expense details.

        Returns:
        {
            "as_of_date": "2026-01-13",
            "currency": "THB",
            "billing_entity": "bmasia_th",
            "summary": {
                "total_ap": 120000.00,
                "current": 85000.00,
                "1_30": 25000.00,
                "31_60": 10000.00,
                "61_90": 0,
                "90_plus": 0,
                "expense_count": 15
            },
            "by_vendor": [
                {
                    "vendor_id": "uuid",
                    "vendor_name": "Soundtrack Your Brand",
                    "total": 50000.00,
                    "current": 50000.00,
                    "1_30": 0,
                    ...
                    "expenses": [...]
                },
                ...
            ],
            "by_category": [
                {
                    "category_id": "uuid",
                    "category_name": "COGS > Soundtrack Licenses",
                    "total": 50000.00,
                    ...
                },
                ...
            ],
            "expenses": [
                {
                    "expense_id": "uuid",
                    "description": "January Soundtrack License",
                    "vendor_name": "Soundtrack Your Brand",
                    "category_name": "COGS > Soundtrack Licenses",
                    "expense_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "amount": 50000.00,
                    "days_overdue": 0,
                    "aging_bucket": "current"
                },
                ...
            ]
        }
        """
        if as_of_date is None:
            as_of_date = date.today()

        expenses = self.get_outstanding_expenses(
            as_of_date=as_of_date,
            currency=currency,
            billing_entity=billing_entity
        )

        # Initialize summary
        summary = {
            'total_ap': Decimal('0'),
            'current': Decimal('0'),
            '1_30': Decimal('0'),
            '31_60': Decimal('0'),
            '61_90': Decimal('0'),
            '90_plus': Decimal('0'),
            'expense_count': 0
        }

        # Group by vendor
        by_vendor = {}
        # Group by category
        by_category = {}
        expense_list = []

        for expense in expenses:
            bucket = self.calculate_aging_bucket(expense.due_date, as_of_date)
            days_overdue = max(0, (as_of_date - expense.due_date).days) if expense.due_date else 0

            # Update summary
            summary['total_ap'] += expense.amount
            summary[bucket] += expense.amount
            summary['expense_count'] += 1

            # Vendor grouping
            vendor_id = str(expense.vendor.id) if expense.vendor else 'no_vendor'
            vendor_name = expense.vendor.name if expense.vendor else 'No Vendor'

            if vendor_id not in by_vendor:
                by_vendor[vendor_id] = {
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'total': Decimal('0'),
                    'current': Decimal('0'),
                    '1_30': Decimal('0'),
                    '31_60': Decimal('0'),
                    '61_90': Decimal('0'),
                    '90_plus': Decimal('0'),
                    'expenses': []
                }

            by_vendor[vendor_id]['total'] += expense.amount
            by_vendor[vendor_id][bucket] += expense.amount

            # Category grouping
            category_id = str(expense.category.id)
            category_name = expense.category.full_path

            if category_id not in by_category:
                by_category[category_id] = {
                    'category_id': category_id,
                    'category_name': category_name,
                    'category_type': expense.category.category_type,
                    'total': Decimal('0'),
                    'current': Decimal('0'),
                    '1_30': Decimal('0'),
                    '31_60': Decimal('0'),
                    '61_90': Decimal('0'),
                    '90_plus': Decimal('0'),
                }

            by_category[category_id]['total'] += expense.amount
            by_category[category_id][bucket] += expense.amount

            # Expense detail
            expense_detail = {
                'expense_id': str(expense.id),
                'description': expense.description,
                'vendor_id': vendor_id,
                'vendor_name': vendor_name,
                'category_id': category_id,
                'category_name': category_name,
                'expense_date': expense.expense_date.isoformat(),
                'due_date': expense.due_date.isoformat() if expense.due_date else None,
                'amount': float(expense.amount),
                'currency': expense.currency,
                'days_overdue': days_overdue,
                'aging_bucket': bucket,
                'status': expense.status,
                'vendor_invoice_number': expense.vendor_invoice_number
            }

            by_vendor[vendor_id]['expenses'].append(expense_detail)
            expense_list.append(expense_detail)

        # Convert vendor dict to sorted list
        vendor_list = sorted(
            by_vendor.values(),
            key=lambda x: x['total'],
            reverse=True
        )

        # Convert category dict to sorted list
        category_list = sorted(
            by_category.values(),
            key=lambda x: x['total'],
            reverse=True
        )

        # Convert Decimals to floats for JSON serialization
        for key in ['total_ap', 'current', '1_30', '31_60', '61_90', '90_plus']:
            summary[key] = float(summary[key])

        for vendor in vendor_list:
            for key in ['total', 'current', '1_30', '31_60', '61_90', '90_plus']:
                vendor[key] = float(vendor[key])

        for category in category_list:
            for key in ['total', 'current', '1_30', '31_60', '61_90', '90_plus']:
                category[key] = float(category[key])

        return {
            'as_of_date': as_of_date.isoformat(),
            'currency': currency or 'all',
            'billing_entity': billing_entity or 'all',
            'summary': summary,
            'by_vendor': vendor_list,
            'by_category': category_list,
            'expenses': expense_list
        }

    def get_ap_summary(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ) -> Dict:
        """
        Get just the summary totals (no expense details).
        Faster for dashboard KPI cards.
        """
        report = self.get_ap_aging_report(
            as_of_date=as_of_date,
            currency=currency,
            billing_entity=billing_entity
        )
        return report['summary']

    def get_overdue_expenses(
        self,
        min_days_overdue: int = 1,
        currency: str = None,
        billing_entity: str = None
    ) -> List[Dict]:
        """
        Get expenses that are overdue by at least min_days_overdue days.
        Useful for generating payment lists or alerts.
        """
        as_of_date = date.today()
        cutoff_date = as_of_date - timedelta(days=min_days_overdue)

        expenses = self.ExpenseEntry.objects.filter(
            status__in=['pending', 'approved'],
            due_date__lt=cutoff_date
        ).select_related(
            'category',
            'vendor'
        )

        if currency:
            expenses = expenses.filter(currency=currency)

        if billing_entity:
            expenses = expenses.filter(billing_entity=billing_entity)

        result = []
        for expense in expenses.order_by('-due_date'):
            days_overdue = (as_of_date - expense.due_date).days if expense.due_date else 0
            result.append({
                'expense_id': str(expense.id),
                'description': expense.description,
                'vendor_name': expense.vendor.name if expense.vendor else 'No Vendor',
                'vendor_id': str(expense.vendor.id) if expense.vendor else None,
                'category_name': expense.category.full_path,
                'due_date': expense.due_date.isoformat() if expense.due_date else None,
                'amount': float(expense.amount),
                'currency': expense.currency,
                'days_overdue': days_overdue,
                'aging_bucket': self.calculate_aging_bucket(expense.due_date, as_of_date),
                'vendor_invoice_number': expense.vendor_invoice_number
            })

        return result

    def get_payment_priority_list(
        self,
        currency: str = None,
        billing_entity: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get prioritized list of expenses for payment.
        Sorted by: amount * days_overdue (highest priority first)
        """
        overdue = self.get_overdue_expenses(
            min_days_overdue=1,
            currency=currency,
            billing_entity=billing_entity
        )

        # Calculate priority score
        for exp in overdue:
            exp['priority_score'] = exp['amount'] * exp['days_overdue']

        # Sort by priority score descending
        sorted_list = sorted(overdue, key=lambda x: x['priority_score'], reverse=True)

        return sorted_list[:limit]

    def get_monthly_expense_summary(
        self,
        year: int,
        month: int = None,
        currency: str = None,
        billing_entity: str = None
    ) -> Dict:
        """
        Get expense summary by category for a specific month/year.
        Used for P&L statement generation.
        """
        queryset = self.ExpenseEntry.objects.filter(
            expense_date__year=year,
            status__in=['approved', 'paid']  # Only count approved/paid expenses
        )

        if month:
            queryset = queryset.filter(expense_date__month=month)

        if currency:
            queryset = queryset.filter(currency=currency)

        if billing_entity:
            queryset = queryset.filter(billing_entity=billing_entity)

        # Aggregate by category type
        by_type = {}
        for exp in queryset.select_related('category'):
            cat_type = exp.category.category_type
            if cat_type not in by_type:
                by_type[cat_type] = {
                    'category_type': cat_type,
                    'total': Decimal('0'),
                    'count': 0,
                    'categories': {}
                }

            by_type[cat_type]['total'] += exp.amount
            by_type[cat_type]['count'] += 1

            # By individual category
            cat_id = str(exp.category.id)
            if cat_id not in by_type[cat_type]['categories']:
                by_type[cat_type]['categories'][cat_id] = {
                    'category_id': cat_id,
                    'category_name': exp.category.name,
                    'total': Decimal('0'),
                    'count': 0
                }

            by_type[cat_type]['categories'][cat_id]['total'] += exp.amount
            by_type[cat_type]['categories'][cat_id]['count'] += 1

        # Convert to float
        for cat_type in by_type.values():
            cat_type['total'] = float(cat_type['total'])
            cat_type['categories'] = list(cat_type['categories'].values())
            for cat in cat_type['categories']:
                cat['total'] = float(cat['total'])

        return {
            'year': year,
            'month': month,
            'currency': currency or 'all',
            'billing_entity': billing_entity or 'all',
            'by_category_type': list(by_type.values()),
            'totals': {
                'cogs': float(by_type.get('opex_cogs', {}).get('total', 0)),
                'gna': float(by_type.get('opex_gna', {}).get('total', 0)),
                'sales_marketing': float(by_type.get('opex_sales', {}).get('total', 0)),
                'capex': float(by_type.get('capex', {}).get('total', 0)),
            }
        }
