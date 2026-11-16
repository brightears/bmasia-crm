"""apply_contract_corrections, file format v2: clear_renewed_from.

Removes a wrong renewed_from link (e.g. an add-on contract linked to the main
term) so the lifecycle rule cannot later close the "predecessor" as Renewed.
Dry-run, execute, refusals, re-run, audit row, journal and --revert, and the
add-on scenario against the REST activation, the v1 activation and the
close_renewed_predecessors backfill. All data is synthetic; no test relies on
primary-key values.
"""
import json
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from crm_app.models import AuditLog, Contract, ContractZone
from crm_app.services import contract_corrections_v2 as v2
from crm_app.tests import test_apply_contract_corrections as v1_tests
from crm_app.tests.test_apply_contract_corrections_v2 import (
    _audits, _company, _contract, _execute, _expected, _file, _reload, _renewed, _run, _zone_link,
)
from crm_app.tests.test_contract_lifecycle import _rest_patch

MAIN_START = timezone.localdate() - timedelta(days=200)


def _clear(contract, current_link, group='L:1', cls='L'):
    return {'op': 'clear_renewed_from', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'renewed_from_id': str(current_link.pk),
            'evidence': 'Fixture sheet / Tab / row 11'}


def _addon_pair(main_status='Active', addon_status='Active'):
    """A main term and an add-on contract wrongly linked to it by renewed_from."""
    company = _company()
    main = _contract(company, status=main_status, start=MAIN_START)
    addon = _contract(company, status=addon_status, start=MAIN_START + timedelta(days=60),
                      end=main.end_date, renewed_from=main)
    return main, addon


def _snapshot(contract):
    contract.refresh_from_db()
    return (contract.status, contract.is_active, contract.start_date, contract.end_date, contract.value,
            contract.total_value, contract.currency, contract.contract_number, contract.notes,
            contract.company_id, contract.lifecycle_type)


def _links(contract):
    return sorted((str(l.zone_id), l.start_date, l.end_date, l.is_active)
                  for l in ContractZone.objects.filter(contract=contract))


def _backfill_dry_run():
    out = StringIO()
    call_command('close_renewed_predecessors', stdout=out)
    return out.getvalue()


@pytest.fixture
def lifecycle_spies():
    """Fail loudly if anything reaches the lifecycle rule or the zone-link hand-over."""
    with mock.patch.object(v2, 'close_renewed_predecessor') as rule, \
            mock.patch('crm_app.services.contract_lifecycle.close_renewed_predecessor') as rule_at_source, \
            mock.patch.object(v2, 'hand_over_zone_links') as hand_over:
        yield rule, rule_at_source, hand_over


# --- dry-run, execute, re-run ------------------------------------------------------------

def test_clear_dry_run_reports_and_writes_nothing(tmp_path):
    main, addon = _addon_pair()
    version = addon.updated_at
    out = _run('--file', _file(tmp_path, [_clear(addon, main)]))
    assert f'[WOULD-APPLY] L clear_renewed_from {addon.pk} {addon.contract_number}: ' in out
    assert f'clear renewed_from (was {main.contract_number}); status stays Active' in out
    addon.refresh_from_db()
    assert (addon.renewed_from_id, addon.updated_at) == (main.pk, version)
    assert not _audits().exists()


def test_clear_execute_removes_only_the_link(tmp_path, lifecycle_spies):
    main, addon = _addon_pair()
    _zone_link(addon)
    _zone_link(main)
    addon_before, main_before = _snapshot(addon), _snapshot(main)
    addon_links, main_links = _links(addon), _links(main)
    addon_version, main_version = addon.updated_at, main.updated_at

    out, journal_path = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    assert f'[APPLIED] L clear_renewed_from {addon.pk} {addon.contract_number}' in out
    _reload(addon, main)
    assert addon.renewed_from_id is None
    assert addon.updated_at > addon_version
    assert _snapshot(addon) == addon_before and _links(addon) == addon_links
    # the former predecessor is not touched at all
    assert _snapshot(main) == main_before and _links(main) == main_links
    assert main.updated_at == main_version
    assert not AuditLog.objects.filter(record_id=str(main.pk)).exists()

    audit = _audits(addon.pk).get()
    assert audit.action == 'UPDATE'
    assert audit.changes == {'renewed_from': {'old': str(main.pk), 'new': None}}
    data = audit.additional_data
    assert (data['op'], data['group'], data['class'], data['evidence']) == (
        'clear_renewed_from', 'L:1', 'L', 'Fixture sheet / Tab / row 11')
    assert data['batch_id'] and data['command'] == 'apply_contract_corrections'
    assert data['former_renewed_from_id'] == str(main.pk)
    assert data['former_renewed_from_contract_number'] == main.contract_number

    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert op['op'] == 'clear_renewed_from' and op['contract_id'] == str(addon.pk)
    assert (op['before']['renewed_from'], op['after']['renewed_from']) == (str(main.pk), None)
    assert op['before']['status'] == op['after']['status'] == 'Active'

    for spy in lifecycle_spies:
        spy.assert_not_called()


def test_clear_rerun_is_already_applied(tmp_path):
    main, addon = _addon_pair()
    path = _file(tmp_path, [_clear(addon, main)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED] L clear_renewed_from' in out
    assert _audits(addon.pk).count() == 1


@pytest.mark.parametrize('status', ['Cancelled', 'Expired', 'Renewed', 'Draft', 'Sent'])
def test_clear_works_for_any_status_and_keeps_it(tmp_path, status):
    main, addon = _addon_pair(addon_status=status)
    out, _ = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    assert '[APPLIED]' in out
    addon.refresh_from_db()
    assert (addon.renewed_from_id, addon.status) == (None, status)


# --- refusals ----------------------------------------------------------------------------

def test_clear_refuses_a_link_to_another_contract(tmp_path):
    main, addon = _addon_pair()
    other = _contract(main.company, status='Expired', start=MAIN_START - timedelta(days=365), is_active=False)
    out, _ = _execute(tmp_path, _file(tmp_path, [_clear(addon, other)]))
    assert '[SKIPPED:renewed_from_differs]' in out
    addon.refresh_from_db()
    assert addon.renewed_from_id == main.pk
    assert not _audits().exists()


def test_clear_refuses_a_contract_without_link(tmp_path):
    main, _ = _addon_pair()
    unlinked = _contract(main.company, status='Active', start=MAIN_START + timedelta(days=90))
    version = unlinked.updated_at
    out, _ = _execute(tmp_path, _file(tmp_path, [_clear(unlinked, main)]))
    assert '[SKIPPED:no_renewed_from]' in out
    unlinked.refresh_from_db()
    assert unlinked.updated_at == version
    assert not _audits().exists()


@pytest.mark.parametrize('edit, reason', [
    ({'updated_at': timezone.now() + timedelta(seconds=5)}, 'updated_at_changed'),
    ({'status': 'Expired'}, 'status_changed'),
    ({'end_date': MAIN_START + timedelta(days=500)}, 'dates_changed'),
])
def test_clear_refuses_a_contract_changed_since_the_file(tmp_path, edit, reason):
    main, addon = _addon_pair()
    path = _file(tmp_path, [_clear(addon, main)])
    Contract.objects.filter(pk=addon.pk).update(**edit)
    out, _ = _execute(tmp_path, path)
    assert f'[SKIPPED:{reason}]' in out
    addon.refresh_from_db()
    assert addon.renewed_from_id == main.pk


def test_clear_refuses_the_same_contract_twice_in_a_file(tmp_path):
    main, addon = _addon_pair()
    path = _file(tmp_path, [_clear(addon, main, group='L:1'), _clear(addon, main, group='L:2')])
    out, _ = _execute(tmp_path, path)
    assert out.count('[SKIPPED:duplicate_contract_id]') == 2
    addon.refresh_from_db()
    assert addon.renewed_from_id == main.pk


def test_clear_refuses_a_group_that_uses_the_contract_as_successor(tmp_path):
    main, addon = _addon_pair()
    path = _file(tmp_path, [_clear(addon, main, group='L:1'), _renewed(main, addon, group='L:1', cls='L')])
    out, _ = _execute(tmp_path, path)
    assert out.count('[SKIPPED:successor_link_cleared]') == 2
    _reload(main, addon)
    assert (main.status, addon.renewed_from_id) == ('Active', main.pk)


def test_clear_in_one_group_and_successor_in_another_is_refused(tmp_path):
    main, addon = _addon_pair()
    path = _file(tmp_path, [_clear(addon, main, group='L:1'), _renewed(main, addon, group='E:1')])
    out, _ = _execute(tmp_path, path)
    assert out.count('[SKIPPED:contract_in_two_groups]') == 2


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.pop('renewed_from_id'), 'missing keys'),
    (lambda e: e.pop('expected'), 'missing keys'),
    (lambda e: e.update(renewed_from_id='not-a-uuid'), 'renewed_from_id: not a UUID'),
    (lambda e: e.update(renewed_from_id=e['contract_id']), 'cannot reference itself'),
    (lambda e: e.update(renewed_from_expected=e['expected']), 'unknown keys'),
    (lambda e: e['expected'].pop('updated_at'), 'must have exactly'),
])
def test_clear_malformed_entry_stops_the_command(tmp_path, mutate, message):
    main, addon = _addon_pair()
    entry = _clear(addon, main)
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))
    addon.refresh_from_db()
    assert addon.renewed_from_id == main.pk


# --- revert ------------------------------------------------------------------------------

def test_clear_revert_restores_the_link(tmp_path, lifecycle_spies):
    main, addon = _addon_pair()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    addon_before, main_before = _snapshot(addon), _snapshot(main)
    assert '[WOULD-REVERT] L clear_renewed_from' in _run('--revert', journal_path)
    addon.refresh_from_db()
    assert addon.renewed_from_id is None

    out = _run('--revert', journal_path, '--execute')
    assert f'[REVERTED] L clear_renewed_from {addon.pk}' in out
    assert f'renewed_from restored to {main.pk}' in out
    _reload(addon, main)
    assert addon.renewed_from_id == main.pk
    assert _snapshot(addon) == addon_before and _snapshot(main) == main_before
    revert_audit = _audits(addon.pk).filter(additional_data__mode='revert').get()
    assert revert_audit.changes == {'renewed_from': {'old': None, 'new': str(main.pk)}}
    assert revert_audit.additional_data['op'] == 'clear_renewed_from'
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')
    for spy in lifecycle_spies:
        spy.assert_not_called()


@pytest.mark.parametrize('edit', [
    lambda addon, main: Contract.objects.filter(pk=addon.pk).update(updated_at=timezone.now() + timedelta(seconds=5)),
    lambda addon, main: Contract.objects.filter(pk=addon.pk).update(status='Expired'),  # updated_at left as it is
    lambda addon, main: Contract.objects.filter(pk=addon.pk).update(  # linked elsewhere, updated_at left as it is
        renewed_from=_contract(main.company, status='Expired', start=MAIN_START - timedelta(days=365))),
])
def test_clear_revert_is_skipped_when_the_contract_changed_since(tmp_path, edit):
    main, addon = _addon_pair()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    edit(addon, main)
    addon.refresh_from_db()
    state = (addon.status, addon.renewed_from_id, addon.updated_at)
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    addon.refresh_from_db()
    assert (addon.status, addon.renewed_from_id, addon.updated_at) == state


def test_clear_revert_is_skipped_when_the_former_predecessor_is_gone(tmp_path):
    main, addon = _addon_pair()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    Contract.objects.filter(pk=main.pk).delete()
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    addon.refresh_from_db()
    assert addon.renewed_from_id is None


# --- the add-on scenario -------------------------------------------------------------------

def _activate_rest(contract):
    response = _rest_patch(contract, {'status': 'Active'})
    assert response.status_code == 200, response.data


def _activate_v1(contract, tmp_path):
    path = v1_tests._file(tmp_path, v1_tests._c(contract), 'v1.json')
    out, _ = v1_tests._execute(tmp_path, path, 'v1-journal.json')
    assert '[APPLIED]' in out, out


@pytest.mark.parametrize('activate', ['rest', 'v1'])
def test_addon_linked_to_main_term_control_without_clear(tmp_path, activate):
    """Without the correction, the wrong link makes the backfill close the main term."""
    main, addon = _addon_pair(main_status='Sent')
    _activate_rest(main) if activate == 'rest' else _activate_v1(main, tmp_path)
    main.refresh_from_db()
    assert main.status == 'Active'
    assert f'[WOULD-CLOSE] Active -> Renewed: {main.contract_number}' in _backfill_dry_run()


@pytest.mark.parametrize('activate', ['rest', 'v1'])
def test_addon_link_cleared_then_main_term_activated_stays_active(tmp_path, activate):
    main, addon = _addon_pair(main_status='Sent')
    out, _ = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    assert '[APPLIED]' in out
    _activate_rest(main) if activate == 'rest' else _activate_v1(main, tmp_path)
    _reload(main, addon)
    assert (main.status, main.is_active) == ('Active', True)
    assert (addon.status, addon.renewed_from_id) == ('Active', None)
    backfill = _backfill_dry_run()
    assert main.contract_number not in backfill
    assert 'would_close=0' in backfill


def test_pending_addon_activated_after_clear_does_not_close_the_main_term(tmp_path):
    main, addon = _addon_pair(main_status='Active', addon_status='Sent')
    _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    _activate_rest(addon)
    _reload(main, addon)
    assert (addon.status, main.status, main.is_active) == ('Active', 'Active', True)


def test_pending_addon_activated_without_clear_closes_the_main_term():
    """Control for the test above: the danger the op removes."""
    main, addon = _addon_pair(main_status='Active', addon_status='Sent')
    _activate_rest(addon)
    main.refresh_from_db()
    assert main.status == 'Renewed'


def test_clear_and_an_op_on_the_former_predecessor_in_another_group(tmp_path):
    """The former predecessor is not one of the entry's contracts: another group may act on it.
    Its checks see the link in a dry-run and see it gone on --execute (groups run in file order)."""
    today = timezone.localdate()
    company = _company()
    main = _contract(company, status='Active', start=today - timedelta(days=400), end=today - timedelta(days=35))
    addon = _contract(company, status='Active', start=main.start_date, end=main.end_date, renewed_from=main)
    expire = {'op': 'mark_expired', 'class': 'X', 'group': 'X:1', 'contract_id': str(main.pk),
              'expected': _expected(main), 'evidence': 'Fixture sheet / Tab / row 12'}
    path = _file(tmp_path, [_clear(addon, main), expire])
    dry = _run('--file', path)
    assert '[WOULD-APPLY] L clear_renewed_from' in dry and '[SKIPPED:renewal_exists] X mark_expired' in dry
    out, _ = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    _reload(main, addon)
    assert (main.status, addon.renewed_from_id, addon.status) == ('Expired', None, 'Active')


# --- review follow-up ----------------------------------------------------------------------

def test_clear_never_calls_contract_save(tmp_path):
    """The link is removed with a queryset update: Contract.save() (number minting, signals,
    the post_save handlers) must not run for the cleared contract, nor for any other."""
    main, addon = _addon_pair()
    with mock.patch.object(Contract, 'save', autospec=True, side_effect=Contract.save) as save_spy:
        out, _ = _execute(tmp_path, _file(tmp_path, [_clear(addon, main)]))
    assert f'[APPLIED] L clear_renewed_from {addon.pk}' in out
    addon.refresh_from_db()
    assert addon.renewed_from_id is None
    assert [call for call in save_spy.call_args_list if call.args[0].pk == addon.pk] == []
    save_spy.assert_not_called()
