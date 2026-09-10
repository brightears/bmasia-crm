"""Compatibility entry point for the approved A4 proforma invoice renderer.

The retired Letter renderer was removed. All callers, including the CRM route
and MCP helper, now receive the same print-light commercial design.
"""

from crm_app.proforma_pdf_v2 import build_proforma_pdf_v2


def build_proforma_pdf(
    contract,
    entity,
    logo_path,
    format_address_multiline,
    issue_date=None,
):
    return build_proforma_pdf_v2(
        contract,
        entity,
        logo_path,
        format_address_multiline,
        issue_date=issue_date,
    )
