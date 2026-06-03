#!/usr/bin/env python3
"""
Preview the quote PDF renderer (crm_app/quote_pdf.py) WITHOUT the Django stack.

Builds a duck-typed sample quote and renders it via the real build_quote_pdf, so
the output is byte-for-byte what QuoteViewSet.pdf will produce in production. Only
needs `reportlab` + `Pillow`.

Usage:
    /tmp/qpdf-venv/bin/python scripts/preview_quote_pdf.py /tmp/AFTER.pdf
"""
import sys
import os
from datetime import date
from types import SimpleNamespace

# Make crm_app importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register the Unicode fonts the renderer expects (the Django app does this at
# views.py import time; we replicate it for the standalone preview).
for name, fname in [('DejaVuSans', 'DejaVuSans.ttf'), ('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf')]:
    try:
        pdfmetrics.registerFont(TTFont(name, fname))
    except Exception:
        pdfmetrics.registerFont(TTFont(name, f'/usr/share/fonts/truetype/dejavu/{fname}'))

from crm_app.quote_pdf import build_quote_pdf


def _format_duration_from_months(months):
    if not months or months <= 0:
        return 'As specified'
    if months == 1:
        return '1 month'
    if months < 12:
        return f'{months} months'
    if months == 12:
        return '1 year'
    if months % 12 == 0:
        years = months // 12
        return f'{years} year{"s" if years > 1 else ""}'
    years = months // 12
    remaining = months % 12
    return f'{years} year{"s" if years > 1 else ""} and {remaining} month{"s" if remaining > 1 else ""}'


def format_address_multiline(company):
    lines = [x for x in [
        getattr(company, 'address_line1', ''), getattr(company, 'address_line2', ''),
        getattr(company, 'city', ''), getattr(company, 'state', ''),
        getattr(company, 'postal_code', ''), getattr(company, 'country', ''),
    ] if x and x != 'Other']
    return '<br/>'.join(lines)


def sample_quote():
    """Hilton Padalarang Bandung — HK-QT26050: 4z SYB @ $290/zone/yr, 2-year term,
    4 complimentary Soundtrack Player units (value $250 each)."""
    company = SimpleNamespace(
        legal_entity_name='PT Padalarang Bandung Hospitality',
        name='Hilton Padalarang Bandung',
        address_line1='Jl. Padalarang No. 1', address_line2='',
        city='Bandung', state='West Java', postal_code='40553', country='Indonesia',
        billing_entity='BMAsia Limited',
    )
    contact = SimpleNamespace(name='Mario', email='mario@example.com', phone='')

    def li(product, desc, qty, price, value=None):
        return SimpleNamespace(
            product_service=product, description=desc,
            quantity=qty, unit_price=price, unit_value=value,
            line_total=qty * price,
        )

    items = [
        li('soundtrack', 'Lobby', 1, 290.0),
        li('soundtrack', 'Dining Area 1', 1, 290.0),
        li('soundtrack', 'Dining Area 2', 1, 290.0),
        li('soundtrack', 'Pool Bar', 1, 290.0),
        li('Soundtrack Player', 'Soundtrack Player 3 hardware unit', 4, 0.0, value=250.0),
    ]

    return SimpleNamespace(
        quote_number='HK-QT26050',
        company=company, contact=contact,
        valid_from=date(2026, 6, 3), valid_until=date(2026, 7, 3),
        contract_duration_months=24,
        currency='USD',
        subtotal=1160.0, discount_amount=0.0, tax_amount=0.0, total_value=1160.0,
        billing_frequency='annual', payment_schedule='',
        terms_conditions='', notes='',
        line_items=SimpleNamespace(all=lambda: items),
    )


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/AFTER.pdf'
    entity = {
        'name': 'BMAsia Limited',
        'address': '22nd Floor, Tai Yau Building, 181 Johnston Road, Wanchai, Hong Kong',
        'phone': '+66 2153 3520',
        'tax': None,
        'bank': 'HSBC, HK',
        'swift': 'HSBCHKHHHKH',
        'account': '808-021570-838',
        'payment_terms_default': ('by bank transfer on a net received, paid in full basis to '
                                  "BMA's HSBC Bank, Hong Kong due immediately as invoiced to "
                                  'activate the music subscription. All bank transfer fees and '
                                  'taxes are borne by the Client.'),
        'billing_entity': 'BMAsia Limited',
    }
    logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png')
    pdf = build_quote_pdf(sample_quote(), entity, logo,
                          format_address_multiline=format_address_multiline,
                          format_duration=_format_duration_from_months)
    with open(out, 'wb') as f:
        f.write(pdf)
    print(f"wrote {out} ({len(pdf):,} bytes)")


if __name__ == '__main__':
    main()
