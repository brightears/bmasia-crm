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
    iif_content = service.generate_iif(
        invoices,
        ar_accounts={'THB': 'Local AR', 'USD': 'Overseas AR'},
        income_accounts={'syb': 'SYB Revenue', 'bms': 'BMS Revenue', 'default': 'Service Revenue'},
        tax_account='VAT Payable',
    )
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

    def generate_iif(self, invoices, ar_accounts=None, income_accounts=None,
                     tax_account='VAT Payable'):
        """
        Generate IIF content for a queryset of Invoice objects.

        Args:
            invoices: QuerySet of Invoice objects (with prefetched line_items and company)
            ar_accounts: Dict mapping currency code to QB AR account name
                         e.g. {'THB': '1005 LOCAL AR', 'USD': '1005.1 OVERSEAS AR'}
            income_accounts: Dict mapping product key to QB income account name
                             e.g. {'syb': '4006.1 SYB', 'bms': '4006.2 BMS', 'default': '...'}
            tax_account: QuickBooks VAT/tax payable account name (must match QB exactly)

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
                self._write_invoice(output, invoice, ar_accounts, income_accounts, tax_account)
                invoice_count += 1
            except Exception as e:
                logger.error(f'Failed to export invoice {invoice.invoice_number}: {e}')
                continue

        logger.info(f'QuickBooks IIF export: {invoice_count} invoices exported')
        output.seek(0)
        return output

    def _resolve_ar_account(self, invoice, ar_accounts):
        """Select AR account based on invoice currency."""
        if not ar_accounts:
            return 'Accounts Receivable'
        currency = (invoice.currency or 'USD').upper()
        return ar_accounts.get(currency, ar_accounts.get('USD', 'Accounts Receivable'))

    def _resolve_income_account(self, product_service, income_accounts, description=None):
        """Select income account based on product/service type.

        Falls back to checking description when product_service is empty
        (handles old invoices where product keywords are in the description).
        """
        if not income_accounts:
            return 'Service Revenue'
        # Try product_service first, then fall back to description
        text_to_check = product_service or description or ''
        if not text_to_check:
            return income_accounts.get('default', 'Service Revenue')
        ps_lower = text_to_check.lower().strip().replace(' ', '')
        # Soundtrack matching
        if 'soundtrack' in ps_lower:
            return income_accounts.get('syb', income_accounts.get('default', 'Service Revenue'))
        # Beat Breeze matching
        if 'beatbreeze' in ps_lower or 'beat' in ps_lower:
            return income_accounts.get('bms', income_accounts.get('default', 'Service Revenue'))
        return income_accounts.get('default', 'Service Revenue')

    def _write_invoice(self, output, invoice, ar_accounts, income_accounts, tax_account):
        """Write a single invoice as TRNS + SPL rows + ENDTRNS.

        VAT handling: line item SPL rows use pre-tax amounts (qty * unit_price).
        If the invoice has tax, a separate SPL row credits the tax to the
        VAT Payable account. All amounts must sum to zero.

        Account resolution:
        - AR account: resolved per invoice currency via ar_accounts dict
        - Income account: resolved per line item product via income_accounts dict
        """
        company_name = self._sanitize_text(invoice.company.name)
        invoice_date = self._format_date(invoice.issue_date)
        due_date = self._format_date(invoice.due_date) if invoice.due_date else ''
        invoice_number = self._sanitize_text(invoice.invoice_number)
        memo = self._sanitize_text(invoice.notes or '')

        # Total amount (positive for TRNS = debit to AR)
        total_amount = self._format_amount(invoice.total_amount)

        # TRNS row (invoice header) — AR account based on invoice currency
        ar_account = self._resolve_ar_account(invoice, ar_accounts)
        trns_values = [
            invoice_number,         # TRNSID
            'INVOICE',              # TRNSTYPE
            invoice_date,           # DATE
            ar_account,             # ACCNT (currency-specific AR)
            company_name,           # NAME (customer)
            total_amount,           # AMOUNT (positive = debit AR)
            invoice_number,         # DOCNUM
            memo,                   # MEMO
            due_date,               # DUEDATE
        ]
        output.write('TRNS\t' + '\t'.join(trns_values) + '\n')

        # SPL rows — pre-tax amounts per line item + separate VAT row
        line_items = list(invoice.line_items.all())
        if line_items:
            total_tax = Decimal('0')
            for idx, item in enumerate(line_items, start=1):
                self._write_line_item(
                    output, idx, item, invoice_date,
                    income_accounts, company_name
                )
                # Accumulate tax per line item
                subtotal = item.quantity * item.unit_price
                tax = subtotal * (item.tax_rate / Decimal('100'))
                total_tax += tax

            next_idx = len(line_items) + 1

            # VAT SPL row — only when there's actual tax
            if total_tax > 0 and tax_account:
                vat_memo = f'VAT {line_items[0].tax_rate}%'
                vat_spl = [
                    str(next_idx),          # SPLID
                    'INVOICE',              # TRNSTYPE
                    invoice_date,           # DATE
                    tax_account,            # ACCNT (VAT Payable)
                    company_name,           # NAME
                    self._format_amount(-total_tax),  # AMOUNT (negative = credit)
                    '0',                    # QNTY
                    '0.00',                 # PRICE
                    'Sales Tax',            # INVITEM
                    vat_memo,               # MEMO
                ]
                output.write('SPL\t' + '\t'.join(vat_spl) + '\n')
                next_idx += 1

            # Discount SPL row — if invoice has discount
            default_income = (income_accounts or {}).get('default', 'Service Revenue')
            if invoice.discount_amount and invoice.discount_amount > 0:
                disc_spl = [
                    str(next_idx),          # SPLID
                    'INVOICE',              # TRNSTYPE
                    invoice_date,           # DATE
                    default_income,         # ACCNT (contra-revenue)
                    company_name,           # NAME
                    self._format_amount(invoice.discount_amount),  # AMOUNT (positive = debit)
                    '0',                    # QNTY
                    '0.00',                 # PRICE
                    'Discount',             # INVITEM
                    'Invoice discount',     # MEMO
                ]
                output.write('SPL\t' + '\t'.join(disc_spl) + '\n')
        else:
            # Invoice has no line items — split into pre-tax + VAT
            default_income = (income_accounts or {}).get('default', 'Service Revenue')
            pre_tax = invoice.amount or invoice.total_amount
            tax = invoice.tax_amount or Decimal('0')
            spl_values = [
                '1',                                    # SPLID
                'INVOICE',                              # TRNSTYPE
                invoice_date,                           # DATE
                default_income,                         # ACCNT
                company_name,                           # NAME
                self._format_amount(-pre_tax),          # AMOUNT (negative)
                '1',                                    # QNTY
                self._format_amount(pre_tax),           # PRICE
                'Service',                              # INVITEM
                memo,                                   # MEMO
            ]
            output.write('SPL\t' + '\t'.join(spl_values) + '\n')
            if tax > 0 and tax_account:
                vat_spl = [
                    '2',                                # SPLID
                    'INVOICE',                          # TRNSTYPE
                    invoice_date,                       # DATE
                    tax_account,                        # ACCNT (VAT Payable)
                    company_name,                       # NAME
                    self._format_amount(-tax),          # AMOUNT (negative)
                    '0',                                # QNTY
                    '0.00',                             # PRICE
                    'Sales Tax',                        # INVITEM
                    'VAT',                              # MEMO
                ]
                output.write('SPL\t' + '\t'.join(vat_spl) + '\n')

        output.write('ENDTRNS\n')

    def _write_line_item(self, output, idx, item, invoice_date,
                         income_accounts, company_name):
        """Write a single SPL row for an invoice line item (pre-tax amount).

        Income account is resolved per line item based on product_service field.
        """
        description = self._sanitize_text(item.description or '')
        # Append service period if available
        if item.service_period_start or item.service_period_end:
            period_start = self._format_date(item.service_period_start) if item.service_period_start else ''
            period_end = self._format_date(item.service_period_end) if item.service_period_end else ''
            if period_start and period_end:
                description += f' (Period: {period_start} - {period_end})'
            elif period_start:
                description += f' (From: {period_start})'
            elif period_end:
                description += f' (To: {period_end})'
        quantity = self._format_amount(-item.quantity)  # Negative for SPL credit rows
        unit_price = self._format_amount(item.unit_price)
        # Use pre-tax amount (qty * unit_price), NOT line_total which includes tax
        pre_tax_amount = item.quantity * item.unit_price
        line_amount = self._format_amount(-pre_tax_amount)  # Negative for SPL
        item_name = self._get_item_name(item.product_service, item.description)
        income_account = self._resolve_income_account(item.product_service, income_accounts, item.description)

        spl_values = [
            str(idx),               # SPLID
            'INVOICE',              # TRNSTYPE
            invoice_date,           # DATE
            income_account,         # ACCNT (product-specific income account)
            company_name,           # NAME
            line_amount,            # AMOUNT (negative = credit income, pre-tax)
            quantity,               # QNTY
            unit_price,             # PRICE
            item_name,              # INVITEM
            description,            # MEMO
        ]
        output.write('SPL\t' + '\t'.join(spl_values) + '\n')

    def _format_date(self, date_obj):
        """Format date as DD/MM/YYYY for QuickBooks (Thailand locale)."""
        if not date_obj:
            return ''
        return date_obj.strftime('%d/%m/%Y')

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

    def _get_item_name(self, product_service, description=None):
        """Map CRM product_service to QuickBooks item name.

        Falls back to checking description when product_service is empty
        (handles old invoices where product keywords are in the description).
        """
        text_to_check = product_service
        if not text_to_check:
            text_to_check = description or ''
        if not text_to_check:
            return 'Service'

        # Check exact match first
        ps_lower = text_to_check.lower().strip()
        if ps_lower in PRODUCT_SERVICE_TO_QB_ITEM:
            return PRODUCT_SERVICE_TO_QB_ITEM[ps_lower]

        # Check partial match (e.g., "Soundtrack Your Brand" contains "soundtrack")
        for key, qb_name in PRODUCT_SERVICE_TO_QB_ITEM.items():
            if key in ps_lower.replace(' ', ''):
                return qb_name

        # Use the product_service value itself (sanitized), not the description
        if product_service:
            return self._sanitize_text(product_service)
        return 'Service'
