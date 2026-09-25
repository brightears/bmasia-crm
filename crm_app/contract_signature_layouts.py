"""Closed, reviewable signature-layout tokens for full contract templates."""
from re import escape

STANDARD_SIGNATURE_BLOCKS = 'signature_blocks'
HILTON_TWO_SIGNERS_FOUR_WITNESSES = 'signature_blocks_hotel_2_witness_4'
SIGNATURE_LAYOUT_SLOTS = frozenset({
    STANDARD_SIGNATURE_BLOCKS,
    HILTON_TWO_SIGNERS_FOUR_WITNESSES,
})
SIGNATURE_LAYOUT_TOKEN_PATTERN = (
    r'\{\{\s*(' + '|'.join(map(escape, sorted(SIGNATURE_LAYOUT_SLOTS))) + r')\s*\}\}'
)


def canonical_signature_slot(slot):
    """Map an approved layout token to the one structural signature slot."""
    if slot in SIGNATURE_LAYOUT_SLOTS:
        return STANDARD_SIGNATURE_BLOCKS
    return slot
