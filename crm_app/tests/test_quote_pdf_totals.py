from decimal import Decimal
from types import SimpleNamespace

from crm_app.quote_pdf import quote_recurring_and_onetime_totals


def _line_item(product_service, line_total):
    return SimpleNamespace(product_service=product_service, line_total=Decimal(line_total))


def test_quote_recurring_total_excludes_one_time_hardware_lines():
    recurring_total, one_time_total = quote_recurring_and_onetime_totals([
        _line_item('soundtrack', '600.00'),
        _line_item('Soundtrack Player', '400.00'),
    ])

    assert recurring_total == Decimal('600.00')
    assert one_time_total == Decimal('400.00')


def test_quote_one_time_split_ignores_complimentary_hardware_value():
    recurring_total, one_time_total = quote_recurring_and_onetime_totals([
        _line_item('beatbreeze', '1200.00'),
        _line_item('Soundtrack Player', '0.00'),
    ])

    assert recurring_total == Decimal('1200.00')
    assert one_time_total == Decimal('0')
