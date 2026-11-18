"""Record that an invoice has been paid, once, and number its receipt safely.

Receipt numbers keep their existing form, ``REC-TH-2026-0001`` / ``REC-HK-2026-0001``
("highest existing + 1" per issuer and year). Two things make that safe now:

- the invoice row is locked (``SELECT ... FOR UPDATE``) and its status re-read
  inside the transaction, so a repeated or concurrent request for the same
  invoice is refused instead of minting a second receipt;
- numbering takes a transaction-scoped PostgreSQL advisory lock, so two
  invoices marked paid at the same moment cannot read the same "highest" number.

SQLite (local tests only) serialises writers and has no such locks.

This is the only way an invoice becomes Paid or gets a receipt number:
- the invoice serializer (REST create/update, the agents' create_record/update_record,
  the bulk ``update_status``) refuses a change to Paid and never writes ``receipt_number``;
- the admin "Mark selected invoices as paid" action calls ``mark_invoice_paid``;
- the admin change form refuses a change to Paid.
"""
import logging
import zlib
from datetime import date, timedelta

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import serializers

from crm_app.models import Invoice
from crm_app.services.document_context import effective_billing_entity

logger = logging.getLogger(__name__)

# Fixed key for pg_advisory_xact_lock; any 64-bit value unique to this purpose.
RECEIPT_NUMBER_LOCK_KEY = zlib.crc32(b'crm_app.invoice.receipt_number')

NOT_PAYABLE_STATUSES = ('Cancelled', 'Refunded')


class InvoiceNotPayable(Exception):
    """The invoice cannot be marked paid in its current state."""

    def __init__(self, code, message, invoice):
        super().__init__(message)
        self.code = code
        self.message = message
        self.invoice = invoice


class _ExplicitBooleanField(serializers.Field):
    """true or false only (JSON booleans, or the strings "true"/"false")."""
    default_error_messages = {'invalid': 'Use true or false.'}

    def to_internal_value(self, data):
        if data is True or data is False:
            return data
        if isinstance(data, str) and data.lower() in ('true', 'false'):
            return data.lower() == 'true'
        self.fail('invalid')

    def to_representation(self, value):
        return bool(value)


class MarkPaidRequestSerializer(serializers.Serializer):
    """Body of POST /invoices/{id}/mark_paid/. Every field is optional."""
    paid_date = serializers.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        help_text='Date the money arrived (bank date), YYYY-MM-DD. Defaults to today.')
    send_receipt = _ExplicitBooleanField(
        required=False, default=False,
        help_text="Email the receipt to the customer's billing contacts. Defaults to false.")
    payment_method = serializers.CharField(required=False, allow_blank=True, max_length=50)
    transaction_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000,
                                  help_text='Kept in the audit log, not on the invoice.')

    def validate_paid_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('The payment date cannot be in the future.')
        return value


def receipt_prefix(invoice):
    return 'REC-TH' if 'Thailand' in effective_billing_entity(invoice) else 'REC-HK'


def _lock_receipt_numbering():
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [RECEIPT_NUMBER_LOCK_KEY])


def _last_receipt_sequence(pattern):
    last = (Invoice.objects.filter(receipt_number__startswith=pattern)
            .order_by('-receipt_number').values_list('receipt_number', flat=True).first())
    if not last:
        return 0
    try:
        return int(last.split('-')[-1])
    except (ValueError, IndexError):
        return 0


def _next_receipt_number(invoice):
    """Call inside a transaction; the advisory lock is held until it ends."""
    _lock_receipt_numbering()
    pattern = f'{receipt_prefix(invoice)}-{timezone.localdate().year}-'
    return f'{pattern}{_last_receipt_sequence(pattern) + 1:04d}'


# Reasons send_receipt_email writes itself; anything else may carry a mail server's reply.
_RECEIPT_EMAIL_REASONS = (
    'No recipients found for this receipt',
    'No receipt number generated for this invoice',
)


def receipt_email_failure_text(request, invoice, failure):
    """A short reason safe to show; the full failure goes to the server log with a reference."""
    from crm_app.request_ids import request_id_for
    from crm_app.services.recipients import no_recipient_message

    if isinstance(failure, str) and (
            failure in _RECEIPT_EMAIL_REASONS or failure == no_recipient_message(invoice.company, 'receipt')):
        return failure
    reference = request_id_for(request)
    logger.error('Receipt email failed for invoice %s [request_id=%s]: %s', invoice.pk, reference,
                 failure, exc_info=failure if isinstance(failure, BaseException) else None)
    return f'the receipt email could not be sent. Reference: {reference}'


EARLIEST_PAYMENT_DATE = date(2000, 1, 1)
# A payment can arrive before the invoice is issued (advance payment), but not by more than this.
MAX_DAYS_PAID_BEFORE_ISSUE = 366


def earliest_payment_date(invoice):
    """The earliest payment date accepted for this invoice."""
    floor = EARLIEST_PAYMENT_DATE
    if invoice.issue_date:
        floor = max(floor, invoice.issue_date - timedelta(days=MAX_DAYS_PAID_BEFORE_ISSUE))
    return floor


def mark_invoice_paid(invoice_pk, *, paid_date, payment_method='', transaction_id=''):
    """Mark the invoice Paid and give it a receipt number.

    Returns (invoice, old_status, receipt_only). receipt_only is True when the invoice was
    already Paid (set by another route) without a receipt number: it then gets its receipt
    number, keeps its status and keeps its own paid date if it has one.

    Raises InvoiceNotPayable when it is Paid with a receipt already, Cancelled or Refunded.
    A receipt number already on the invoice is kept.
    """
    with transaction.atomic():
        invoice = (Invoice.objects.select_for_update(of=('self',))
                   .select_related('company').get(pk=invoice_pk))
        if invoice.status == 'Paid' and invoice.receipt_number:
            raise InvoiceNotPayable(
                'already_paid', 'This invoice is already marked as paid.', invoice)
        if invoice.status in NOT_PAYABLE_STATUSES:
            raise InvoiceNotPayable(
                'not_payable',
                f'A {invoice.status.lower()} invoice cannot be marked as paid.', invoice)

        old_status = invoice.status
        receipt_only = invoice.status == 'Paid'
        if not invoice.receipt_number:
            invoice.receipt_number = _next_receipt_number(invoice)
        if receipt_only:
            invoice.paid_date = invoice.paid_date or paid_date
            invoice.payment_method = invoice.payment_method or payment_method
            invoice.transaction_id = invoice.transaction_id or transaction_id
        else:
            invoice.status = 'Paid'
            invoice.paid_date = paid_date
            if payment_method:
                invoice.payment_method = payment_method
            if transaction_id:
                invoice.transaction_id = transaction_id
        invoice.save()
    return invoice, old_status, receipt_only
