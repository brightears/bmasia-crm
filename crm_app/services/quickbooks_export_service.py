"""
QuickBooks IIF Export Service for BMAsia CRM

Generates IIF (Intuit Interchange Format) files for importing invoices
into QuickBooks Pro 2016 (Desktop).

IIF is a tab-delimited text format with this structure per invoice:
  !TRNS header row (column definitions)
  TRNS row (invoice header: AR account, customer, total amount)
  !SPL header row (column definitions)
  SPL rows (one per line item: income account, negative amount)
  ENDTRNS terminator

Usage:
    from crm_app.services.quickbooks_export_service import QuickBooksExportService

    service = QuickBooksExportService()
    iif_content = service.generate_iif(invoices, ar_account='Accounts Receivable',
                                        income_account='Service Revenue')
"""

import logging
import re
from io import StringIO
from decimal import Decimal

logger = logging.getLogger(__name__)

# Map CRM product_service values to QuickBooks item names
PRODUCT_SERVICE_TO_QB_ITEM = {
    'soundtrack': 'Soundtrack Music Service',
    'beatbreeze': 'Beat Breeze Music Service',
    'hardware': 'Hardware',
    'installation': 'Installation Service',
    'support': 'Support Service',
}


class QuickBooksExportService:
    """Generates IIF files for QuickBooks Pro 2016 invoice import."""

    # IIF column definitions
    TRNS_HEADERS = [
        'TRNSID', 'TRNSTYPE', 'DATE', 'ACCNT', 'NAME',
        'AMOUNT', 'DOCNUM', 'MEMO', 'DUEDATE',
    ]
    SPL_HEADERS = [
        'SPLID', 'TRNSTYPE', 'DATE', 'ACCNT', 'NAME',
        'AMOUNT', 'QNTY', 'PRICE', 'INVITEM', 'MEMO',
    ]

    def generate_iif(self, invoices, ar_account='Accounts Receivable',
                     income_account='Service Revenue'):
        """
        Generate IIF content for a queryset of Invoice objects.

        Args:
            invoices: QuerySet of Invoice objects (with prefetched line_items and company)
            ar_account: QuickBooks AR account name (must match QB exactly)
            income_account: QuickBooks income account name (must match QB exactly)

        Returns:
            StringIO buffer containing IIF content
        """
        output = StringIO()

        # Write TRNS header row
        output.write('!TRNS\t' + '\t'.join(self.TRNS_HEADERS) + '\n')
        # Write SPL header row
        output.write('!SPL\t' + '\t'.join(self.SPL_HEADERS) + '\n')
        # End of header section
        output.write('!ENDTRNS\n')

        invoice_count = 0
        for invoice in invoices:
            try:
                self._write_invoice(output, invoice, ar_account, income_account)
                invoice_count += 1
            except Exception as e:
                logger.error(f'Failed to export invoice {invoice.invoice_number}: {e}')
                continue

        logger.info(f'QuickBooks IIF export: {invoice_count} invoices exported')
        output.seek(0)
        return output

    def _write_invoice(self, output, invoice, ar_account, income_account):
        """Write a single invoice as TRNS + SPL rows + ENDTRNS."""
        company_name = self._sanitize_text(invoice.company.name)
        invoice_date = self._format_date(invoice.issue_date)
        due_date = self._format_date(invoice.due_date) if invoice.due_date else ''
        invoice_number = self._sanitize_text(invoice.invoice_number)
        memo = self._sanitize_text(invoice.notes or '')

        # Total amount (positive for TRNS = debit to AR)
        total_amount = self._format_amount(invoice.total_amount)

        # TRNS row (invoice header)
        trns_values = [
            invoice_number,         # TRNSID
            'INVOICE',              # TRNSTYPE
            invoice_date,           # DATE
            ar_account,             # ACCNT (Accounts Receivable)
            company_name,           # NAME (customer)
            total_amount,           # AMOUNT (positive = debit AR)
            invoice_number,         # DOCNUM
            memo,                   # MEMO
            due_date,               # DUEDATE
        ]
        output.write('TRNS\t' + '\t'.join(trns_values) + '\n')

        # SPL rows (one per line item — amounts are NEGATIVE = credit income)
        line_items = invoice.line_items.all()
        if line_items.exists():
            for idx, item in enumerate(line_items, start=1):
                self._write_line_item(
                    output, idx, item, invoice_date,
                    income_account, company_name
                )
        else:
            # Invoice has no line items — create a single SPL row for the total
            spl_values = [
                '1',                                    # SPLID
                'INVOICE',                              # TRNSTYPE
                invoice_date,                           # DATE
                income_account,                         # ACCNT
                company_name,                           # NAME
                self._format_amount(-invoice.total_amount),  # AMOUNT (negative)
                '1',                                    # QNTY
                total_amount,                           # PRICE
                'Service',                              # INVITEM
                memo,                                   # MEMO
            ]
            output.write('SPL\t' + '\t'.join(spl_values) + '\n')

        output.write('ENDTRNS\n')

    def _write_line_item(self, output, idx, item, invoice_date,
                         income_account, company_name):
        """Write a single SPL row for an invoice line item."""
        description = self._sanitize_text(item.description or '')
        quantity = self._format_amount(item.quantity)
        unit_price = self._format_amount(item.unit_price)
        line_total = self._format_amount(-item.line_total)  # Negative for SPL
        item_name = self._get_item_name(item.product_service)

        spl_values = [
            str(idx),               # SPLID
            'INVOICE',              # TRNSTYPE
            invoice_date,           # DATE
            income_account,         # ACCNT
            company_name,           # NAME
            line_total,             # AMOUNT (negative = credit income)
            quantity,               # QNTY
            unit_price,             # PRICE
            item_name,              # INVITEM
            description,            # MEMO
        ]
        output.write('SPL\t' + '\t'.join(spl_values) + '\n')

    def _format_date(self, date_obj):
        """Format date as MM/DD/YYYY for QuickBooks."""
        if not date_obj:
            return ''
        return date_obj.strftime('%m/%d/%Y')

    def _format_amount(self, amount):
        """Format decimal amount to 2 decimal places."""
        if amount is None:
            return '0.00'
        if isinstance(amount, str):
            amount = Decimal(amount)
        return f'{float(amount):.2f}'

    def _sanitize_text(self, text):
        """
        Sanitize text for IIF format.
        - Strip semicolons (QB stops reading at semicolon)
        - Replace newlines with spaces
        - Replace non-ASCII chars with ? (QB Pro 2016 can't handle high-ASCII)
        - Truncate to 255 characters
        """
        if not text:
            return ''
        text = str(text)
        # Replace semicolons with commas
        text = text.replace(';', ',')
        # Replace newlines and tabs with spaces
        text = re.sub(r'[\r\n\t]+', ' ', text)
        # Replace non-ASCII characters with ?
        text = ''.join(c if ord(c) < 128 else '?' for c in text)
        # Strip extra whitespace
        text = ' '.join(text.split())
        # Truncate
        return text[:255]

    def _get_item_name(self, product_service):
        """Map CRM product_service to QuickBooks item name."""
        if not product_service:
            return 'Service'

        # Check exact match first
        ps_lower = product_service.lower().strip()
        if ps_lower in PRODUCT_SERVICE_TO_QB_ITEM:
            return PRODUCT_SERVICE_TO_QB_ITEM[ps_lower]

        # Check partial match (e.g., "Soundtrack Your Brand" contains "soundtrack")
        for key, qb_name in PRODUCT_SERVICE_TO_QB_ITEM.items():
            if key in ps_lower.replace(' ', ''):
                return qb_name

        # Use the product_service value itself (sanitized)
        return self._sanitize_text(product_service)
