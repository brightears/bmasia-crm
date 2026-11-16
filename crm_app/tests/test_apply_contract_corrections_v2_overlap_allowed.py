"""apply_contract_corrections, file format v2: the optional ``overlap_allowed`` key of
create_successor and create_contract.

A client may hold two separate subscriptions on one company record with different
yearly cycles (one renewing in March, one in May, plus an add-on). The next term of
one cycle then overlaps the other cycle's contracts; ``overlap_allowed`` names those
contracts so the overlap check leaves exactly them out. All data is synthetic; no
test relies on primary-key values.
"""
import json
from datetime import date, timedelta
from unittest import mock

import pytest
from django.core.management.base import CommandError
from django.utils import timezone

from crm_app.models import Contract, ContractServiceLocation
from crm_app.services import contract_corrections_v2 as v2
from crm_app.models import ContractZone
from crm_app.tests.test_apply_contract_corrections_v2 import (
    _audits, _company, _contract, _create, _created_for, _execute, _expected, _file, _reload, _run, _zone_link,
)
from crm_app.tests.test_apply_contract_corrections_v2_ops import _create_new, _created_on, _note

# The March-cycle term the default new term (2026-03-01..2027-02-28) renews.
MARCH_START = date(2025, 3, 1)


def _allow(*contracts):
    return [{'contract_id': str(c.pk), 'expected': _expected(c)} for c in contracts]


def _successor(old, allowed=(), **kwargs):
    entry = _create(old, **kwargs)
    if allowed:
        entry['overlap_allowed'] = _allow(*allowed)
    return entry


def _new_contract(company, allowed=(), **kwargs):
    entry = _create_new(company, **kwargs)
    if allowed:
        entry['overlap_allowed'] = _allow(*allowed)
    return entry


def _march_old(company):
    return _contract(company, status='Expired', start=MARCH_START, is_active=False)


def _may_term(company, status='Active', **extra):
    """A separate subscription renewing every May: 2025-05-01..2026-04-30."""
    return _contract(company, status=status, start=date(2025, 5, 1), is_active=status == 'Active', **extra)


def _state(contract):
    contract.refresh_from_db()
    return (contract.status, contract.is_active, contract.start_date, contract.end_date, contract.updated_at,
            contract.renewed_from_id)


def _span(c):
    c.refresh_from_db()
    return f'{c.contract_number} ({c.status} {c.start_date.isoformat()}..{c.end_date.isoformat()})'


# --- create_successor --------------------------------------------------------------------------

def test_successor_overlap_refused_without_the_option_and_applied_with_it(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old)]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_for(old) is None

    may_before = _state(may)
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])], 'b.json'), 'j2.json')
    assert '[APPLIED] G create_successor' in out
    new = _created_for(old)
    assert (new.status, new.start_date) == ('Active', date(2026, 3, 1))
    old.refresh_from_db()
    assert old.status == 'Renewed'
    assert _state(may) == may_before  # the allowed contract is not touched


def test_successor_with_two_allowed_overlaps(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    addon = _contract(company, status='Active', start=date(2026, 6, 1), end=date(2027, 4, 30))
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[SKIPPED:overlapping_contract]' in out
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may, addon])], 'b.json'), 'j2.json')
    assert '[APPLIED]' in out
    assert _created_for(old) is not None


def test_an_unlisted_overlap_is_still_refused_while_a_listed_one_is_allowed(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    _contract(company, status='Draft', start=date(2026, 9, 1), is_active=False)  # not listed
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_for(old) is None and _state(old)[0] == 'Expired'


def test_a_zone_shared_with_an_allowed_contract_is_refused(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    zone, _ = _zone_link(old)
    ContractZone.objects.create(contract=may, zone=zone, start_date=may.start_date)  # both hold the zone
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[SKIPPED:overlap_allowed_shares_zone]' in out
    assert _created_for(old) is None
    assert ContractZone.objects.filter(zone=zone, is_active=True).count() == 2  # nothing moved


def test_zones_not_shared_with_an_allowed_contract_are_copied(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    _zone_link(old)
    _zone_link(may)  # the allowed contract holds another zone: no conflict
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[APPLIED]' in out
    new = _created_for(old)
    assert ContractZone.objects.filter(contract=new, is_active=True).count() == 1


def test_an_inactive_shared_zone_link_on_the_allowed_contract_is_not_a_conflict(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    zone, _ = _zone_link(old)
    ContractZone.objects.create(contract=may, zone=zone, start_date=may.start_date, is_active=False,
                                end_date=date(2025, 6, 30))
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[APPLIED]' in out


def test_more_than_twenty_allowed_items_stop_the_command(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    entry = _successor(old, [may])
    entry['overlap_allowed'] = entry['overlap_allowed'] + [
        {'contract_id': str(_contract(company, status='Active', start=date(2026, 4, 1)).pk),
         'expected': {'status': 'Active', 'start_date': '2026-04-01', 'end_date': '2027-03-31',
                      'updated_at': timezone.now().isoformat()}} for _ in range(20)]
    with pytest.raises(CommandError, match='want a list of 1-20'):
        _run('--file', _file(tmp_path, [entry]))
    assert _created_for(old) is None


@pytest.mark.parametrize('make', [
    # ends the day before the new term starts
    lambda company: _contract(company, status='Expired', start=date(2025, 2, 1), end=date(2026, 2, 28),
                              is_active=False),
    # starts the day after the new term ends
    lambda company: _contract(company, status='Active', start=date(2027, 3, 1)),
    # overlaps by date, but Cancelled never counts as an overlap
    lambda company: _contract(company, status='Cancelled', start=date(2025, 5, 1), is_active=False),
])
def test_an_allowed_contract_that_does_not_overlap_is_refused(tmp_path, make):
    company = _company()
    old = _march_old(company)
    other = make(company)
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [other])]))
    assert '[SKIPPED:overlap_allowed_not_overlapping]' in out
    assert _created_for(old) is None


def test_an_allowed_contract_of_another_company_is_refused(tmp_path):
    old = _march_old(_company())
    elsewhere = _may_term(_company())
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [elsewhere])]))
    assert '[SKIPPED:overlap_allowed_other_company]' in out
    assert _created_for(old) is None


def test_an_allowed_contract_of_a_twin_company_is_refused(tmp_path):
    company, twin = _company(), _company()
    old = _march_old(company)
    twin_term = _may_term(twin)
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [twin_term], twins=[twin])]))
    assert '[SKIPPED:overlap_allowed_other_company]' in out
    assert _created_for(old) is None


@pytest.mark.parametrize('edit', [
    {'updated_at': timezone.now() + timedelta(seconds=5)},
    {'status': 'Renewed'},
    {'end_date': date(2026, 5, 31)},
    {'start_date': date(2025, 4, 1)},
])
def test_an_allowed_contract_changed_since_the_file_is_refused(tmp_path, edit):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    path = _file(tmp_path, [_successor(old, [may])])
    Contract.objects.filter(pk=may.pk).update(**edit)
    out, _ = _execute(tmp_path, path)
    assert '[SKIPPED:overlap_allowed_changed]' in out
    assert _created_for(old) is None and _state(old)[0] == 'Expired'


def test_a_missing_allowed_contract_is_refused(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    path = _file(tmp_path, [_successor(old, [may])])
    Contract.objects.filter(pk=may.pk).delete()
    out, _ = _execute(tmp_path, path)
    assert '[SKIPPED:overlap_allowed_missing]' in out
    assert _created_for(old) is None


def test_allowed_contracts_are_locked_with_the_group(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    seen = {}
    original = v2.V2Runner._check_group

    def spy(self, members, locked):
        seen['locked'] = set(locked)
        return original(self, members, locked)

    with mock.patch.object(v2.V2Runner, '_check_group', spy):
        out, _ = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert '[APPLIED]' in out
    assert seen['locked'] == {str(old.pk), str(may.pk)}


def test_an_allowed_contract_used_by_another_group_is_refused(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    path = _file(tmp_path, [_successor(old, [may], group='G:1'), _note(may, group='N:1')])
    out, _ = _execute(tmp_path, path)
    assert out.count('[SKIPPED:contract_in_two_groups]') == 2
    assert _created_for(old) is None


def test_an_allowed_contract_changed_by_the_same_group_is_judged_before_the_write(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    path = _file(tmp_path, [_successor(old, [may], group='G:1'), _note(may, group='G:1', cls='G')])
    out, _ = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    assert _created_for(old) is not None


def test_planned_overlap_in_one_group_is_still_refused(tmp_path):
    """Two cycles' successors planned in one group overlap each other: refused, overlap_allowed
    covers existing contracts only."""
    company = _company()
    march, may = _march_old(company), _may_term(company)
    entries = [_successor(march, [may], group='G:1'),
               _create(may, group='G:1', start_date='2026-05-01', end_date='2027-04-30')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert _created_for(march) is None and _created_for(may) is None


def test_creating_the_other_cycle_in_another_group_is_refused(tmp_path):
    """The allowed contract is relied on by G:1, so G:2 may not change it (and the planned terms overlap)."""
    company = _company()
    march, may = _march_old(company), _may_term(company)
    entries = [_successor(march, [may], group='G:1'),
               _create(may, group='G:2', start_date='2026-05-01', end_date='2027-04-30')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:contract_in_two_groups]') == 2
    assert _created_for(march) is None and _created_for(may) is None


# --- output, audit, journal, re-run, revert -------------------------------------------------------

def test_dry_run_names_every_allowed_overlap_and_writes_nothing(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    addon = _contract(company, status='Active', start=date(2026, 6, 1), end=date(2027, 4, 30))
    out = _run('--file', _file(tmp_path, [_successor(old, [may, addon])]))
    assert '[WOULD-APPLY] G create_successor' in out
    assert f'; overlap allowed with {_span(may)}; overlap allowed with {_span(addon)}' in out
    assert _created_for(old) is None and not _audits().exists()


def test_execute_output_audit_row_and_journal_record_the_allowed_overlaps(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    assert f'overlap allowed with {_span(may)}' in out
    new = _created_for(old)
    row = {'contract_id': str(may.pk), 'contract_number': may.contract_number, 'status': 'Active',
           'start_date': '2025-05-01', 'end_date': may.end_date.isoformat()}
    assert _audits(new.pk, 'CREATE').get().additional_data['overlap_allowed'] == [row]
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert op['overlap_allowed'] == [row]


def test_without_the_option_audit_and_journal_have_no_overlap_key(tmp_path):
    old = _march_old(_company())
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_successor(old)]))
    assert '[APPLIED]' in out and 'overlap allowed' not in out
    assert 'overlap_allowed' not in _audits(_created_for(old).pk, 'CREATE').get().additional_data
    assert 'overlap_allowed' not in json.loads(open(journal_path).read())['groups'][0]['ops'][0]


def test_rerun_with_the_option_is_already_applied(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    path = _file(tmp_path, [_successor(old, [may])])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED]' in out
    assert Contract.objects.filter(renewed_from=old).count() == 1


def test_revert_still_deletes_the_created_successor(tmp_path):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    may_before = _state(may)
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_successor(old, [may])]))
    new = _created_for(old)
    out = _run('--revert', journal_path, '--execute')
    assert f'deletes created {new.pk} {new.contract_number}' in out and '[REVERTED]' in out
    assert not Contract.objects.filter(pk=new.pk).exists()
    old.refresh_from_db()
    assert old.status == 'Expired'
    assert _state(may) == may_before


# --- create_contract ---------------------------------------------------------------------------

def test_create_contract_refused_without_the_option_and_applied_with_it(tmp_path):
    company = _company()
    may = _may_term(company)
    out, _ = _execute(tmp_path, _file(tmp_path, [_new_contract(company)]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_on(company) is None

    out, journal_path = _execute(tmp_path, _file(tmp_path, [_new_contract(company, [may])], 'b.json'), 'j2.json')
    assert '[APPLIED] C create_contract' in out and f'overlap allowed with {_span(may)}' in out
    new = _created_on(company)
    assert new is not None and new.renewed_from_id is None
    row = {'contract_id': str(may.pk), 'contract_number': may.contract_number, 'status': 'Active',
           'start_date': '2025-05-01', 'end_date': may.end_date.isoformat()}
    assert _audits(new.pk, 'CREATE').get().additional_data['overlap_allowed'] == [row]
    assert json.loads(open(journal_path).read())['groups'][0]['ops'][0]['overlap_allowed'] == [row]

    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED]' in out
    assert not Contract.objects.filter(pk=new.pk).exists()
    assert not ContractServiceLocation.objects.filter(contract_id=new.pk).exists()


def test_create_contract_unlisted_overlap_still_refused(tmp_path):
    company = _company()
    may = _may_term(company)
    _contract(company, status='Active', start=date(2026, 6, 1), end=date(2027, 4, 30))
    out, _ = _execute(tmp_path, _file(tmp_path, [_new_contract(company, [may])]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_on(company) is None


@pytest.mark.parametrize('case, reason', [
    ('other_company', 'overlap_allowed_other_company'),
    ('changed', 'overlap_allowed_changed'),
    ('not_overlapping', 'overlap_allowed_not_overlapping'),
])
def test_create_contract_allowed_item_refusals(tmp_path, case, reason):
    company = _company()
    if case == 'other_company':
        other = _may_term(_company())
    elif case == 'not_overlapping':
        other = _contract(company, status='Expired', start=date(2025, 1, 1), end=date(2026, 2, 28),
                          is_active=False)
    else:
        other = _may_term(company)
    path = _file(tmp_path, [_new_contract(company, [other])])
    if case == 'changed':
        Contract.objects.filter(pk=other.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
    out, _ = _execute(tmp_path, path)
    assert f'[SKIPPED:{reason}]' in out
    assert _created_on(company) is None


# --- the realistic case ---------------------------------------------------------------------------

def _two_cycle_client():
    """March-cycle old term (Expired), May-cycle term (Renewed), its May renewal (Active) and an
    add-on (Active), all on one company record."""
    company = _company()
    march = _march_old(company)
    may_old = _may_term(company, status='Renewed')
    may_new = _contract(company, status='Active', start=date(2026, 5, 1), renewed_from=may_old)
    addon = _contract(company, status='Active', start=date(2025, 9, 1), end=date(2026, 8, 31))
    return march, may_old, may_new, addon


@pytest.mark.parametrize('leave_out', [0, 1, 2])
def test_two_cycle_client_refused_unless_all_three_overlaps_are_listed(tmp_path, leave_out):
    march, *others = _two_cycle_client()
    listed = [c for n, c in enumerate(others) if n != leave_out]
    out, _ = _execute(tmp_path, _file(tmp_path, [_successor(march, listed)]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_for(march) is None and _state(march)[0] == 'Expired'


def test_two_cycle_client_march_successor_applies_with_all_three_listed(tmp_path):
    march, may_old, may_new, addon = _two_cycle_client()
    before = {c.pk: _state(c) for c in (may_old, may_new, addon)}
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_successor(march, [may_old, may_new, addon])]))
    assert '[APPLIED] G create_successor' in out
    for c in (may_old, may_new, addon):
        assert f'overlap allowed with {_span(c)}' in out
    new = _created_for(march)
    _reload(march)
    assert (march.status, new.status, new.renewed_from_id) == ('Renewed', 'Active', march.pk)
    assert {c.pk: _state(c) for c in (may_old, may_new, addon)} == before
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert [r['contract_id'] for r in op['overlap_allowed']] == [str(may_old.pk), str(may_new.pk), str(addon.pk)]


# --- malformed entries -----------------------------------------------------------------------------

@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(overlap_allowed={'contract_id': e['old_contract_id']}), 'overlap_allowed: want a list'),
    (lambda e: e.update(overlap_allowed='all'), 'overlap_allowed: want a list'),
    (lambda e: e.update(overlap_allowed=[]), 'overlap_allowed: want a list'),
    (lambda e: e['overlap_allowed'][0].pop('expected'), r'overlap_allowed\[0\]: must have exactly'),
    (lambda e: e['overlap_allowed'][0].update(note='x'), r'overlap_allowed\[0\]: must have exactly'),
    (lambda e: e['overlap_allowed'].__setitem__(0, 'not-an-object'), r'overlap_allowed\[0\]: must have exactly'),
    (lambda e: e['overlap_allowed'][0].update(contract_id='abc'), 'contract_id: not a UUID'),
    (lambda e: e['overlap_allowed'][0]['expected'].pop('updated_at'), r'expected: must have exactly'),
    (lambda e: e['overlap_allowed'][0]['expected'].update(status='Gone'), 'not a contract status'),
    (lambda e: e['overlap_allowed'].append(dict(e['overlap_allowed'][0])), 'named twice'),
    (lambda e: e['overlap_allowed'].append({'contract_id': e['old_contract_id'], 'expected': e['old_expected']}),
     'the old contract itself'),
])
def test_malformed_overlap_allowed_stops_the_command(tmp_path, mutate, message):
    company = _company()
    old, may = _march_old(company), _may_term(company)
    entry = _successor(old, [may])
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))
    assert _created_for(old) is None


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(overlap_allowed='all'), 'overlap_allowed: want a list'),
    (lambda e: e['overlap_allowed'][0].pop('expected'), 'must have exactly'),
    (lambda e: e['overlap_allowed'].append(dict(e['overlap_allowed'][0])), 'named twice'),
])
def test_malformed_overlap_allowed_on_create_contract_stops_the_command(tmp_path, mutate, message):
    company = _company()
    entry = _new_contract(company, [_may_term(company)])
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))


@pytest.mark.parametrize('op', ['mark_renewed', 'mark_cancelled'])
def test_overlap_allowed_is_unknown_on_other_ops(tmp_path, op):
    company = _company()
    may = _may_term(company)
    entry = {'op': 'mark_cancelled', 'class': 'D', 'group': 'D:1', 'contract_id': str(may.pk),
             'expected': _expected(may), 'evidence': 'Fixture sheet / Tab / row 3'}
    if op == 'mark_renewed':
        later = _contract(company, status='Active', start=date(2026, 5, 1), renewed_from=may)
        entry.update(op='mark_renewed', successor_id=str(later.pk), successor_expected=_expected(later))
    entry['overlap_allowed'] = _allow(may)
    with pytest.raises(CommandError, match='unknown keys'):
        _run('--file', _file(tmp_path, [entry]))
