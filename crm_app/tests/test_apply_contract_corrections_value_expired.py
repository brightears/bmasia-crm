"""apply_contract_corrections v1: set_value on an activation, and an Expired old term closed as Renewed.

All data is synthetic. Helpers come from the main v1 test module.
"""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.core.management.base import CommandError

from crm_app.models import ContractLineItem, ContractServiceLocation, ContractZone, Zone
from crm_app.tests.test_apply_contract_corrections import (
    _a, _b, _c, _command_audits, _company, _contract, _execute, _file, _run, _status, _valid_entry,
)


def _expired_pair(successor_status='Draft', linked=True, old_end=None, **successor_extra):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 1, 1), end_date=old_end or date(2025, 12, 31),
                    is_active=False)
    new = _contract(company, status=successor_status, start=date(2026, 9, 15),
                    renewed_from=old if linked else None, **successor_extra)
    return old, new


def _refusal(tmp_path, entries):
    return _run('--file', _file(tmp_path, entries))


def _values(contract):
    contract.refresh_from_db()
    return contract.value, contract.tax_amount, contract.total_value


# --- Expired old term ---------------------------------------------------------------

def test_b_pair_with_expired_old_term_closes_it_as_renewed_status_only(tmp_path):
    old, new = _expired_pair()
    old_dates = (old.start_date, old.end_date)
    path = _file(tmp_path, _b(old, new))

    dry = _run('--file', path)
    assert dry.count('[WOULD-APPLY]') == 2
    assert 'Expired -> Renewed' in dry
    assert _status(old) == 'Expired'

    out, journal = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    old.refresh_from_db()
    assert old.status == 'Renewed' and old.is_active is False
    assert (old.start_date, old.end_date) == old_dates
    assert _status(new) == 'Active'
    assert _command_audits(old).count() == 1

    assert _run('--file', path).count('[ALREADY-APPLIED]') == 2
    revert = _run('--revert', journal, '--execute')
    assert revert.count('[REVERTED]') == 2
    assert _status(old) == 'Expired'
    assert _status(new) == 'Draft'


def test_a_with_expired_old_term_and_linked_active_successor(tmp_path):
    old, new = _expired_pair(successor_status='Active')
    path = _file(tmp_path, _a(old))
    out, journal = _execute(tmp_path, path)
    assert '[APPLIED] A' in out
    old.refresh_from_db()
    assert old.status == 'Renewed' and (old.start_date, old.end_date) == (date(2025, 1, 1), date(2025, 12, 31))
    assert _status(new) == 'Active'
    _run('--revert', journal, '--execute')
    assert _status(old) == 'Expired'


def test_a_with_expired_old_term_refused_without_renewed_from_link(tmp_path):
    old, new = _expired_pair(successor_status='Active', linked=False)
    assert '[SKIPPED:no_active_successor]' in _refusal(tmp_path, _a(old))
    assert _status(old) == 'Expired'


def test_a_with_expired_old_term_refused_when_successor_is_on_another_company(tmp_path):
    old = _contract(_company(), status='Expired', start=date(2025, 1, 1), end_date=date(2025, 12, 31))
    _contract(_company(), status='Active', start=date(2026, 9, 15), renewed_from=old)
    assert '[SKIPPED:no_active_successor]' in _refusal(tmp_path, _a(old))
    assert _status(old) == 'Expired'


@pytest.mark.parametrize('kind', ['A', 'B'])
def test_expired_old_term_refused_when_terms_overlap(tmp_path, kind):
    old, new = _expired_pair(successor_status='Active' if kind == 'A' else 'Sent', old_end=date(2026, 9, 15))
    entries = _a(old) if kind == 'A' else _b(old, new)
    assert '[SKIPPED:terms_overlap]' in _refusal(tmp_path, entries)
    assert _status(old) == 'Expired'


def test_activation_alone_still_refused_when_it_would_close_an_expired_predecessor(tmp_path):
    old, new = _expired_pair(successor_status='Sent')
    assert '[SKIPPED:would_close_contract_outside_file]' in _refusal(tmp_path, _c(new))
    assert _status(old) == 'Expired' and _status(new) == 'Sent'


def test_expired_old_term_on_another_company_refused_in_pair(tmp_path):
    old = _contract(_company(), status='Expired', start=date(2025, 1, 1), end_date=date(2025, 12, 31))
    new = _contract(_company(), status='Sent', start=date(2026, 9, 15), renewed_from=old)
    assert '[SKIPPED:different_companies]' in _refusal(tmp_path, _b(old, new))


def test_expired_to_active_is_still_not_allowed(tmp_path):
    c = _contract(_company(), status='Expired')
    assert '[SKIPPED:transition_not_allowed]' in _refusal(tmp_path, _c(c))


def test_expired_old_term_zone_links_handed_over_and_reopened_on_revert(tmp_path):
    old, new = _expired_pair()
    zone = Zone.objects.create(company=old.company, name='Fixture zone', status='online')
    old_link = ContractZone.objects.create(contract=old, zone=zone, start_date=old.start_date, is_active=True)
    ContractZone.objects.create(contract=new, zone=zone, start_date=new.start_date, is_active=True)
    _, journal = _execute(tmp_path, _file(tmp_path, _b(old, new)))
    old_link.refresh_from_db()
    assert old_link.is_active is False and old_link.end_date == date(2025, 12, 31)
    _run('--revert', journal, '--execute')
    old_link.refresh_from_db()
    assert old_link.is_active is True and old_link.end_date is None


# --- set_value -----------------------------------------------------------------------

def _value_pair(**successor_extra):
    company = _company()
    old = _contract(company, status='Active')
    new = _contract(company, status='Sent', start=date(2026, 11, 1), renewed_from=old,
                    value=Decimal('26000.00'), tax_rate=Decimal('7.00'), tax_amount=Decimal('1820.00'),
                    total_value=Decimal('27820.00'), currency='THB', **successor_extra)
    return old, new


SET = {'from': '26000.00', 'to': '21000.00'}


def test_set_value_activates_with_new_value_and_recomputes_tax(tmp_path):
    old, new = _value_pair()
    path = _file(tmp_path, _b(old, new, set_value=SET))
    dry = _run('--file', path)
    assert 'value 26000.00 -> 21000.00' in dry
    assert _values(new) == (Decimal('26000.00'), Decimal('1820.00'), Decimal('27820.00'))

    out, journal = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    assert _values(new) == (Decimal('21000.00'), Decimal('1470.00'), Decimal('22470.00'))
    new.refresh_from_db()
    assert new.currency == 'THB' and new.status == 'Active'
    audit = _command_audits(new).get()
    assert audit.changes['value'] == {'old': '26000.00', 'new': '21000.00'}
    assert audit.changes['total_value'] == {'old': '27820.00', 'new': '22470.00'}
    row = json.load(open(journal))['groups'][0]['contracts'][0]
    assert row['before']['value'] == '26000.00' and row['after']['value'] == '21000.00'

    assert _run('--file', path).count('[ALREADY-APPLIED]') == 2
    _run('--revert', journal, '--execute')
    assert _values(new) == (Decimal('26000.00'), Decimal('1820.00'), Decimal('27820.00'))
    assert _status(new) == 'Sent' and _status(old) == 'Active'


def test_set_value_refused_when_current_value_differs_from_file(tmp_path):
    old, new = _value_pair()
    path = _file(tmp_path, _b(old, new, set_value={'from': '25000.00', 'to': '21000.00'}))
    assert '[SKIPPED:value_changed]' in _run('--file', path)
    assert _values(new)[0] == Decimal('26000.00')


def test_set_value_already_active_with_other_value_is_refused_not_applied(tmp_path):
    old, new = _value_pair()
    entries = _b(old, new, set_value=SET)
    new.status = 'Active'
    new.save()
    old.status = 'Renewed'
    old.save()
    # same status/dates as the target but the value was never changed
    out = _run('--file', _file(tmp_path, entries))
    assert '[SKIPPED:value_changed]' in out


def test_set_value_refused_with_line_items(tmp_path):
    old, new = _value_pair()
    ContractLineItem.objects.create(contract=new, product_service='Fixture', unit_price=Decimal('26000.00'),
                                    line_total=Decimal('26000.00'))
    assert '[SKIPPED:value_has_line_items]' in _refusal(tmp_path, _b(old, new, set_value=SET))
    assert _values(new)[0] == Decimal('26000.00')


def test_set_value_refused_when_priced_rows_would_not_add_up(tmp_path):
    old, new = _value_pair(show_zone_pricing_detail=True)
    ContractServiceLocation.objects.create(contract=new, location_name='Lobby', price=Decimal('12000.00'))
    ContractServiceLocation.objects.create(contract=new, location_name='Bar', price=Decimal('14000.00'))
    assert '[SKIPPED:value_contradicts_location_prices]' in _refusal(tmp_path, _b(old, new, set_value=SET))
    assert _values(new)[0] == Decimal('26000.00')


def test_set_value_allowed_when_rows_carry_no_price(tmp_path):
    old, new = _value_pair(show_zone_pricing_detail=True)
    ContractServiceLocation.objects.create(contract=new, location_name='Lobby')
    out, _ = _execute(tmp_path, _file(tmp_path, _b(old, new, set_value=SET)))
    assert out.count('[APPLIED]') == 2
    assert _values(new)[0] == Decimal('21000.00')


def test_set_value_on_class_c(tmp_path):
    c = _contract(_company(), status='Sent', value=Decimal('500.00'), total_value=Decimal('500.00'))
    out, _ = _execute(tmp_path, _file(tmp_path, _c(c, set_value={'from': '500.00', 'to': '450.00'})))
    assert '[APPLIED] C' in out
    assert _values(c) == (Decimal('450.00'), Decimal('0.00'), Decimal('450.00'))


@pytest.mark.parametrize('set_value, message', [
    ({'from': '1.00'}, 'exactly'),
    ({'from': '1.00', 'to': '2.00', 'x': 1}, 'exactly'),
    ({'from': 1, 'to': '2.00'}, 'decimal string'),
    ({'from': '1.00', 'to': 'abc'}, 'decimal string'),
    ({'from': '1.00', 'to': '-2.00'}, 'non-negative'),
    ({'from': '1.00', 'to': '2.001'}, 'at most 2 decimals'),
    ({'from': '1.00', 'to': '1.00'}, 'equal'),
    ('2.00', 'exactly'),
])
def test_malformed_set_value(tmp_path, set_value, message):
    entry = _valid_entry()
    entry['set_value'] = set_value
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))


def test_set_value_on_renewed_target_is_malformed(tmp_path):
    entry = _valid_entry()
    entry.update(target_status='Renewed', set_value=SET, expected={**entry['expected'], 'status': 'Active'})
    entry['class'] = 'A'
    with pytest.raises(CommandError, match='Active targets only'):
        _run('--file', _file(tmp_path, [entry]))
