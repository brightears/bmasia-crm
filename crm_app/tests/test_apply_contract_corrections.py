"""apply_contract_corrections: reviewed status corrections applied per group.

Covers dry-run and execute for classes A/B/C, group atomicity, every refusal
reason, idempotent re-runs, Draft activation parity with the REST path,
set_renewed_from, signed_date, audit rows, the revert journal and --revert,
and that nothing emails or calls out. All data is synthetic.
"""
import json
from datetime import date, timedelta, timedelta as td, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
from unittest import mock

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone as dj_timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.management.commands import apply_contract_corrections as cmd
from crm_app.models import AuditLog, Company, Contract, User
from crm_app.services import contract_lifecycle
from crm_app.views import ContractViewSet

_numbers = iter(range(1, 100_000))
TODAY_START = date(2025, 11, 1)


# --- fixtures ------------------------------------------------------------------

def _company():
    return Company.objects.create(name=f'Corrections fixture company {next(_numbers)}',
                                  billing_entity='BMAsia Limited')


def _contract(company, status='Active', start=TODAY_START, renewed_from=None, number=None, **extra):
    values = dict(
        company=company, contract_number=number or f'TEST-CT-{next(_numbers):05d}',
        status=status, start_date=start, end_date=start + timedelta(days=364),
        value=Decimal('1200.00'), total_value=Decimal('1200.00'),
        is_active=True, renewed_from=renewed_from,
    )
    values.update(extra)
    return Contract.objects.create(**values)


def _pair(successor_status='Sent', linked=True, **successor_extra):
    company = _company()
    old = _contract(company, status='Active')
    new = _contract(company, status=successor_status, start=date(2026, 11, 1),
                    renewed_from=old if linked else None, **successor_extra)
    return old, new


def _entry(contract, cls, group, target, **extra):
    contract.refresh_from_db()
    entry = {
        'contract_id': str(contract.pk),
        'class': cls,
        'group': group,
        'expected': {
            'status': contract.status,
            'start_date': contract.start_date.isoformat(),
            'end_date': contract.end_date.isoformat() if contract.end_date else None,
            'updated_at': contract.updated_at.isoformat(),
        },
        'target_status': target,
        'evidence': 'Fixture sheet / Tab / row 7',
    }
    entry.update(extra)
    return entry


def _a(old, group='A:1', **extra):
    return [_entry(old, 'A', group, 'Renewed', **extra)]


def _b(old, new, group='B:1', **succ_extra):
    return [_entry(new, 'B', group, 'Active', **succ_extra), _entry(old, 'B', group, 'Renewed')]


def _c(contract, group='C:1', **extra):
    return [_entry(contract, 'C', group, 'Active', **extra)]


def _file(tmp_path, entries, name='corrections.json'):
    path = tmp_path / name
    path.write_text(json.dumps({'format': cmd.FILE_FORMAT, 'entries': entries}))
    return str(path)


def _run(*args):
    out = StringIO()
    call_command('apply_contract_corrections', *args, stdout=out)
    return out.getvalue()


def _execute(tmp_path, path, journal='journal.json', *extra):
    journal_path = str(tmp_path / journal)
    return _run('--file', path, '--execute', '--journal', journal_path, *extra), journal_path


def _command_audits(contract=None):
    qs = AuditLog.objects.filter(model_name='Contract', additional_data__command=cmd.COMMAND)
    if contract is not None:
        qs = qs.filter(record_id=str(contract.pk))
    return qs


def _status(contract):
    contract.refresh_from_db()
    return contract.status


def _a_case():
    company = _company()
    old = _contract(company, status='Active')
    _contract(company, status='Active', start=date(2026, 11, 1), renewed_from=old)
    return old


# --- dry run and execute per class -------------------------------------------------

def test_dry_run_reports_each_class_and_writes_nothing(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair()
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _b(b_old, b_new) + _c(c))
    versions = {x.pk: x.updated_at for x in (a_old, b_old, b_new, c)}

    out = _run('--file', path)

    assert 'DRY-RUN' in out
    assert out.count('[WOULD-APPLY]') == 4
    assert '  A: would_apply=1' in out
    assert '  B: would_apply=2' in out
    assert '  C: would_apply=1' in out
    for x in (a_old, b_old, b_new, c):
        x.refresh_from_db()
        assert x.updated_at == versions[x.pk]
    assert (_status(a_old), _status(b_old), _status(b_new), _status(c)) == ('Active', 'Active', 'Sent', 'Sent')
    assert not AuditLog.objects.exists()


def test_execute_applies_each_class_with_one_audit_row_per_contract(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair()
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _b(b_old, b_new) + _c(c))

    out, journal_path = _execute(tmp_path, path)

    assert out.count('[APPLIED]') == 4
    assert '  A: applied=1' in out and '  B: applied=2' in out and '  C: applied=1' in out
    for old in (a_old, b_old):
        old.refresh_from_db()
        assert (old.status, old.is_active) == ('Renewed', False)
    assert _status(b_new) == 'Active' and _status(c) == 'Active'

    batch_ids = set()
    for contract, cls, group in ((a_old, 'A', 'A:1'), (b_old, 'B', 'B:1'), (b_new, 'B', 'B:1'), (c, 'C', 'C:1')):
        rows = list(AuditLog.objects.filter(model_name='Contract', record_id=str(contract.pk), action='UPDATE'))
        assert len(rows) == 1, contract
        data = rows[0].additional_data
        assert data['command'] == cmd.COMMAND
        assert (data['group'], data['class']) == (group, cls)
        assert data['evidence'] == 'Fixture sheet / Tab / row 7'
        batch_ids.add(data['batch_id'])
    assert len(batch_ids) == 1
    assert batch_ids.pop() in out

    # Old terms: closed by the lifecycle rule, real before/after values.
    for old in (a_old, b_old):
        row = _command_audits(old).get()
        assert row.changes == {'status': {'old': 'Active', 'new': 'Renewed'},
                               'is_active': {'old': True, 'new': False}}
        assert row.additional_data['rule'] == 'renewed_predecessor_closed_on_successor_active'
        assert row.additional_data['source'] == cmd.COMMAND
    assert _command_audits(c).get().changes == {'status': {'old': 'Sent', 'new': 'Active'}}


def test_only_class_applies_one_class(tmp_path):
    a_old = _a_case()
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _c(c))

    out, _ = _execute(tmp_path, path, 'journal.json', '--only-class', 'C')

    assert _status(c) == 'Active'
    assert _status(a_old) == 'Active'
    assert 'not selected by --only-class: 1 entries' in out


def test_lifecycle_rule_fires_exactly_once_per_group(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair()
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _b(b_old, b_new) + _c(c))

    with mock.patch.object(cmd, 'close_renewed_predecessor',
                           wraps=contract_lifecycle.close_renewed_predecessor) as spy:
        _execute(tmp_path, path)

    called_for = sorted(str(call.args[0].pk) for call in spy.call_args_list)
    successor_of_a = Contract.objects.get(renewed_from=a_old)
    assert called_for == sorted([str(successor_of_a.pk), str(b_new.pk), str(c.pk)])


def test_expected_updated_at_compared_as_instant(tmp_path):
    c = _contract(_company(), status='Sent')
    entries = _c(c)
    c.refresh_from_db()
    entries[0]['expected']['updated_at'] = c.updated_at.astimezone(dt_timezone(td(hours=7))).isoformat()
    _execute(tmp_path, _file(tmp_path, entries))
    assert _status(c) == 'Active'


# --- atomicity ---------------------------------------------------------------

def test_group_refused_when_second_line_is_stale(tmp_path):
    old, new = _pair()
    entries = _b(old, new)
    Contract.objects.filter(pk=old.pk).update(notes='edited elsewhere', updated_at=old.updated_at + td(seconds=5))

    out, _ = _execute(tmp_path, _file(tmp_path, entries))

    assert out.count('[SKIPPED:updated_at_changed]') == 2
    assert _status(new) == 'Sent' and _status(old) == 'Active'
    assert not AuditLog.objects.exists()


def test_failure_after_first_write_rolls_back_whole_group(tmp_path):
    old, new = _pair(successor_status='Draft', number='DRAFT-0901')
    path = _file(tmp_path, _b(old, new))
    not_closed = contract_lifecycle.PredecessorClosure(
        contract_lifecycle.PREDECESSOR_NOT_ACTIVE, successor_id=str(new.pk))

    with mock.patch.object(cmd, 'close_renewed_predecessor', return_value=not_closed):
        out, journal_path = _execute(tmp_path, path)

    assert 'SKIPPED:rule_did_not_close_old_term(predecessor_not_active)' in out
    new.refresh_from_db()
    assert (new.status, new.contract_number) == ('Draft', 'DRAFT-0901')
    assert _status(old) == 'Active'
    assert not AuditLog.objects.exists()
    assert json.load(open(journal_path))['groups'] == []


# --- refusals ------------------------------------------------------------------

def _refusal(tmp_path, entries):
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    return out


def test_refuses_missing_contract(tmp_path):
    c = _contract(_company(), status='Sent')
    entries = _c(c)
    entries[0]['contract_id'] = '00000000-0000-4000-8000-000000000001'
    assert '[SKIPPED:missing_contract]' in _refusal(tmp_path, entries)


def test_refuses_status_changed(tmp_path):
    c = _contract(_company(), status='Sent')
    entries = _c(c)
    Contract.objects.filter(pk=c.pk).update(status='Cancelled')
    assert '[SKIPPED:status_changed]' in _refusal(tmp_path, entries)
    assert _status(c) == 'Cancelled'


@pytest.mark.parametrize('field', ['start_date', 'end_date'])
def test_refuses_dates_changed(tmp_path, field):
    c = _contract(_company(), status='Sent')
    entries = _c(c)
    Contract.objects.filter(pk=c.pk).update(**{field: getattr(c, field) + td(days=1)})
    assert '[SKIPPED:dates_changed]' in _refusal(tmp_path, entries)
    assert _status(c) == 'Sent'


def test_refuses_updated_at_changed(tmp_path):
    c = _contract(_company(), status='Sent')
    entries = _c(c)
    c.notes = 'touched'
    c.save()
    assert '[SKIPPED:updated_at_changed]' in _refusal(tmp_path, entries)
    assert _status(c) == 'Sent'


@pytest.mark.parametrize('status', ['Expired', 'Cancelled', 'Renewed'])
def test_refuses_transition_not_allowed(tmp_path, status):
    c = _contract(_company(), status=status)
    assert '[SKIPPED:transition_not_allowed]' in _refusal(tmp_path, _c(c))
    assert _status(c) == status


def test_refuses_pair_on_different_companies(tmp_path):
    old = _contract(_company(), status='Active')
    new = _contract(_company(), status='Sent', renewed_from=old, start=date(2026, 11, 1))
    out = _refusal(tmp_path, _b(old, new))
    assert out.count('[SKIPPED:different_companies]') == 2
    assert _status(new) == 'Sent' and _status(old) == 'Active'


def test_refuses_duplicate_contract_id_in_both_groups(tmp_path):
    c = _contract(_company(), status='Sent')
    out = _refusal(tmp_path, _c(c, group='C:1') + _c(c, group='C:2'))
    assert out.count('[SKIPPED:duplicate_contract_id]') == 2
    assert _status(c) == 'Sent'


def test_refuses_existing_different_renewed_from(tmp_path):
    company = _company()
    old = _contract(company, status='Active')
    other = _contract(company, status='Expired', start=date(2024, 11, 1))
    new = _contract(company, status='Sent', renewed_from=other, start=date(2026, 11, 1))
    out = _refusal(tmp_path, _b(old, new, set_renewed_from=str(old.pk)))
    assert out.count('[SKIPPED:renewed_from_conflict]') == 2
    new.refresh_from_db()
    assert new.renewed_from_id == other.pk and new.status == 'Sent'


def test_refuses_pair_linked_elsewhere_without_set_renewed_from(tmp_path):
    company = _company()
    old = _contract(company, status='Active')
    other = _contract(company, status='Expired', start=date(2024, 11, 1))
    new = _contract(company, status='Sent', renewed_from=other, start=date(2026, 11, 1))
    assert '[SKIPPED:renewed_from_conflict]' in _refusal(tmp_path, _b(old, new))


def test_refuses_unlinked_pair_without_set_renewed_from(tmp_path):
    old, new = _pair(linked=False)
    out = _refusal(tmp_path, _b(old, new))
    assert out.count('[SKIPPED:pair_not_linked]') == 2
    assert _status(new) == 'Sent'


def test_refuses_activation_that_would_close_contract_outside_file(tmp_path):
    old, new = _pair()
    out = _refusal(tmp_path, _c(new))
    assert '[SKIPPED:would_close_contract_outside_file]' in out
    assert _status(new) == 'Sent' and _status(old) == 'Active'


def test_refuses_mark_renewed_without_active_successor(tmp_path):
    company = _company()
    old = _contract(company, status='Active')
    _contract(company, status='Sent', renewed_from=old, start=date(2026, 11, 1))
    assert '[SKIPPED:no_active_successor]' in _refusal(tmp_path, _a(old))
    assert _status(old) == 'Active'


def test_refuses_partially_applied_group(tmp_path):
    old, new = _pair(linked=False)
    entries = _b(old, new)
    # Successor went Active elsewhere without a link; the old term is untouched.
    Contract.objects.filter(pk=new.pk).update(status='Active')
    out = _refusal(tmp_path, entries)
    assert out.count('[SKIPPED:partially_applied]') == 2
    assert _status(old) == 'Active'


# --- idempotency ------------------------------------------------------------------

def test_rerun_after_execute_is_already_applied(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair()
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _b(b_old, b_new) + _c(c))
    _execute(tmp_path, path, 'journal-1.json')
    audit_count = AuditLog.objects.count()

    dry = _run('--file', path)
    out, journal_path = _execute(tmp_path, path, 'journal-2.json')

    for text in (dry, out):
        assert text.count('[ALREADY-APPLIED]') == 4
        assert 'SKIPPED' not in text
    assert '  B: already_applied=2' in out
    assert AuditLog.objects.count() == audit_count
    assert json.load(open(journal_path))['groups'] == []


# --- Draft successor parity with a normal activation ------------------------------

def test_draft_successor_gets_same_treatment_as_rest_activation(tmp_path):
    old, new = _pair(successor_status='Draft', number='DRAFT-0901')
    twin_old, twin_new = _pair(successor_status='Draft', number='DRAFT-0902')

    out, _ = _execute(tmp_path, _file(tmp_path, _b(old, new)))
    user = User.objects.create_user(username=f'corrections-rest-{next(_numbers)}', role='Sales')
    request = APIRequestFactory().patch(f'/api/v1/contracts/{twin_new.pk}/', {'status': 'Active'}, format='json')
    force_authenticate(request, user=user)
    response = ContractViewSet.as_view({'patch': 'partial_update'})(request, pk=str(twin_new.pk))
    assert response.status_code == 200, response.data

    for x in (old, new, twin_old, twin_new):
        x.refresh_from_db()
    fields = ('status', 'is_active', 'sent_date', 'signed_date', 'renewed_from_id')
    assert [getattr(new, f) for f in fields[:-1]] == [getattr(twin_new, f) for f in fields[:-1]]
    assert (new.status, new.sent_date, new.renewed_from_id) == ('Active', None, old.pk)
    assert [getattr(old, f) for f in fields] == [getattr(twin_old, f) for f in fields]
    assert (old.status, old.is_active) == ('Renewed', False)
    # Final number from the same sequence and format as the REST path.
    assert new.contract_number[:5] == twin_new.contract_number[:5] == 'HK-CT'
    assert new.contract_number != twin_new.contract_number
    assert 'final number reserved (was DRAFT-0901)' not in out  # execute reports the change itself
    assert f'contract_number DRAFT-0901 -> {new.contract_number}' in out
    assert _command_audits(new).get().changes['contract_number'] == {'old': 'DRAFT-0901', 'new': new.contract_number}


def test_draft_number_reservation_skips_numbers_already_taken(tmp_path):
    from crm_app.models import DocumentSequence
    old, new = _pair(successor_status='Draft', number='DRAFT-0903')
    year = dj_timezone.now().strftime('%y')
    DocumentSequence.objects.update_or_create(region='HK', doc_type='CT', year=year,
                                              defaults={'next_sequence': 501})
    _contract(old.company, status='Expired', number=f'HK-CT{year}501', start=date(2023, 11, 1))

    _execute(tmp_path, _file(tmp_path, _b(old, new)))

    new.refresh_from_db()
    assert new.status == 'Active'
    assert new.contract_number == f'HK-CT{year}502'


def test_dry_run_mentions_number_reservation_without_minting(tmp_path):
    old, new = _pair(successor_status='Draft', number='DRAFT-0904')
    out = _run('--file', _file(tmp_path, _b(old, new)))
    assert 'final number reserved (was DRAFT-0904)' in out
    new.refresh_from_db()
    assert new.contract_number == 'DRAFT-0904'


# --- set_renewed_from and signed_date ---------------------------------------------

def test_set_renewed_from_links_unlinked_pair_and_closes_old_term(tmp_path):
    old, new = _pair(linked=False)
    out, journal_path = _execute(tmp_path, _file(tmp_path, _b(old, new, set_renewed_from=str(old.pk))))

    new.refresh_from_db()
    assert (new.status, new.renewed_from_id) == ('Active', old.pk)
    assert _status(old) == 'Renewed'
    changes = _command_audits(new).get().changes
    assert changes['renewed_from'] == {'old': None, 'new': str(old.pk)}
    journal = json.load(open(journal_path))
    succ_row = next(r for r in journal['groups'][0]['contracts'] if r['contract_id'] == str(new.pk))
    assert succ_row['before']['renewed_from'] is None
    assert succ_row['after']['renewed_from'] == str(old.pk)


def test_set_renewed_from_already_present_is_a_no_op_link(tmp_path):
    old, new = _pair(linked=True)
    _execute(tmp_path, _file(tmp_path, _b(old, new, set_renewed_from=str(old.pk))))
    assert 'renewed_from' not in _command_audits(new).get().changes
    assert _status(old) == 'Renewed'


def test_signed_date_set_when_empty(tmp_path):
    c = _contract(_company(), status='Sent')
    _execute(tmp_path, _file(tmp_path, _c(c, signed_date='2026-10-20')))
    c.refresh_from_db()
    assert c.signed_date == date(2026, 10, 20)
    assert _command_audits(c).get().changes['signed_date'] == {'old': None, 'new': '2026-10-20'}


def test_signed_date_not_overwritten(tmp_path):
    c = _contract(_company(), status='Sent', signed_date=date(2026, 10, 1))
    dry = _run('--file', _file(tmp_path, _c(c, signed_date='2026-10-20')))
    assert 'signed_date kept (already set, differs from file)' in dry
    _execute(tmp_path, _file(tmp_path, _c(c, signed_date='2026-10-20'), name='again.json'))
    c.refresh_from_db()
    assert (c.status, c.signed_date) == ('Active', date(2026, 10, 1))
    assert 'signed_date' not in _command_audits(c).get().changes


# --- actor -------------------------------------------------------------------------

def test_actor_is_recorded_and_unknown_actor_refused(tmp_path):
    user = User.objects.create_user(username='corrections-operator', role='Admin')
    old, new = _pair()
    path = _file(tmp_path, _b(old, new))
    with pytest.raises(CommandError, match='unknown --actor'):
        _execute(tmp_path, path, 'journal-x.json', '--actor', 'nobody-by-this-name')
    assert _status(new) == 'Sent'

    _execute(tmp_path, path, 'journal.json', '--actor', 'corrections-operator')
    assert {row.user_id for row in _command_audits()} == {user.pk}
    assert json.load(open(tmp_path / 'journal.json'))['actor'] == 'corrections-operator'


# --- journal and revert ----------------------------------------------------------

def test_journal_records_before_and_after_of_touched_fields(tmp_path):
    old, new = _pair(successor_status='Draft', number='DRAFT-0905')
    out, journal_path = _execute(tmp_path, _file(tmp_path, _b(old, new, signed_date='2026-10-20')))
    journal = json.load(open(journal_path))

    assert journal['format'] == cmd.JOURNAL_FORMAT
    assert journal['batch_id'] in out
    [group] = journal['groups']
    assert (group['group'], group['class']) == ('B:1', 'B')
    rows = {r['contract_id']: r for r in group['contracts']}
    new.refresh_from_db()
    old.refresh_from_db()
    assert rows[str(new.pk)]['before'] == {
        'status': 'Draft', 'contract_number': 'DRAFT-0905', 'signed_date': None,
        'updated_at': rows[str(new.pk)]['before']['updated_at'],
    }
    assert rows[str(new.pk)]['after'] == {
        'status': 'Active', 'contract_number': new.contract_number, 'signed_date': '2026-10-20',
        'updated_at': new.updated_at.isoformat(),
    }
    assert rows[str(old.pk)]['before']['status'] == 'Active'
    assert rows[str(old.pk)]['after'] == {'status': 'Renewed', 'is_active': False,
                                          'updated_at': old.updated_at.isoformat()}


def test_execute_requires_new_journal(tmp_path):
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _c(c))
    with pytest.raises(CommandError, match='requires --journal'):
        _run('--file', path, '--execute')
    existing = tmp_path / 'exists.json'
    existing.write_text('{}')
    with pytest.raises(CommandError, match='already exists'):
        _run('--file', path, '--execute', '--journal', str(existing))
    assert _status(c) == 'Sent'


def test_revert_restores_and_reports(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair(successor_status='Draft', number='DRAFT-0906')
    c = _contract(_company(), status='Sent')
    _, journal_path = _execute(tmp_path, _file(tmp_path, _a(a_old) + _b(b_old, b_new, signed_date='2026-10-20') + _c(c)))
    b_new.refresh_from_db()
    minted = b_new.contract_number

    dry = _run('--revert', journal_path)
    assert dry.count('[WOULD-REVERT]') == 4
    assert _status(b_new) == 'Active'

    out = _run('--revert', journal_path, '--execute')
    assert out.count('[REVERTED]') == 4
    assert f'final number {minted} kept' in out
    for x in (a_old, b_old):
        x.refresh_from_db()
        assert (x.status, x.is_active) == ('Active', True)
    b_new.refresh_from_db()
    assert (b_new.status, b_new.signed_date, b_new.contract_number) == ('Draft', None, minted)
    assert _status(c) == 'Sent'
    reverts = AuditLog.objects.filter(additional_data__mode='revert')
    assert reverts.count() == 4
    assert {r.additional_data['reverted_batch_id'] for r in reverts} == {json.load(open(journal_path))['batch_id']}

    again = _run('--revert', journal_path, '--execute')
    assert again.count('[ALREADY-REVERTED]') == 4
    assert AuditLog.objects.filter(additional_data__mode='revert').count() == 4


def test_revert_skips_group_changed_since_apply(tmp_path):
    b_old, b_new = _pair()
    c = _contract(_company(), status='Sent')
    _, journal_path = _execute(tmp_path, _file(tmp_path, _b(b_old, b_new) + _c(c)))
    b_new.refresh_from_db()
    b_new.notes = 'edited after the correction'
    b_new.save()

    out = _run('--revert', journal_path, '--execute')

    assert out.count('[SKIPPED:changed_since_apply]') == 2
    assert out.count('[REVERTED]') == 1
    assert _status(b_new) == 'Active' and _status(b_old) == 'Renewed'  # whole group kept
    assert _status(c) == 'Sent'


# --- no email, no external call ------------------------------------------------------

def test_no_email_and_no_external_call(tmp_path):
    a_old = _a_case()
    b_old, b_new = _pair(successor_status='Draft', number='DRAFT-0907')
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, _a(a_old) + _b(b_old, b_new) + _c(c))

    def no_network(*args, **kwargs):
        raise AssertionError('external call attempted')

    with mock.patch('crm_app.services.soundtrack_api.SoundtrackAPIService.sync_company_zones') as sync_zones, \
            mock.patch('crm_app.models.Zone.mark_as_cancelled') as cancel_zone, \
            mock.patch('crm_app.services.email_service.EmailService.send_email', side_effect=no_network), \
            mock.patch('requests.sessions.Session.request', side_effect=no_network), \
            mock.patch('urllib.request.urlopen', side_effect=no_network), \
            mock.patch('smtplib.SMTP', side_effect=no_network), \
            mock.patch('smtplib.SMTP_SSL', side_effect=no_network):
        _execute(tmp_path, path)
        journal = str(tmp_path / 'journal.json')
        _run('--revert', journal, '--execute')

    assert mail.outbox == []
    sync_zones.assert_not_called()
    cancel_zone.assert_not_called()


# --- malformed files -------------------------------------------------------------------

def _valid_entry():
    return {
        'contract_id': '00000000-0000-4000-8000-0000000000aa', 'class': 'C', 'group': 'C:1',
        'expected': {'status': 'Sent', 'start_date': '2026-01-01', 'end_date': None,
                     'updated_at': '2026-01-01T00:00:00+07:00'},
        'target_status': 'Active', 'evidence': 'Sheet / Tab / row 1',
    }


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(company='x'), 'unknown keys'),
    (lambda e: e.pop('evidence'), 'missing keys'),
    (lambda e: e.update(target_status='Expired'), 'target_status'),
    (lambda e: e.update(contract_id='not-a-uuid'), 'not a UUID'),
    (lambda e: e.update({'class': 'D'}), 'class must be'),
    (lambda e: e.update({'class': 'B'}), 'needs target'),
    (lambda e: e['expected'].update(updated_at='2026-01-01T00:00:00'), 'no UTC offset'),
    (lambda e: e['expected'].update(start_date='01/02/2026'), 'YYYY-MM-DD'),
    (lambda e: e['expected'].update(status='Pending'), 'not a contract status'),
    (lambda e: e.update(signed_date='2026-13-01'), 'YYYY-MM-DD'),
    (lambda e: e.update(set_renewed_from='00000000-0000-4000-8000-0000000000bb'), 'set_renewed_from'),
    (lambda e: e.update(evidence='line one\nline two'), 'evidence'),
    (lambda e: e.update(group='has space'), 'group must match'),
])
def test_malformed_entry_exits_non_zero(tmp_path, mutate, message):
    entry = _valid_entry()
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))


@pytest.mark.parametrize('payload, message', [
    ('not json', 'cannot read'),
    (json.dumps([]), 'top level'),
    (json.dumps({'format': 'other', 'entries': []}), 'format must be'),
    (json.dumps({'format': cmd.FILE_FORMAT, 'entries': []}), 'non-empty'),
    (json.dumps({'format': cmd.FILE_FORMAT, 'entries': [], 'note': 'x'}), 'unknown top-level'),
])
def test_malformed_file_exits_non_zero(tmp_path, payload, message):
    path = tmp_path / 'bad.json'
    path.write_text(payload)
    with pytest.raises(CommandError, match=message):
        _run('--file', str(path))


def test_renewed_target_with_signed_date_is_malformed(tmp_path):
    entry = _valid_entry()
    entry.update(target_status='Renewed', signed_date='2026-01-01', expected={**entry['expected'], 'status': 'Active'})
    entry['class'] = 'A'
    with pytest.raises(CommandError, match='Active targets only'):
        _run('--file', _file(tmp_path, [entry]))
