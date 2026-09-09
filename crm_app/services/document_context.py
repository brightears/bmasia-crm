"""Explicit issuer selection for commercial documents.

Document overrides do not modify the customer's default, currency, or tax rate.
Unknown issuers require correction; country/currency are never issuer evidence.
"""
import re
from decimal import Decimal

BILLING_ENTITY_CHOICES = (
    ('BMAsia (Thailand) Co., Ltd.', 'BMAsia (Thailand) Co., Ltd.'),
    ('BMAsia Limited', 'BMAsia Limited'),
)


def effective_billing_entity(document):
    """Return the document override, otherwise its Company's canonical issuer."""
    override = getattr(document, 'billing_entity', '')
    company = getattr(document, 'company', None)
    value = override or getattr(company, 'billing_entity', '')
    if value not in dict(BILLING_ENTITY_CHOICES):
        raise ValueError(f"Unsupported billing entity: {value or 'blank'}")
    return value


def document_region(document):
    """Number a new document for its selected issuer, not customer location."""
    return 'TH' if effective_billing_entity(document) == BILLING_ENTITY_CHOICES[0][0] else 'HK'


def contract_line_tax_values(line_items):
    """Sum instructed line rates exactly; the weighted rate is display-only."""
    items = list(line_items)
    cents = Decimal('0.01')
    value = sum((item.line_total for item in items), Decimal('0'))
    tax_amount = sum((
        (item.line_total * item.tax_rate / Decimal('100')).quantize(cents)
        for item in items
    ), Decimal('0'))
    weighted_rate = (tax_amount * Decimal('100') / value).quantize(cents) if value else Decimal('0')
    return {
        'value': value, 'tax_rate': weighted_rate,
        'tax_amount': tax_amount, 'total_value': value + tax_amount,
    }


def contract_tailoring_context(contract):
    """Expose current template slots without changing a record or legal text."""
    template = getattr(contract, 'preamble_template', None)
    placeholders = sorted(set(re.findall(r'\{\{\s*(\w+)\s*\}\}', template.content if template else '')))
    slot_fields = {
        'preamble_custom': ['preamble'],
        'payment_custom': ['payment_clause', 'payment_terms'],
        'activation_custom': ['activation_clause', 'activation_terms'],
        'custom_terms': ['additional_terms', 'custom_terms'],
        'payment_schedule': ['payment_schedule'],
    }
    return {
        'pdf_format': (template.pdf_format if template else contract.contract_category) or 'standard',
        'template_id': str(template.pk) if template else None,
        'template_name': template.name if template else None,
        'template_placeholders': placeholders,
        'tailoring_fields': {
            field: {
                'accepted_template_slots': slots,
                'present_template_slots': [slot for slot in slots if slot in placeholders],
                'role': 'additional_customer_text' if field in {'custom_terms', 'payment_schedule'} else 'replacement_clause',
            }
            for field, slots in slot_fields.items()
        },
        'review_rule': (
            'Writable fields are not permission to change approved legal text. '
            'For a full template, replacement clauses need a present named slot; '
            'a missing slot requires a tailored template copy and clause selection. '
            'Additional terms and payment schedule are inserted before signatures when no slot exists. '
            'Preview the PDF and resolve its structured clarifications before delivery.'
        ),
    }
