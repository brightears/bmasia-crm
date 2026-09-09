"""Convert an accepted Quote into a Draft Contract.

Shared by the REST action (QuoteViewSet.convert_to_contract) and the MCP tool
(convert_quote_to_contract) so agents and the UI take exactly one code path.

Behaviour:
  * Idempotent — if a non-Cancelled contract already links this quote, it is returned untouched
    (no duplicate). This is what prevented duplicates when a quote was converted twice.
  * Creates a Draft contract, copies the quote's financial terms + line items, and derives
    service locations (the rows that drive the contract PDF product/zone table).
  * The product→platform mapping is best-effort (Beat Breeze / LIM → custom + 'Beat Breeze' label,
    matching the proven Meliá pattern; Soundtrack / SYB → soundtrack; anything else → custom with
    the product name as the label). The caller is told to review the derived locations.
"""
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from dateutil.relativedelta import relativedelta

from crm_app.models import Contract


def _parse_date(v):
    if not v:
        return None
    if hasattr(v, 'year'):
        return v
    try:
        return datetime.strptime(str(v)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _platform_for(product):
    """Return (platform, custom_service_name) for a line-item product name."""
    p = (product or '').strip().lower().replace(' ', '')
    if any(k in p for k in ('beatbreeze', 'beatbreze', 'lim', 'licenseinclusive')):
        return 'custom', 'Beat Breeze'
    if 'soundtrack' in p or p == 'syb':
        return 'soundtrack', ''
    return 'custom', (product or '').strip()[:200]


def _contract_billing_frequency_from_quote(quote, overrides):
    """Normalize quote billing codes to the title-case values used by contracts."""
    raw = overrides.get('billing_frequency') or getattr(quote, 'billing_frequency', None) or 'Annual'
    value = str(raw).strip()
    normalized = value.lower()
    display_values = {
        'annual': 'Annually',
        'annually': 'Annually',
        'monthly': 'Monthly',
        'quarterly': 'Quarterly',
        'biannual': 'Semi-annually',
        'bi-annually': 'Semi-annually',
        'semi-annually': 'Semi-annually',
        'one-time': 'One-time',
        'one time': 'One-time',
        'onetime': 'One-time',
        'upfront': 'One-time',
        'full term': 'One-time',
        'full-term': 'One-time',
    }
    return display_values.get(normalized, value or 'Annual')


@transaction.atomic
def convert_quote_to_contract(quote, overrides=None):
    """Returns (contract, info). info includes {already_existed, service_locations_derived, message}."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        raise ValueError('Contract overrides must be a JSON object.')
    allowed = {
        'start_date', 'end_date', 'contract_duration_months', 'billing_frequency',
        'property_name', 'notes', 'price_per_zone', 'customer_contact_name',
        'customer_contact_title', 'customer_contact_email', 'billing_entity',
        'payment_schedule', 'payment_custom', 'preamble_custom', 'activation_custom',
        'custom_terms',
    }
    unknown = set(overrides) - allowed
    if unknown:
        raise ValueError('Unsupported contract override field(s): ' + ', '.join(sorted(unknown)))
    from crm_app.services.document_context import BILLING_ENTITY_CHOICES
    if 'billing_entity' in overrides and overrides['billing_entity'] not in {'', *dict(BILLING_ENTITY_CHOICES)}:
        raise ValueError('billing_entity must be a canonical BMAsia issuer, or blank for the Company default.')
    for field in ('payment_schedule', 'payment_custom', 'preamble_custom', 'activation_custom', 'custom_terms'):
        if field in overrides and not isinstance(overrides[field], str):
            raise ValueError(f'{field} must be text; use an empty string to clear it.')

    existing = Contract.objects.filter(quote=quote).exclude(status='Cancelled').first()
    if existing:
        return existing, {
            'already_existed': True,
            'message': (f"Quote {quote.quote_number} already has contract {existing.contract_number} "
                        f"({existing.status}); returned it — no duplicate created."),
        }

    months = int(overrides.get('contract_duration_months')
                 or getattr(quote, 'contract_duration_months', None) or 12)
    start = _parse_date(overrides.get('start_date')) or quote.valid_from or timezone.now().date()
    end = _parse_date(overrides.get('end_date')) or (start + relativedelta(months=months))

    line_items = list(quote.line_items.all())
    prices = {li.unit_price for li in line_items if li.unit_price}
    price_per_zone = overrides.get('price_per_zone') or (next(iter(prices)) if len(prices) == 1 else None)
    quote_base = quote.subtotal or quote.total_value
    # Preserve the approved quotation's exact tax amount. The header rate is
    # only a display summary; copied per-line rates may intentionally differ.
    tax_rate = (quote.tax_amount * Decimal('100') / quote_base).quantize(Decimal('0.01')) if quote_base else Decimal('0')

    contract = Contract.objects.create(
        company=quote.company,
        quote=quote,
        opportunity=quote.opportunity,
        status='Draft',                       # save() assigns a deferred DRAFT-xxxx number
        start_date=start,
        end_date=end,
        value=quote_base,
        total_value=quote.total_value,
        tax_rate=tax_rate,
        tax_amount=quote.tax_amount,
        currency=quote.currency,
        billing_entity=overrides.get('billing_entity', getattr(quote, 'billing_entity', '')),
        # The quotation labels terms_conditions as PAYMENT TERMS. Preserve that
        # exact text, with schedule separate, rather than translating legal text.
        payment_custom=overrides.get('payment_custom', quote.terms_conditions),
        payment_schedule=overrides.get('payment_schedule', quote.payment_schedule),
        preamble_custom=overrides.get('preamble_custom', ''),
        activation_custom=overrides.get('activation_custom', ''),
        custom_terms=overrides.get('custom_terms', ''),
        billing_frequency=_contract_billing_frequency_from_quote(quote, overrides),
        property_name=overrides.get('property_name', ''),
        price_per_zone=price_per_zone,
        show_zone_pricing_detail=bool(price_per_zone),
        notes=overrides.get('notes') or f"Created from quote {quote.quote_number}",
        customer_contact_name=overrides.get('customer_contact_name', ''),
        customer_contact_title=overrides.get('customer_contact_title', ''),
        customer_contact_email=overrides.get('customer_contact_email', ''),
    )

    derived = 0
    for idx, li in enumerate(line_items):
        contract.line_items.create(
            product_service=li.product_service, description=li.description, quantity=li.quantity,
            unit_price=li.unit_price, discount_percentage=li.discount_percentage,
            tax_rate=li.tax_rate, line_total=li.line_total)
        platform, custom_name = _platform_for(li.product_service)
        contract.service_locations.create(
            location_name=(li.description or li.product_service or '').strip()[:200],
            platform=platform, custom_service_name=custom_name, sort_order=idx, price=li.unit_price)
        derived += 1

    return contract, {
        'already_existed': False,
        'service_locations_derived': derived,
        'message': (f"Draft contract {contract.contract_number} created from quote {quote.quote_number}. "
                    f"Review the {derived} derived service location(s) — the product/zone mapping is best-effort."),
    }
