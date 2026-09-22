"""Fail-closed rules for the two Beat Breeze yearly player-box variants."""

import re
from decimal import Decimal, InvalidOperation


BEAT_BREEZE_YEARLY_EXCLUDES_PLAYERS = "beat_breeze_yearly"
BEAT_BREEZE_YEARLY_INCLUDES_CHARGED_PLAYERS = "beat_breeze_yearly_with_players"
BEAT_BREEZE_YEARLY_VARIANTS = {
    BEAT_BREEZE_YEARLY_EXCLUDES_PLAYERS,
    BEAT_BREEZE_YEARLY_INCLUDES_CHARGED_PLAYERS,
}

_PLAYER_BOX_PATTERN = re.compile(r"\bplayer\s*box(?:es)?\b", re.IGNORECASE)
_FREE_WORDING_PATTERN = re.compile(
    r"\b(?:provided|free|complimentary)\b|\bno\s+charge\b",
    re.IGNORECASE,
)


def _value(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _text(item):
    return " ".join(
        str(_value(item, field, "") or "")
        for field in ("product_service", "name", "description")
    ).strip()


def is_player_box_item(item):
    return bool(_PLAYER_BOX_PATTERN.search(_text(item)))


def _positive_price(item):
    try:
        quantity = Decimal(str(_value(item, "quantity", 0) or 0))
        unit_price = Decimal(str(_value(item, "unit_price", 0) or 0))
        discount = Decimal(str(_value(item, "discount_percentage", 0) or 0))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return quantity > 0 and unit_price > 0 and discount < 100


def player_box_variant_error(service_type, line_items, service_wording=()):
    """Return a user-facing validation error, or ``None`` when consistent."""
    if service_type not in BEAT_BREEZE_YEARLY_VARIANTS:
        return None

    line_items = list(line_items or [])
    wording = [*line_items, *(service_wording or [])]
    player_items = [item for item in line_items if is_player_box_item(item)]

    for item in wording:
        text = _text(item)
        if _PLAYER_BOX_PATTERN.search(text) and _FREE_WORDING_PATTERN.search(text):
            return (
                "Player boxes must never be described as provided, free, complimentary, "
                "or at no charge. Use a positive-price Player Box line item."
            )

    if service_type == BEAT_BREEZE_YEARLY_EXCLUDES_PLAYERS:
        if player_items:
            return (
                "This Beat Breeze yearly variant excludes player boxes. Remove the Player Box "
                "line item or select the charged-player-box variant."
            )
        return None

    if not player_items:
        return (
            "The charged-player-box Beat Breeze variant requires a Player Box line item "
            "with a positive quantity and unit price."
        )
    if any(not _positive_price(item) for item in player_items):
        return (
            "Every Player Box line item must have a positive quantity and unit price and "
            "must not be discounted to zero."
        )
    return None


def contract_player_box_variant_error(contract):
    service_type = getattr(contract, 'service_type', '')
    if service_type not in BEAT_BREEZE_YEARLY_VARIANTS:
        return None
    service_items = getattr(contract, 'service_items', None)
    line_items = getattr(contract, 'line_items', None)
    service_wording = (
        list(service_items.all()) if service_items is not None else []
    ) + list(getattr(contract, 'custom_service_items', None) or [])
    return player_box_variant_error(
        service_type,
        line_items.all() if line_items is not None else [],
        service_wording,
    )
