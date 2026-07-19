from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from crm_app.models import ContractLineItem
from crm_app.services.quote_conversion import _contract_billing_frequency_from_quote


def test_contract_line_item_save_accepts_string_decimal_values():
    line_item = ContractLineItem(
        product_service='Soundtrack Your Brand',
        description='Two-zone annual service',
        quantity='2.00',
        unit_price='100.00',
        discount_percentage='10.00',
    )

    with patch('django.db.models.Model.save', return_value=None):
        line_item.save()

    assert line_item.line_total == Decimal('180.000000')


def test_quote_conversion_maps_one_time_billing_to_contract_display_value():
    quote = SimpleNamespace(billing_frequency='one-time')

    assert _contract_billing_frequency_from_quote(quote, {}) == 'One-time'
