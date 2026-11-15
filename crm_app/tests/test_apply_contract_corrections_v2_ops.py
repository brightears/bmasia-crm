"""apply_contract_corrections, file format v2: mark_renewed for an Expired term,
mark_expired, add_note and create_contract.

Dry-run, execute, every refusal, idempotent re-runs, audit rows, the journal and
--revert. All data is synthetic; no test relies on primary-key values.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core import mail
from django.core.management.base import CommandError
from django.utils import timezone

from crm_app.models import (
    Company, Contract, ContractServiceLocation, ContractZone, DocumentSequence, Task,
)
from crm_app.services.document_context import document_region
from crm_app.tests.test_apply_contract_corrections_v2 import (
    _audits, _company, _contract, _create, _execute, _expected, _file, _link, _new_term, _reload,
    _renewed, _run, _status, _zone_link,
)

THAI_ENTITY = 'BMAsia (Thailand) Co., Ltd.'


def _expire(contract, group='X:1', cls='X'):
    return {'op': 'mark_expired', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'evidence': 'Fixture sheet / Tab / row 7'}


def _note(contract, text='Funnel check 2026-11: term confirmed by invoice FIXTURE-2.', group='N:1', cls='N'):
    return {'op': 'add_note', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'text': text, 'evidence': 'Fixture sheet / Tab / row 8'}


def _create_new(company, group='C:1', cls='C', twins=(), **new):
    entry = {'op': 'create_contract', 'class': cls, 'group': group, 'company_id': str(company.pk),
             'new': _new_term(**new), 'evidence': 'Fixture sheet / Tab / row 9'}
    if twins:
        entry['twin_company_ids'] = [str(t.pk) for t in twins]
    return entry


def _created_on(company):
    return Contract.objects.filter(company=company, renewed_from__isnull=True,
                                   start_date=date(2026, 3, 1)).order_by('created_at').first()


def _ended_term(company=None, **extra):
    """An Active contract whose end date is already behind us."""
    today = timezone.localdate()
    return _contract(company or _company(), status='Active', start=today - timedelta(days=400),
                     end=today - timedelta(days=35), **extra)


# --- mark_renewed for an Expired old term ------------------------------------------------------

def test_mark_renewed_from_expired_with_link_in_the_same_group(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 1, 1), is_active=False)
    current = _contract(company, status='Active', start=date(2026, 1, 1))
    path = _file(tmp_path, [_link(current, old), _renewed(old, current)])
    assert 'Expired -> Renewed (status only)' in _run('--file', path)
    out, journal_path = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    _reload(old, current)
    assert (old.status, old.is_active, old.start_date) == ('Renewed', False, date(2025, 1, 1))
    assert current.renewed_from_id == old.pk and current.status == 'Active'
    audit = _audits(old.pk).get()
    assert audit.additional_data['action'] == 'Correction: Expired -> Renewed (later term exists)'
    assert audit.changes == {'status': {'old': 'Expired', 'new': 'Renewed'}}

    out, _ = _execute(tmp_path, path, 'j2.json')
    assert out.count('[ALREADY-APPLIED]') == 2

    out = _run('--revert', journal_path, '--execute')
    assert out.count('[REVERTED]') == 2
    _reload(old, current)
    assert (old.status, old.is_active) == ('Expired', False)
    assert current.renewed_from_id is None


def test_mark_renewed_from_expired_refuses_a_successor_on_another_company(tmp_path):
    old = _contract(_company(), status='Expired', start=date(2025, 1, 1), is_active=False)
    elsewhere = _contract(_company(), status='Active', start=date(2026, 1, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_renewed(old, elsewhere)]))
    assert '[SKIPPED:successor_other_company]' in out
    assert _status(old) == 'Expired'


@pytest.mark.parametrize('status', ['Cancelled', 'Draft'])
def test_mark_renewed_from_cancelled_or_draft_is_still_refused(tmp_path, status):
    company = _company()
    old = _contract(company, status=status, start=date(2025, 1, 1))
    current = _contract(company, status='Active', start=date(2026, 1, 1), renewed_from=old)
    out, _ = _execute(tmp_path, _file(tmp_path, [_renewed(old, current)]))
    assert '[SKIPPED:transition_not_allowed]' in out
    assert _status(old) == status


# --- mark_expired -------------------------------------------------------------------------------

def test_mark_expired_dry_run_writes_nothing(tmp_path):
    c = _ended_term()
    version = c.updated_at
    out = _run('--file', _file(tmp_path, [_expire(c)]))
    assert '[WOULD-APPLY] X mark_expired' in out and 'zone links untouched' in out
    c.refresh_from_db()
    assert (c.status, c.updated_at) == ('Active', version)
    assert not _audits().exists()


def test_mark_expired_apply_rerun_and_revert(tmp_path):
    c = _ended_term()
    zone, link = _zone_link(c)
    path = _file(tmp_path, [_expire(c)])
    out, journal_path = _execute(tmp_path, path)
    assert '[APPLIED] X mark_expired' in out
    _reload(c, zone, link)
    assert (c.status, c.is_active) == ('Expired', False)
    # zone links and zones are not touched
    assert (link.is_active, link.end_date, zone.status) == (True, None, 'online')
    audit = _audits(c.pk).get()
    assert audit.action == 'UPDATE'
    assert audit.changes == {'status': {'old': 'Active', 'new': 'Expired'}, 'is_active': {'old': True, 'new': False}}
    assert audit.additional_data['op'] == 'mark_expired'
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert (op['before']['status'], op['after']['status']) == ('Active', 'Expired')
    assert (op['before']['is_active'], op['after']['is_active']) == (True, False)

    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED]' in out
    assert _audits(c.pk).count() == 1

    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] X mark_expired' in out
    _reload(c, link)
    assert (c.status, c.is_active) == ('Active', True)
    assert link.is_active is True
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


def test_mark_expired_revert_is_skipped_when_the_contract_changed_since(tmp_path):
    c = _ended_term()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    assert _status(c) == 'Expired'


def test_mark_expired_refuses_a_contract_without_end_date(tmp_path):
    c = _ended_term()
    Contract.objects.filter(pk=c.pk).update(end_date=None)
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[SKIPPED:no_end_date]' in out
    assert _status(c) == 'Active'


@pytest.mark.parametrize('days_ahead', [0, 30])
def test_mark_expired_refuses_a_term_that_has_not_ended(tmp_path, days_ahead):
    today = timezone.localdate()
    c = _contract(_company(), status='Active', start=today - timedelta(days=300),
                  end=today + timedelta(days=days_ahead))
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[SKIPPED:term_not_ended]' in out
    assert _status(c) == 'Active'


@pytest.mark.parametrize('renewal_status', ['Draft', 'Sent', 'Active'])
def test_mark_expired_refuses_a_term_with_a_renewal(tmp_path, renewal_status):
    c = _ended_term()
    _contract(c.company, status=renewal_status, start=timezone.localdate() - timedelta(days=34), renewed_from=c)
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[SKIPPED:renewal_exists]' in out
    assert _status(c) == 'Active'


def test_mark_expired_ignores_a_cancelled_renewal(tmp_path):
    c = _ended_term()
    _contract(c.company, status='Cancelled', start=timezone.localdate() - timedelta(days=34),
              renewed_from=c, is_active=False)
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[APPLIED]' in out


@pytest.mark.parametrize('status', ['Expired', 'Renewed', 'Cancelled', 'Draft', 'Sent'])
def test_mark_expired_only_from_active(tmp_path, status):
    c = _ended_term()
    Contract.objects.filter(pk=c.pk).update(status=status)
    assert '[SKIPPED:transition_not_allowed]' in _run('--file', _file(tmp_path, [_expire(c)]))


# --- add_note --------------------------------------------------------------------------------------

def test_add_note_appends_a_line_to_existing_notes(tmp_path):
    c = _contract(_company(), notes='First line\nSecond line')
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_note(c, 'Third line')]))
    assert '[APPLIED] N add_note' in out
    c.refresh_from_db()
    assert c.notes == 'First line\nSecond line\nThird line'
    assert (c.status, c.is_active) == ('Active', True)
    audit = _audits(c.pk).get()
    assert audit.changes == {'notes': {'old': 'First line\nSecond line', 'new': c.notes}}
    assert audit.additional_data['note_added'] == 'Third line'
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert (op['before']['notes'], op['after']['notes']) == ('First line\nSecond line', c.notes)


def test_add_note_to_empty_notes_and_any_status(tmp_path):
    c = _contract(_company(), status='Cancelled', is_active=False)
    assert c.notes == ''
    out, _ = _execute(tmp_path, _file(tmp_path, [_note(c, 'Only line')]))
    assert '[APPLIED]' in out
    c.refresh_from_db()
    assert (c.notes, c.status) == ('Only line', 'Cancelled')


def test_add_note_rerun_is_already_applied(tmp_path):
    c = _contract(_company(), notes='Existing')
    path = _file(tmp_path, [_note(c)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED]' in out
    c.refresh_from_db()
    assert c.notes.count('Funnel check') == 1
    assert _audits(c.pk).count() == 1


def test_add_note_line_already_present_is_already_applied(tmp_path):
    c = _contract(_company(), notes='Existing\nAlready here')
    out, _ = _execute(tmp_path, _file(tmp_path, [_note(c, 'Already here')]))
    assert '[ALREADY-APPLIED]' in out
    assert not _audits().exists()


def test_add_note_revert_restores_the_notes(tmp_path):
    c = _contract(_company(), notes='Existing')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_note(c)]))
    assert '[WOULD-REVERT]' in _run('--revert', journal_path)
    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] N add_note' in out and 'notes restored' in out
    c.refresh_from_db()
    assert c.notes == 'Existing'
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


@pytest.mark.parametrize('edit', [
    lambda c: Contract.objects.filter(pk=c.pk).update(notes='Rewritten by someone', updated_at=timezone.now()),
    lambda c: Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5)),
])
def test_add_note_revert_is_skipped_when_edited_since(tmp_path, edit):
    c = _contract(_company(), notes='Existing')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_note(c, 'Added')]))
    edit(c)
    c.refresh_from_db()
    notes = c.notes
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    c.refresh_from_db()
    assert c.notes == notes


@pytest.mark.parametrize('text', ['', '   ', 'x' * 501, 'two\nlines', 'tab\there', 'carriage\rreturn', None, 5])
def test_add_note_malformed_text_stops_the_command(tmp_path, text):
    c = _contract(_company())
    entry = _note(c)
    entry['text'] = text
    with pytest.raises(CommandError, match='text'):
        _run('--file', _file(tmp_path, [entry]))
    c.refresh_from_db()
    assert c.notes == ''


def test_add_note_accepts_500_characters(tmp_path):
    c = _contract(_company())
    out, _ = _execute(tmp_path, _file(tmp_path, [_note(c, 'y' * 500)]))
    assert '[APPLIED]' in out


def test_add_note_refuses_a_changed_contract(tmp_path):
    c = _contract(_company())
    path = _file(tmp_path, [_note(c)])
    Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5))
    assert '[SKIPPED:updated_at_changed]' in _execute(tmp_path, path)[0]


# --- create_contract --------------------------------------------------------------------------------

def test_create_contract_dry_run_writes_nothing_and_reserves_no_number(tmp_path):
    company = _company()
    sequences = list(DocumentSequence.objects.values_list('region', 'next_sequence'))
    out = _run('--file', _file(tmp_path, [_create_new(company)]))
    assert '[WOULD-APPLY] C create_contract company:' in out
    assert 'creates Active 2026-03-01..2027-02-28 (HK-CT number, no predecessor, tax 0.00%)' in out
    assert _created_on(company) is None
    assert list(DocumentSequence.objects.values_list('region', 'next_sequence')) == sequences


def test_create_contract_usd(tmp_path):
    company = _company()
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    assert '[APPLIED] C create_contract' in out
    new = _created_on(company)
    assert new.contract_number in out and new.contract_number.startswith('HK-CT')
    assert new.contract_number.startswith(f'{document_region(new)}-CT')
    assert (new.status, new.is_active, new.renewed_from_id) == ('Active', True, None)
    assert (new.start_date, new.end_date, new.signed_date) == (date(2026, 3, 1), date(2027, 2, 28), date(2026, 2, 10))
    assert (new.currency, new.value, new.tax_rate, new.tax_amount, new.total_value) == (
        'USD', Decimal('900.00'), Decimal('0.00'), Decimal('0.00'), Decimal('900.00'))
    assert new.lifecycle_type == 'new' and new.lifecycle_type_manually_set is True
    assert (new.billing_entity, new.property_name) == ('', '')
    # model defaults
    assert (new.contract_type, new.contract_category, new.renewal_period_months) == ('Annual', 'standard', 12)
    assert new.send_renewal_reminders is True and new.show_zone_pricing_detail is True
    assert new.auto_renew is False and new.billing_frequency == 'Annual'
    assert new.notes.startswith('Created from renewal funnel row')
    rows = list(new.service_locations.order_by('sort_order'))
    assert [(r.location_name, r.platform, r.price) for r in rows] == [
        ('Lobby', 'beatbreeze', Decimal('450.00')), ('Restaurant', 'beatbreeze', Decimal('450.00'))]
    assert not ContractZone.objects.filter(contract=new).exists()
    audit = _audits(new.pk, 'CREATE').get()
    assert audit.additional_data['company_id'] == str(company.pk)
    assert audit.changes['service_locations'] == {'old': 0, 'new': 2}
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert op['contract_id'] == op['created']['contract_id'] == str(new.pk)
    assert op['company_id'] == str(company.pk) and len(op['created']['service_locations']) == 2


def test_create_contract_thb_gets_the_serializer_tax_rate(tmp_path):
    company = _company(THAI_ENTITY)
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company, currency='THB')]))
    assert '[APPLIED]' in out
    new = _created_on(company)
    assert new.contract_number.startswith('TH-CT')
    assert (new.currency, new.tax_rate, new.tax_amount, new.total_value) == (
        'THB', Decimal('7.00'), Decimal('63.00'), Decimal('963.00'))


def test_create_contract_rerun_is_already_applied(tmp_path):
    company = _company()
    path = _file(tmp_path, [_create_new(company)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED]' in out
    assert Contract.objects.filter(company=company).count() == 1


def test_create_contract_revert_deletes_the_untouched_contract(tmp_path):
    company = _company()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    new = _created_on(company)
    assert '[WOULD-REVERT]' in _run('--revert', journal_path)
    out = _run('--revert', journal_path, '--execute')
    assert f'deletes created {new.pk} {new.contract_number}' in out and '[REVERTED]' in out
    assert not Contract.objects.filter(pk=new.pk).exists()
    assert not ContractServiceLocation.objects.filter(contract_id=new.pk).exists()
    assert _audits(new.pk, 'DELETE').exists()
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


@pytest.mark.parametrize('touch', [
    lambda new: Contract.objects.filter(pk=new.pk).update(notes='edited', updated_at=timezone.now()),
    lambda new: Task.objects.create(company=new.company, title='Follow up', related_contract=new),
    lambda new: _zone_link(new),
    lambda new: ContractServiceLocation.objects.create(contract=new, location_name='Extra', platform='soundtrack'),
])
def test_create_contract_revert_never_deletes_a_touched_contract(tmp_path, touch):
    company = _company()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    new = _created_on(company)
    touch(new)
    out = _run('--revert', journal_path, '--execute')
    assert '[SKIPPED:created_contract_touched]' in out
    assert Contract.objects.filter(pk=new.pk, status='Active').exists()


def test_create_contract_refuses_an_overlapping_contract_of_the_company(tmp_path):
    company = _company()
    _contract(company, status='Expired', start=date(2026, 1, 1), is_active=False)
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_on(company) is None


def test_create_contract_refuses_an_overlapping_contract_of_a_twin_company(tmp_path):
    company, twin = _company(), _company()
    _contract(twin, status='Draft', start=date(2026, 6, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company, twins=[twin])]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_on(company) is None


def test_create_contract_ignores_cancelled_and_adjacent_contracts(tmp_path):
    company = _company()
    _contract(company, status='Cancelled', start=date(2026, 5, 1), is_active=False)
    _contract(company, status='Expired', start=date(2025, 3, 1), end=date(2026, 2, 28), is_active=False)
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    assert '[APPLIED]' in out


def test_two_create_contracts_for_one_company_in_one_file_are_refused(tmp_path):
    company = _company()
    entries = [_create_new(company, group='C:1'),
               _create_new(company, group='C:2', start_date='2026-06-01', end_date='2027-05-31')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert not Contract.objects.filter(company=company).exists()


def test_two_create_contracts_in_one_group_are_refused(tmp_path):
    company, twin = _company(), _company()
    entries = [_create_new(company, group='C:1', twins=[twin]), _create_new(twin, group='C:1')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert not Contract.objects.filter(company__in=[company, twin]).exists()


def test_create_contract_and_create_successor_overlapping_are_refused(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 1, 1), is_active=False)
    other = _company()
    entries = [_create(old, group='G:1'), _create_new(other, group='C:1', twins=[company])]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert _status(old) == 'Expired' and not Contract.objects.filter(company=other).exists()


def test_create_contracts_with_consecutive_terms_both_apply(tmp_path):
    company = _company()
    entries = [_create_new(company, group='C:1'),
               _create_new(company, group='C:2', start_date='2027-03-01', end_date='2028-02-29')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[APPLIED]') == 2


def test_create_contract_refuses_a_pricing_mismatch(tmp_path):
    company = _company()
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company, value='1000.00')]))
    assert '[SKIPPED:service_location_pricing_mismatch]' in out
    assert not Contract.objects.filter(company=company).exists()


def test_create_contract_refuses_a_missing_company_or_twin(tmp_path):
    ghost = Company(pk='00000000-0000-4000-8000-00000000c0de')
    company = _company()
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(ghost)]))
    assert '[SKIPPED:missing_company]' in out
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company, twins=[ghost])], 'b.json'), 'j2.json')
    assert '[SKIPPED:missing_twin_company]' in out
    assert not Contract.objects.filter(company=company).exists()


def test_create_contract_refuses_a_company_without_billing_entity(tmp_path):
    company = _company(entity='')
    out, _ = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    assert '[SKIPPED:billing_entity_unresolved]' in out


def test_create_contract_number_reservation_failure_rolls_back(tmp_path):
    from crm_app.services.rene_phase2 import RenePhase2Error
    company = _company()
    with mock.patch('crm_app.services.rene_phase2._reserve_final_contract_number',
                    side_effect=RenePhase2Error('NUMBER_RESERVATION_BLOCKED', 'fixture')):
        out, journal_path = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    assert '[SKIPPED:number_reservation_failed]' in out
    assert not Contract.objects.filter(company=company).exists()
    assert json.loads(open(journal_path).read())['groups'] == []


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(expected={}), 'unknown keys'),
    (lambda e: e.pop('company_id'), 'missing keys'),
    (lambda e: e.update(company_id='abc'), 'company_id: not a UUID'),
    (lambda e: e['new'].update(status='Draft'), 'must be Active'),
    (lambda e: e['new'].update(currency='EUR'), 'currency'),
    (lambda e: e['new'].update(end_date='2026-01-01'), 'before start_date'),
    (lambda e: e.update(twin_company_ids=[e['company_id']]), 'own twin'),
])
def test_create_contract_malformed_entry_stops_the_command(tmp_path, mutate, message):
    entry = _create_new(_company())
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))


# --- no email, no external call ------------------------------------------------------------------

def test_new_ops_send_nothing_and_call_nothing(tmp_path):
    company = _company()
    expire_me = _ended_term()
    note_me = _contract(_company())
    path = _file(tmp_path, [_expire(expire_me), _note(note_me), _create_new(company)])

    def no_network(*args, **kwargs):
        raise AssertionError('external call attempted')

    with mock.patch('crm_app.services.soundtrack_api.SoundtrackAPIService.sync_company_zones') as sync_zones, \
            mock.patch('crm_app.services.email_service.EmailService.send_email', side_effect=no_network), \
            mock.patch('requests.sessions.Session.request', side_effect=no_network), \
            mock.patch('urllib.request.urlopen', side_effect=no_network), \
            mock.patch('smtplib.SMTP', side_effect=no_network), \
            mock.patch('smtplib.SMTP_SSL', side_effect=no_network):
        out, journal_path = _execute(tmp_path, path)
        assert out.count('[APPLIED]') == 3
        assert _run('--revert', journal_path, '--execute').count('[REVERTED]') == 3

    assert mail.outbox == []
    sync_zones.assert_not_called()


# --- review follow-ups ------------------------------------------------------------------------

@pytest.mark.parametrize('old_status', ['Expired', 'Active'])
def test_mark_renewed_refuses_a_successor_that_does_not_renew_it(tmp_path, old_status):
    company = _company()
    old = _contract(company, status=old_status, start=date(2023, 1, 1), is_active=old_status == 'Active')
    later = _contract(company, status='Active', start=date(2026, 1, 1))  # no renewed_from, no link in the group
    out, _ = _execute(tmp_path, _file(tmp_path, [_renewed(old, later)]))
    assert '[SKIPPED:successor_not_linked]' in out
    assert _status(old) == old_status


def test_mark_renewed_accepts_a_successor_already_linked(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 1, 1), is_active=False)
    current = _contract(company, status='Active', start=date(2026, 1, 1), renewed_from=old)
    out, _ = _execute(tmp_path, _file(tmp_path, [_renewed(old, current)]))
    assert '[APPLIED]' in out
    assert _status(old) == 'Renewed'


@pytest.mark.parametrize('renewal_status', ['Renewed', 'Expired'])
def test_mark_expired_refuses_a_term_with_a_closed_renewal(tmp_path, renewal_status):
    c = _ended_term()
    _contract(c.company, status=renewal_status, start=timezone.localdate() - timedelta(days=34),
              renewed_from=c, is_active=False)
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[SKIPPED:renewal_exists]' in out
    assert _status(c) == 'Active'


def test_mark_expired_refuses_when_a_later_active_contract_exists(tmp_path):
    c = _ended_term()
    _contract(c.company, status='Active', start=timezone.localdate() - timedelta(days=34))  # not linked
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[SKIPPED:later_active_contract]' in out
    assert _status(c) == 'Active'


def test_mark_expired_ignores_an_earlier_active_contract_of_the_company(tmp_path):
    c = _ended_term()
    _contract(c.company, status='Active', start=c.start_date - timedelta(days=30))
    out, _ = _execute(tmp_path, _file(tmp_path, [_expire(c)]))
    assert '[APPLIED]' in out


@pytest.mark.parametrize('text', ['line separator', 'next\x85line', 'para graph', 'del\x7fchar'])
def test_add_note_refuses_line_separators(tmp_path, text):
    c = _contract(_company())
    entry = _note(c)
    entry['text'] = text
    with pytest.raises(CommandError, match='text'):
        _run('--file', _file(tmp_path, [entry]))


def test_add_note_revert_is_skipped_when_notes_changed_without_updated_at(tmp_path):
    c = _contract(_company(), notes='Existing')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_note(c, 'Added')]))
    Contract.objects.filter(pk=c.pk).update(notes='Existing\nAdded\nAnother line')  # updated_at left as it is
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal_path, '--execute')
    c.refresh_from_db()
    assert c.notes == 'Existing\nAdded\nAnother line'


def test_create_contract_rerun_needs_the_same_value(tmp_path):
    company = _company()
    _contract(company, status='Active', start=date(2026, 3, 1), end=date(2027, 2, 28), value=Decimal('950.00'))
    out = _run('--file', _file(tmp_path, [_create_new(company)]))   # file value 900.00
    assert '[ALREADY-APPLIED]' not in out
    assert '[SKIPPED:overlapping_contract]' in out


def test_create_contract_pricing_mismatch_is_refused_in_the_dry_run_too(tmp_path):
    company = _company()
    out = _run('--file', _file(tmp_path, [_create_new(company, value='1000.00')]))
    assert '[SKIPPED:service_location_pricing_mismatch]' in out
    assert '[WOULD-APPLY]' not in out


def test_create_contract_revert_notices_a_company_change(tmp_path):
    company, other = _company(), _company()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create_new(company)]))
    new = _created_on(company)
    Contract.objects.filter(pk=new.pk).update(company=other)  # updated_at left as it is
    out = _run('--revert', journal_path, '--execute')
    assert '[SKIPPED:created_contract_touched]' in out
    assert Contract.objects.filter(pk=new.pk).exists()


def test_dry_run_says_groups_are_judged_on_current_data(tmp_path):
    c = _contract(_company())
    out = _run('--file', _file(tmp_path, [_note(c)]))
    assert 'in a dry-run every group is judged on the current data' in out
    out, _ = _execute(tmp_path, _file(tmp_path, [_note(c)], 'b.json'))
    assert 'in a dry-run every group is judged' not in out
