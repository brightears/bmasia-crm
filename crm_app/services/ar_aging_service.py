"""
Accounts Receivable Aging Service for BMAsia CRM

Calculates AR aging buckets from unpaid invoices.
Part of the Finance & Accounting Module - Phase 2.

Aging Buckets:
- Current: Not yet due (due_date >= today)
- 1-30 days: 1-30 days past due
- 31-60 days: 31-60 days past due
- 61-90 days: 61-90 days past due
- 90+ days: Over 90 days past due

Usage:
    from crm_app.services.ar_aging_service import ARAgingService

    service = ARAgingService()

    # Get full AR aging report
    report = service.get_ar_aging_report(as_of_date=date.today())

    # Get summary totals by bucket
    summary = service.get_ar_summary()
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)


class ARAgingService:
    """
    Service for Accounts Receivable aging calculations.
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
        from crm_app.models import Invoice, Contract, Company
        self.Invoice = Invoice
        self.Contract = Contract
        self.Company = Company

    def get_outstanding_invoices(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ):
        """
        Get all outstanding (unpaid) invoices.

        Args:
            as_of_date: Date to calculate aging from (default: today)
            currency: Filter by currency (USD, THB)
            billing_entity: Filter by billing entity (bmasia_th, bmasia_hk)

        Returns:
            QuerySet of Invoice objects
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Outstanding = Sent or Overdue (not Paid, Draft, Cancelled, Refunded)
        queryset = self.Invoice.objects.filter(
            status__in=['Sent', 'Overdue']
        ).select_related(
            'contract',
            'contract__company'
        )

        if currency:
            queryset = queryset.filter(currency=currency)

        if billing_entity:
            queryset = queryset.filter(contract__company__billing_entity=billing_entity)

        return queryset.order_by('contract__company__name', 'due_date')

    def calculate_aging_bucket(self, due_date: date, as_of_date: date = None) -> str:
        """
        Determine which aging bucket an invoice belongs to.

        Args:
            due_date: Invoice due date
            as_of_date: Date to calculate from (default: today)

        Returns:
            Bucket key: 'current', '1_30', '31_60', '61_90', or '90_plus'
        """
        if as_of_date is None:
            as_of_date = date.today()

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

    def get_ar_aging_report(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ) -> Dict:
        """
        Generate full AR aging report with invoice details.

        Returns:
        {
            "as_of_date": "2026-01-13",
            "currency": "USD",
            "billing_entity": "bmasia_th",
            "summary": {
                "total_ar": 450000.00,
                "current": 280000.00,
                "1_30": 95000.00,
                "31_60": 50000.00,
                "61_90": 15000.00,
                "90_plus": 10000.00,
                "invoice_count": 25
            },
            "by_company": [
                {
                    "company_id": "uuid",
                    "company_name": "Hilton Pattaya",
                    "total": 50000.00,
                    "current": 30000.00,
                    "1_30": 20000.00,
                    "31_60": 0,
                    "61_90": 0,
                    "90_plus": 0,
                    "invoices": [...]
                },
                ...
            ],
            "invoices": [
                {
                    "invoice_id": "uuid",
                    "invoice_number": "INV-2026-001",
                    "company_name": "Hilton Pattaya",
                    "issue_date": "2025-12-01",
                    "due_date": "2025-12-31",
                    "amount": 50000.00,
                    "days_overdue": 13,
                    "aging_bucket": "1_30"
                },
                ...
            ]
        }
        """
        if as_of_date is None:
            as_of_date = date.today()

        invoices = self.get_outstanding_invoices(
            as_of_date=as_of_date,
            currency=currency,
            billing_entity=billing_entity
        )

        # Initialize summary
        summary = {
            'total_ar': Decimal('0'),
            'current': Decimal('0'),
            '1_30': Decimal('0'),
            '31_60': Decimal('0'),
            '61_90': Decimal('0'),
            '90_plus': Decimal('0'),
            'invoice_count': 0
        }

        # Group by company
        by_company = {}
        invoice_list = []

        for invoice in invoices:
            bucket = self.calculate_aging_bucket(invoice.due_date, as_of_date)
            days_overdue = max(0, (as_of_date - invoice.due_date).days)
            company = invoice.company

            # Update summary
            summary['total_ar'] += invoice.total_amount
            summary[bucket] += invoice.total_amount
            summary['invoice_count'] += 1

            # Update company grouping
            company_id = str(company.id)
            if company_id not in by_company:
                by_company[company_id] = {
                    'company_id': company_id,
                    'company_name': company.name,
                    'total': Decimal('0'),
                    'current': Decimal('0'),
                    '1_30': Decimal('0'),
                    '31_60': Decimal('0'),
                    '61_90': Decimal('0'),
                    '90_plus': Decimal('0'),
                    'invoices': []
                }

            by_company[company_id]['total'] += invoice.total_amount
            by_company[company_id][bucket] += invoice.total_amount

            # Invoice detail
            invoice_detail = {
                'invoice_id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'company_id': company_id,
                'company_name': company.name,
                'issue_date': invoice.issue_date.isoformat(),
                'due_date': invoice.due_date.isoformat(),
                'amount': float(invoice.total_amount),
                'currency': invoice.currency,
                'days_overdue': days_overdue,
                'aging_bucket': bucket,
                'status': invoice.status
            }

            by_company[company_id]['invoices'].append(invoice_detail)
            invoice_list.append(invoice_detail)

        # Convert company dict to sorted list
        company_list = sorted(
            by_company.values(),
            key=lambda x: x['total'],
            reverse=True
        )

        # Convert Decimals to floats for JSON serialization
        for key in ['total_ar', 'current', '1_30', '31_60', '61_90', '90_plus']:
            summary[key] = float(summary[key])

        for company in company_list:
            for key in ['total', 'current', '1_30', '31_60', '61_90', '90_plus']:
                company[key] = float(company[key])

        return {
            'as_of_date': as_of_date.isoformat(),
            'currency': currency or 'all',
            'billing_entity': billing_entity or 'all',
            'summary': summary,
            'by_company': company_list,
            'invoices': invoice_list
        }

    def get_ar_summary(
        self,
        as_of_date: date = None,
        currency: str = None,
        billing_entity: str = None
    ) -> Dict:
        """
        Get just the summary totals (no invoice details).
        Faster for dashboard KPI cards.
        """
        report = self.get_ar_aging_report(
            as_of_date=as_of_date,
            currency=currency,
            billing_entity=billing_entity
        )
        return report['summary']

    def get_overdue_invoices(
        self,
        min_days_overdue: int = 1,
        currency: str = None,
        billing_entity: str = None
    ) -> List[Dict]:
        """
        Get invoices that are overdue by at least min_days_overdue days.
        Useful for generating collection lists or alerts.
        """
        as_of_date = date.today()
        cutoff_date = as_of_date - timedelta(days=min_days_overdue)

        invoices = self.Invoice.objects.filter(
            status__in=['Sent', 'Overdue'],
            due_date__lt=cutoff_date
        ).select_related(
            'contract',
            'contract__company'
        )

        if currency:
            invoices = invoices.filter(currency=currency)

        if billing_entity:
            invoices = invoices.filter(contract__company__billing_entity=billing_entity)

        result = []
        for invoice in invoices.order_by('-due_date'):
            days_overdue = (as_of_date - invoice.due_date).days
            result.append({
                'invoice_id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'company_name': invoice.company.name,
                'company_id': str(invoice.company.id),
                'due_date': invoice.due_date.isoformat(),
                'amount': float(invoice.total_amount),
                'currency': invoice.currency,
                'days_overdue': days_overdue,
                'aging_bucket': self.calculate_aging_bucket(invoice.due_date, as_of_date),
                'contact_email': invoice.company.email or '',
                'contact_phone': invoice.company.phone or ''
            })

        return result

    def get_collection_priority_list(
        self,
        currency: str = None,
        billing_entity: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get prioritized list of invoices for collection efforts.
        Sorted by: amount * days_overdue (highest priority first)
        """
        overdue = self.get_overdue_invoices(
            min_days_overdue=1,
            currency=currency,
            billing_entity=billing_entity
        )

        # Calculate priority score
        for inv in overdue:
            inv['priority_score'] = inv['amount'] * inv['days_overdue']

        # Sort by priority score descending
        sorted_list = sorted(overdue, key=lambda x: x['priority_score'], reverse=True)

        return sorted_list[:limit]
