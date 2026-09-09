"""Query documents by the same issuer precedence used by their PDFs.

Finance screens use entity slugs, while Company and commercial documents store
canonical legal names. A document override must never be attributed to its
customer's different default entity or lost because an invoice has no contract.
"""

from django.db.models import Q

from crm_app.services.document_context import BILLING_ENTITY_CHOICES


ENTITY_FILTER_ALIASES = {
    "bmasia_th": "BMAsia (Thailand) Co., Ltd.",
    "bmasia_hk": "BMAsia Limited",
}


def finance_entity_slug(billing_entity):
    """Normalize legal-name inputs for finance's existing slug-backed records.

    Preserve literal ``all`` here: legacy finance snapshot/expense selectors
    do not consistently implement combined reports. This document rollout
    must not change only the revenue side into an unfiltered combined total.
    """
    return {name: slug for slug, name in ENTITY_FILTER_ALIASES.items()}.get(
        billing_entity, billing_entity,
    )


def document_entity_q(billing_entity, *, prefix=""):
    """Return an issuer Q expression; prefix identifies a related document."""
    if billing_entity in (None, "", "all"):
        return Q()
    canonical = ENTITY_FILTER_ALIASES.get(billing_entity, billing_entity)
    if canonical not in dict(BILLING_ENTITY_CHOICES):
        raise ValueError(f"Unsupported billing entity filter: {billing_entity}")
    return Q(**{f"{prefix}billing_entity": canonical}) | Q(**{
        f"{prefix}billing_entity": "",
        f"{prefix}company__billing_entity": canonical,
    })


def filter_document_entity(queryset, billing_entity, *, prefix=""):
    return queryset.filter(document_entity_q(billing_entity, prefix=prefix))
