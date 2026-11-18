"""The pricing-block split rule holds when a row prints Thai text.

A Thai zone name is printed in Sarabun and its stacked tone marks are lifted
(crm_app/pdf_thai.py), so the row's height is measured with a different font.
The split rule measures rows before ReportLab lays them out; these tests put a
Thai row in every position of the threshold layouts, and in large-amount
layouts, and check the rendered pages against the rule applied to the layout
without block measuring, exactly as the Latin-only tests do.
"""

from contextlib import contextmanager
from unittest import mock

import pytest

import test_quote_pricing_block_split_rule as split_rule


THAI_ZONE = 'ห้องอาหาร ที่ปรึกษา ชื่อ น้ำ ปั้น ชั้น 1'


@contextmanager
def _thai_rows(rows):
    real = split_rule._item

    def item(index, words, price='1000.00'):
        value = real(index, words, price)
        if index in rows:
            begin, _, rest = value.description.partition(' ')
            value.description = f'{begin} {THAI_ZONE} {rest}'
        return value

    with mock.patch.object(split_rule, '_item', item):
        yield


def _check(row_count, words, thai, tall=(), **money):
    with _thai_rows(thai):
        old, fits_a_page = split_rule._layout(
            row_count, words, layout_before_measuring=True, tall=tall, **money,
        )
        new, _ = split_rule._layout(row_count, words, tall=tall, **money)
    assert new.totals == new.rows[-1]
    assert new.heading == new.rows[0] == new.headers[0]
    assert sorted(set(new.headers)) == sorted(set(new.rows))
    assert new == split_rule._expected(old, fits_a_page)
    return old, new


THRESHOLD_LAYOUTS = [
    (case.values[0], case.values[1], case.values[2]) for case in split_rule.THRESHOLD_CASES
]


@pytest.mark.parametrize('row_count, words, tall', THRESHOLD_LAYOUTS)
def test_split_rule_holds_with_a_thai_row_in_every_position(row_count, words, tall):
    for position in range(1, row_count + 1):
        _check(row_count, words, {position}, tall=tall)


@pytest.mark.parametrize('row_count', [5, 8, 10, 12])
def test_split_rule_holds_when_every_row_is_thai(row_count):
    _check(row_count, 0, set(range(1, row_count + 1)))


@pytest.mark.parametrize('currency, price', split_rule.LARGE_AMOUNTS)
@pytest.mark.parametrize('row_count', [6, 8, 10])
def test_large_amounts_with_thai_rows_follow_the_rule(currency, price, row_count):
    for thai in ({row_count - 1}, {row_count}, set(range(1, row_count + 1))):
        _check(row_count, 0, thai, currency=currency, price=price)


def test_a_thai_row_still_triggers_the_earlier_split():
    # 9 short rows split 8 + 1 naturally; with Thai in the row given up the
    # block still splits one row earlier, 7 + 2.
    old, new = _check(9, 0, {8})
    assert old.rows == (0,) * 8 + (1,)
    assert new == split_rule.Layout(0, (0, 1), (0,) * 7 + (1,) * 2, 1)
