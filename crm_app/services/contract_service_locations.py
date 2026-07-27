"""Safety helpers for contract service-location pricing.

Contract PDFs show both a total contract value and a service-location count.
Those values must not be sourced independently when the contract uses explicit
per-zone pricing, otherwise a stale location row can produce a commercially
incorrect document.
"""

from decimal import Decimal, InvalidOperation


MONEY_TOLERANCE = Decimal("0.01")


def service_location_pricing_mismatch(contract):
    """Return mismatch evidence, or ``None`` when the values reconcile.

    The check is intentionally limited to the unambiguous flat-price case:

    - at least one ContractServiceLocation exists;
    - no contract line items provide a separate total source;
    - per-zone pricing is enabled;
    - every row has either its own price or the contract fallback price; and
    - no contract-level discount changes the simple sum.

    More complex contracts continue to use their line-item or negotiated total
    logic. This guard targets the exact class of failure where the PDF printed
    one total next to a contradictory zone count.
    """

    locations = list(contract.service_locations.all())
    if not locations or not getattr(contract, "show_zone_pricing_detail", False):
        return None

    line_items = getattr(contract, "line_items", None)
    if line_items is not None and line_items.exists():
        return None

    try:
        discount = Decimal(str(getattr(contract, "discount_percentage", 0) or 0))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if discount != 0:
        return None

    fallback_price = getattr(contract, "price_per_zone", None)
    prices = []
    for location in locations:
        price = getattr(location, "price", None)
        if price is None:
            price = fallback_price
        if price is None:
            return None
        try:
            prices.append(Decimal(str(price)))
        except (InvalidOperation, TypeError, ValueError):
            return None

    actual_value = getattr(contract, "value", None)
    if actual_value is None:
        return None
    try:
        actual_value = Decimal(str(actual_value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    expected_value = sum(prices, Decimal("0"))
    if abs(expected_value - actual_value) <= MONEY_TOLERANCE:
        return None

    return {
        "zone_count": len(locations),
        "expected_value": expected_value.quantize(MONEY_TOLERANCE),
        "actual_value": actual_value.quantize(MONEY_TOLERANCE),
        "currency": getattr(contract, "currency", "") or "",
    }


def pricing_mismatch_message(mismatch):
    """Render a concise operator-facing explanation for API/PDF failures."""

    return (
        "Contract total does not reconcile with service-location pricing: "
        f"{mismatch['zone_count']} zone(s) total "
        f"{mismatch['currency']} {mismatch['expected_value']}, but contract.value is "
        f"{mismatch['currency']} {mismatch['actual_value']}. "
        "Correct the rows or contract value before generating a customer PDF."
    )
