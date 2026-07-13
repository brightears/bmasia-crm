"""renewal_book_service.py — the Renewal Book.

A funnel month-tab, built from CRM data. Single source of truth shared by the REST action
(ContractViewSet.renewal_book) and the MCP tool (mcp.renewal_book) so the agent-facing surface
and the human-facing surface can never drift. Built to retire the Google-Sheets renewal funnel.
"""
import calendar
from datetime import date


def _product_of(contract):
    """Best label of the contract's product (Soundtrack / Beat Breeze / Other)."""
    st = (contract.service_type or '').strip().lower()
    if 'beat' in st or st == 'lim':
        return 'Beat Breeze'
    if 'sound' in st or 'syb' in st:
        return 'Soundtrack'
    cp = (getattr(contract.company, 'contracted_product', '') or '').lower()
    return {'beatbreeze': 'Beat Breeze', 'soundtrack': 'Soundtrack'}.get(cp, 'Other')


def build_renewal_book(year, month, currency=None):
    """Return the renewal book for a year/month (optionally one currency) as a plain dict.

    Raises ValueError/TypeError on bad year/month so callers can return a 400.
    """
    from crm_app.models import Contract
    year, month = int(year), int(month)
    if not (1 <= month <= 12):
        raise ValueError('month must be 1-12')
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    qs = (Contract.objects
          .filter(end_date__gte=month_start, end_date__lte=month_end)
          .exclude(status='Draft')
          .select_related('company', 'company__parent_company')
          .prefetch_related('service_locations', 'invoices', 'renewals'))
    if currency:
        qs = qs.filter(currency=currency)

    rows, totals, status_totals = [], {}, {}
    for c in qs:
        group = c.company.parent_company.name if c.company.parent_company else c.company.name
        # Prefer the real service_location rows; when a contract has none yet, fall back to the
        # funnel-sourced company.contracted_zone_count so the book/parity aren't blind to the zone
        # count. zones_source flags which, so an empty-service_locations contract is still visible.
        zones = c.service_locations.count()
        zones_source = 'service_locations'
        if zones == 0:
            fallback = getattr(c.company, 'contracted_zone_count', None) or 0
            if fallback:
                zones, zones_source = fallback, 'contracted_zone_count'
        product = _product_of(c)
        renewals = list(c.renewals.all())
        successor = renewals[0] if renewals else None
        invoices = list(c.invoices.all())
        outstanding = sum(float(i.total_amount or 0) for i in invoices if i.status in ('Sent', 'Overdue'))
        paid = bool(invoices) and all(i.status == 'Paid' for i in invoices)
        val = float(c.value or 0)
        rows.append({
            'contract_number': c.contract_number,
            'corporate_group': group,
            'company': c.company.name,
            'country': c.company.country or '',
            'end_date': c.end_date.isoformat() if c.end_date else None,
            'zones': zones,
            'zones_source': zones_source,
            'value': val,
            'currency': c.currency,
            'product': product,
            'lifecycle_type': c.lifecycle_type or '',
            'status': c.status,
            'cancelled': c.status == 'Cancelled',
            'auto_renew': c.auto_renew,
            'billing_frequency': c.billing_frequency,
            'successor_contract': successor.contract_number if successor else None,
            'successor_status': successor.status if successor else None,
            'invoices_paid': paid,
            'outstanding_amount': round(outstanding, 2),
        })
        t = totals.setdefault(product, {'contracts': 0, 'zones': 0, 'value': 0.0})
        t['contracts'] += 1
        t['zones'] += zones
        t['value'] += val
        status_totals[c.status] = status_totals.get(c.status, 0) + 1

    for t in totals.values():
        t['value'] = round(t['value'], 2)
    rows.sort(key=lambda r: (r['corporate_group'].lower(), r['company'].lower()))
    return {
        'year': year,
        'month': month,
        'month_label': month_start.strftime('%B %Y'),
        'currency': currency or 'ALL',
        'count': len(rows),
        'totals_by_product': totals,
        'totals_by_status': status_totals,
        'rows': rows,
    }
