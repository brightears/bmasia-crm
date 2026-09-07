"""Reversible CRM-only quarterly sender handover, not a fleet ownership claim."""

from django.conf import settings


def quarterly_owner():
    owner = getattr(settings, "CARA_QUARTERLY_OWNER", "legacy")
    return owner if owner in ("legacy", "cara") else "invalid"


def legacy_quarterly_enabled():
    # An expired Cara credential never silently reactivates the old sender.
    # Unknown configuration disables old quarterly mail until an owner fixes it.
    return quarterly_owner() == "legacy"
