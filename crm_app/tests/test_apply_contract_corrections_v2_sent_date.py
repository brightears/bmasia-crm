"""apply_contract_corrections, file format v2: set_sent_date, and one contract carrying a status
operation plus set_sent_date and add_note in one group.

Dry-run, execute, every refusal, idempotent re-runs, audit rows, the journal and --revert.
All data is synthetic; no test relies on primary-key values.
"""
import json
from datetime import date, timedelta

import pytest
from django.core import mail
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm_app.dates import business_today
from crm_app.models import Contract, Task
from crm_app.services import contract_corrections_v2 as v2
from crm_app.tests.test_apply_contract_corrections_v2 import (
    _audits, _cancel, _company, _contract, _create, _execute, _expected, _file, _reload, _run, _zone_link,
)
from crm_app.tests.test_apply_contract_corrections_v2_ops import _note

SENT = '2024-12-10'  # the default fixture term starts 2025-01-01


def _sent(contract, sent_date=SENT, expected_sent_date=None, group='S:1', cls='S'):
    return {'op': 'set_sent_date', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'expected_sent_date': expected_sent_date, 'sent_date': sent_date,
            'evidence': 'Fixture mailbox / thread 1 / message 1'}


def _writes(queries):
    return [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]


# --- dry run and execute ----------------------------------------------------------------------

def test_dry_run_shows_old_and_new_and_writes_nothing(tmp_path):
    c = _contract(_company(), status='Draft', is_active=False)
    version = c.updated_at
    path = _file(tmp_path, [_sent(c)])
    with CaptureQueriesContext(connection) as queries:
        out = _run('--file', path)
    assert '[WOULD-APPLY] S set_sent_date' in out
    assert f'sent_date empty -> {SENT}; status stays Draft' in out
    assert _writes(queries.captured_queries) == []
    _reload(c)
    assert (c.sent_date, c.updated_at) == (None, version)
    assert not _audits().exists()


@pytest.mark.parametrize('status', ['Draft', 'Sent', 'Active', 'Cancelled', 'Expired', 'Renewed'])
def test_execute_sets_only_the_sent_date_whatever_the_status(tmp_path, status):
    c = _contract(_company(), status=status, is_active=status == 'Active')
    zone, link = _zone_link(c)
    Contract.objects.filter(pk=c.pk).update(sent_date=None)  # a Sent fixture may hold none either
    c.refresh_from_db()
    number, tasks = c.contract_number, Task.objects.count()
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_sent(c)]))
    assert '[APPLIED] S set_sent_date' in out
    _reload(c, zone, link)
    # The file's date, never "today"; nothing else moves: no save(), no post_save handler.
    assert c.sent_date == date.fromisoformat(SENT)
    assert (c.status, c.contract_number, c.is_active) == (status, number, status == 'Active')
    assert (zone.status, link.is_active, link.end_date) == ('online', True, None)
    assert Task.objects.count() == tasks
    assert mail.outbox == []
    audit = _audits(c.pk).get()
    assert audit.action == 'UPDATE'
    assert audit.changes == {'sent_date': {'old': None, 'new': SENT}}
    assert audit.additional_data['op'] == 'set_sent_date'
    assert audit.additional_data['action'] == 'Correction: sent date recorded'
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert (op['before']['sent_date'], op['after']['sent_date']) == (None, SENT)


def test_a_rerun_is_already_applied_and_writes_nothing(tmp_path):
    c = _contract(_company(), status='Active')
    path = _file(tmp_path, [_sent(c)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED] S set_sent_date' in out
    assert _audits(c.pk).count() == 1


def test_a_date_already_holding_the_value_is_already_applied(tmp_path):
    c = _contract(_company(), status='Active', sent_date=date.fromisoformat(SENT))
    out, _ = _execute(tmp_path, _file(tmp_path, [_sent(c, expected_sent_date=None)]))
    assert '[ALREADY-APPLIED]' in out
    assert not _audits().exists()


# --- refusals ---------------------------------------------------------------------------------

def test_a_date_set_since_the_file_was_made_is_not_overwritten(tmp_path):
    c = _contract(_company(), status='Active')
    path = _file(tmp_path, [_sent(c)])
    Contract.objects.filter(pk=c.pk).update(sent_date=date(2024, 12, 20))  # without touching updated_at
    assert '[SKIPPED:sent_date_changed]' in _execute(tmp_path, path)[0]
    Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
    assert '[SKIPPED:updated_at_changed]' in _execute(tmp_path, path, 'j2.json')[0]
    c.refresh_from_db()
    assert c.sent_date == date(2024, 12, 20)


def test_an_existing_date_is_replaced_only_when_the_file_names_it(tmp_path):
    c = _contract(_company(), status='Active', sent_date=date(2024, 12, 20))
    out, _ = _execute(tmp_path, _file(tmp_path, [_sent(c, expected_sent_date='2024-12-20')]))
    assert '[APPLIED]' in out and 'sent_date 2024-12-20 -> 2024-12-10' in out
    c.refresh_from_db()
    assert c.sent_date == date.fromisoformat(SENT)


def test_a_future_date_is_refused(tmp_path):
    c = _contract(_company(), status='Active', start=business_today())
    tomorrow = (business_today() + timedelta(days=1)).isoformat()
    assert '[SKIPPED:sent_date_in_future]' in _run('--file', _file(tmp_path, [_sent(c, tomorrow)]))
    out, _ = _execute(tmp_path, _file(tmp_path, [_sent(c, business_today().isoformat())], 'today.json'))
    assert '[APPLIED]' in out


def test_a_date_after_the_signature_is_refused(tmp_path):
    c = _contract(_company(), status='Active', signed_date=date(2024, 12, 9))
    assert '[SKIPPED:sent_date_after_signed]' in _execute(tmp_path, _file(tmp_path, [_sent(c)]))[0]
    out, _ = _execute(tmp_path, _file(tmp_path, [_sent(c, '2024-12-09')], 'same.json'), 'j2.json')
    assert '[APPLIED]' in out


def test_a_date_far_before_the_term_is_taken_for_a_typo(tmp_path):
    c = _contract(_company(), status='Active')
    bound = v2.SENT_DATE_MAX_DAYS_BEFORE_START
    too_early = (c.start_date - timedelta(days=bound + 1)).isoformat()
    assert '[SKIPPED:sent_date_too_early]' in _run('--file', _file(tmp_path, [_sent(c, too_early)]))
    earliest = (c.start_date - timedelta(days=bound)).isoformat()
    assert '[APPLIED]' in _execute(tmp_path, _file(tmp_path, [_sent(c, earliest)], 'edge.json'))[0]


@pytest.mark.parametrize('change', [
    {'sent_date': '10/12/2024'}, {'sent_date': None}, {'expected_sent_date': 'yesterday'},
    {'expected_sent_date': SENT},  # the same as sent_date: nothing to set
])
def test_malformed_entries_stop_the_command(tmp_path, change):
    c = _contract(_company(), status='Active')
    entry = {**_sent(c), **change}
    with pytest.raises(CommandError, match='sent_date'):
        _run('--file', _file(tmp_path, [entry]))


def test_the_keys_are_required(tmp_path):
    c = _contract(_company(), status='Active')
    entry = _sent(c)
    del entry['expected_sent_date']
    with pytest.raises(CommandError, match='expected_sent_date'):
        _run('--file', _file(tmp_path, [entry]))


# --- one contract, several entries --------------------------------------------------------------

def _draft_with_zone():
    c = _contract(_company(), status='Draft', is_active=False, notes='Existing line')
    zone, link = _zone_link(c)
    return c, zone, link


def test_cancel_record_the_sent_date_and_add_a_note_in_one_group(tmp_path):
    c, zone, link = _draft_with_zone()
    entries = [_note(c, 'Sent on 10 Dec, then cancelled (fixture).', group='S:1', cls='S'),
               _cancel(c, group='S:1', cls='S'), _sent(c)]
    path = _file(tmp_path, entries)
    dry = _run('--file', path)
    assert dry.count('[WOULD-APPLY]') == 3
    out, journal_path = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 3
    _reload(c, zone, link)
    assert (c.status, c.sent_date, c.notes) == ('Cancelled', date.fromisoformat(SENT),
                                                'Existing line\nSent on 10 Dec, then cancelled (fixture).')
    assert (link.is_active, zone.status) == (False, 'cancelled')
    ops = json.loads(open(journal_path).read())['groups'][0]['ops']
    assert [op['op'] for op in ops] == ['set_sent_date', 'mark_cancelled', 'add_note']  # the write order
    assert sorted(a.additional_data['op'] for a in _audits(c.pk)) == ['add_note', 'mark_cancelled', 'set_sent_date']
    assert '[ALREADY-APPLIED]' in _execute(tmp_path, path, 'j2.json')[0]
    assert _audits(c.pk).count() == 3

    assert _run('--revert', journal_path).count('[WOULD-REVERT]') == 3
    reverted = _run('--revert', journal_path, '--execute')
    assert reverted.count('[REVERTED]') == 3
    _reload(c, zone, link)
    assert (c.status, c.sent_date, c.notes) == ('Draft', None, 'Existing line')
    assert (link.is_active, zone.status) == (True, 'online')
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


def test_revert_of_several_entries_is_skipped_when_the_contract_changed_since(tmp_path):
    c, _zone, _link = _draft_with_zone()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_cancel(c, group='S:1', cls='S'), _sent(c)]))
    Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    c.refresh_from_db()
    assert (c.status, c.sent_date) == ('Cancelled', date.fromisoformat(SENT))


def test_a_refused_entry_keeps_the_whole_group_unwritten(tmp_path):
    c, zone, link = _draft_with_zone()
    tomorrow = (business_today() + timedelta(days=1)).isoformat()
    out, _ = _execute(tmp_path, _file(tmp_path, [_cancel(c, group='S:1', cls='S'), _sent(c, tomorrow)]))
    assert out.count('[SKIPPED:sent_date_in_future]') == 2
    _reload(c, link)
    assert (c.status, c.sent_date, link.is_active) == ('Draft', None, True)
    assert not _audits().exists()


def test_entries_for_one_contract_must_state_the_same_expected_state(tmp_path):
    c = _contract(_company(), status='Active')
    stale = _sent(c)
    stale['expected'] = {**stale['expected'], 'updated_at': (c.updated_at - timedelta(minutes=1)).isoformat()}
    out = _run('--file', _file(tmp_path, [_note(c, group='S:1', cls='S'), stale]))
    assert out.count('[SKIPPED:expected_differs]') == 2


@pytest.mark.parametrize('entries', [
    lambda c: [_sent(c), _sent(c, '2024-12-11')],                       # two dates
    lambda c: [_cancel(c, group='S:1', cls='S'), _cancel(c, group='S:1', cls='S')],
    lambda c: [_sent(c), _note(c, group='S:2', cls='S')],                # two groups
    lambda c: [_sent(c), _create(c, group='S:1', cls='S')],             # with a created term
])
def test_other_repetitions_of_a_contract_are_refused(tmp_path, entries):
    c = _contract(_company(), status='Active')
    out = _run('--file', _file(tmp_path, entries(c)))
    assert '[SKIPPED:duplicate_contract_id]' in out
    assert 'WOULD-APPLY' not in out


# --- revert of set_sent_date alone ---------------------------------------------------------------

def test_revert_restores_the_previous_sent_date(tmp_path):
    c = _contract(_company(), status='Active')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_sent(c)]))
    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] S set_sent_date' in out and 'sent date restored' in out
    c.refresh_from_db()
    assert c.sent_date is None
    audit = _audits(c.pk).get(additional_data__mode='revert')
    assert audit.changes == {'sent_date': {'old': SENT, 'new': None}}
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


def test_revert_is_skipped_when_the_date_was_changed_since(tmp_path):
    c = _contract(_company(), status='Active')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_sent(c)]))
    Contract.objects.filter(pk=c.pk).update(sent_date=date(2024, 12, 15))
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    c.refresh_from_db()
    assert c.sent_date == date(2024, 12, 15)


# --- what a historical sent date does to the contract follow-ups ---------------------------------

@pytest.mark.parametrize('status', ['Active', 'Cancelled', 'Expired', 'Renewed', 'Draft'])
def test_follow_ups_never_select_a_contract_that_is_not_sent(status):
    from crm_app.services.email_service import contract_followup_candidates
    old = business_today() - timedelta(days=45)
    c = _contract(_company(), status=status, sent_date=old)
    sent = _contract(_company(), status='Sent', sent_date=old)
    Contract.objects.filter(pk=c.pk).update(sent_date=old)
    candidates = set(contract_followup_candidates().values_list('pk', flat=True))
    assert c.pk not in candidates
    assert sent.pk in candidates


def test_the_contract_follow_up_sender_is_switched_off():
    from crm_app.services.email_service import EmailService
    _contract(_company(), status='Sent', sent_date=business_today() - timedelta(days=45))
    assert EmailService().send_contract_followups() == {'sent': 0, 'failed': 0, 'skipped': 0}
    assert mail.outbox == []
