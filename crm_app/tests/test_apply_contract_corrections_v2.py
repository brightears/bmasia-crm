"""apply_contract_corrections, file format v2.

mark_cancelled (with the zone-release side effect), mark_renewed (status
only), set_renewed_from and create_successor: dry-run, execute, every refusal,
group atomicity, idempotent re-runs, audit rows, the journal and --revert, and
that nothing emails or calls out. All data is synthetic; no test relies on
primary-key values.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connection
from django.utils import timezone

from crm_app.management.commands import apply_contract_corrections as cmd
from crm_app.models import (
    AuditLog, Company, Contract, ContractServiceLocation, ContractZone, DocumentSequence, Task, Zone,
)
from crm_app.services import contract_corrections_v2 as v2
from crm_app.services.document_context import document_region


def _status(contract):
    contract.refresh_from_db()
    return contract.status

_numbers = iter(range(1, 100_000))
PLACEHOLDER_START = date(2025, 1, 1)


# --- fixtures ------------------------------------------------------------------------

def _company(entity='BMAsia Limited'):
    return Company.objects.create(name=f'V2 fixture company {next(_numbers)}', billing_entity=entity)


def _contract(company, status='Active', start=PLACEHOLDER_START, end=None, renewed_from=None, **extra):
    values = dict(
        company=company, contract_number=f'TEST-V2-{next(_numbers):05d}', status=status,
        start_date=start, end_date=end or start + timedelta(days=364),
        value=Decimal('1200.00'), total_value=Decimal('1200.00'), is_active=status == 'Active',
        renewed_from=renewed_from, currency='USD',
    )
    values.update(extra)
    return Contract.objects.create(**values)


def _zone_link(contract, status='online'):
    zone = Zone.objects.create(company=contract.company, name=f'Zone {next(_numbers)}', status=status)
    link = ContractZone.objects.create(contract=contract, zone=zone, start_date=contract.start_date)
    return zone, link


def _expected(contract):
    contract.refresh_from_db()
    return {
        'status': contract.status,
        'start_date': contract.start_date.isoformat(),
        'end_date': contract.end_date.isoformat() if contract.end_date else None,
        'updated_at': contract.updated_at.isoformat(),
    }


def _cancel(contract, group='D:1', cls='D'):
    return {'op': 'mark_cancelled', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'evidence': 'Fixture sheet / Tab / row 3'}


def _renewed(old, successor, group='E:1', cls='E'):
    return {'op': 'mark_renewed', 'class': cls, 'group': group, 'contract_id': str(old.pk),
            'expected': _expected(old), 'successor_id': str(successor.pk),
            'successor_expected': _expected(successor), 'evidence': 'Fixture sheet / Tab / row 4'}


def _link(contract, predecessor, group='E:1', cls='E'):
    return {'op': 'set_renewed_from', 'class': cls, 'group': group, 'contract_id': str(contract.pk),
            'expected': _expected(contract), 'renewed_from_id': str(predecessor.pk),
            'renewed_from_expected': _expected(predecessor), 'evidence': 'Fixture sheet / Tab / row 5'}


def _new_term(**overrides):
    new = {
        'status': 'Active', 'start_date': '2026-03-01', 'end_date': '2027-02-28',
        'value': '900.00', 'currency': 'USD', 'signed_date': '2026-02-10',
        'billing_frequency': 'Annual', 'auto_renew': None, 'service_type': None, 'price_per_zone': None,
        'notes': 'Created from renewal funnel row (fixture). Invoice FIXTURE-1.',
        'service_locations': [
            {'location_name': 'Lobby', 'platform': 'beatbreeze', 'price': '450.00'},
            {'location_name': 'Restaurant', 'platform': 'beatbreeze', 'price': '450.00'},
        ],
    }
    new.update(overrides)
    return new


def _create(old, group='G:1', cls='G', twins=(), **new):
    entry = {'op': 'create_successor', 'class': cls, 'group': group, 'old_contract_id': str(old.pk),
             'old_expected': _expected(old), 'new': _new_term(**new), 'evidence': 'Fixture sheet / Tab / row 6'}
    if twins:
        entry['twin_company_ids'] = [str(t.pk) for t in twins]
    return entry


def _file(tmp_path, entries, name='v2.json'):
    path = tmp_path / name
    path.write_text(json.dumps({'format': v2.FILE_FORMAT_V2, 'entries': entries}))
    return str(path)


def _run(*args):
    out = StringIO()
    call_command('apply_contract_corrections', *args, stdout=out)
    return out.getvalue()


def _execute(tmp_path, path, journal='journal.json'):
    journal_path = str(tmp_path / journal)
    return _run('--file', path, '--execute', '--journal', journal_path), journal_path


def _audits(record_id=None, action=None):
    qs = AuditLog.objects.filter(model_name='Contract', additional_data__command=cmd.COMMAND)
    if record_id is not None:
        qs = qs.filter(record_id=str(record_id))
    if action:
        qs = qs.filter(action=action)
    return qs


def _reload(*objs):
    for obj in objs:
        obj.refresh_from_db()


def _created_for(old):
    return Contract.objects.filter(renewed_from=old).order_by('created_at').first()


# --- mark_cancelled ----------------------------------------------------------------------

def test_cancel_dry_run_writes_nothing(tmp_path):
    c = _contract(_company())
    zone, link = _zone_link(c)
    version = c.updated_at
    out = _run('--file', _file(tmp_path, [_cancel(c)]))
    assert '[WOULD-APPLY] D mark_cancelled' in out and 'releases 1 active zone link(s)' in out
    _reload(c, zone, link)
    assert (c.status, c.updated_at, zone.status, link.is_active) == ('Active', version, 'online', True)
    assert not _audits().exists()


@pytest.mark.parametrize('status', ['Active', 'Sent', 'Draft'])
def test_cancel_execute_releases_zones_and_journals_them(tmp_path, status):
    c = _contract(_company(), status=status)
    zone, link = _zone_link(c)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    assert '[APPLIED] D mark_cancelled' in out
    _reload(c, zone, link)
    assert c.status == 'Cancelled' and c.is_active is False
    # the link ends on the earlier of today and the contract's end date
    assert link.is_active is False and link.end_date == min(timezone.now().date(), c.end_date)
    assert zone.status == 'cancelled'
    audit = _audits(c.pk).get()
    assert audit.changes['status'] == {'old': status, 'new': 'Cancelled'}
    assert audit.additional_data['zone_links_closed'] == [str(link.pk)]
    assert audit.additional_data['zones_marked_cancelled'] == [str(zone.pk)]
    assert audit.additional_data['op'] == 'mark_cancelled'
    journal = json.loads(open(journal_path).read())
    op = journal['groups'][0]['ops'][0]
    assert op['zone_links'][0]['before'] == {'end_date': None, 'is_active': True}
    assert op['zones'][0] == {'id': str(zone.pk), 'before': {'status': 'online'}, 'after': {'status': 'cancelled'},
                              'other_active_links': []}


def test_cancel_revert_restores_contract_links_and_zones(tmp_path):
    c = _contract(_company())
    zone, link = _zone_link(c, status='offline')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    assert '[WOULD-REVERT]' in _run('--revert', journal_path)
    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] D mark_cancelled' in out and '1 zone link(s) restored' in out
    _reload(c, zone, link)
    assert (c.status, c.is_active) == ('Active', True)
    assert (link.is_active, link.end_date, zone.status) == (True, None, 'offline')
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


def test_cancel_revert_leaves_a_zone_whose_status_moved(tmp_path):
    c = _contract(_company())
    zone, link = _zone_link(c)
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    Zone.objects.filter(pk=zone.pk).update(status='expired')  # e.g. a later sync
    out = _run('--revert', journal_path, '--execute')
    assert 'zone status(es) changed since apply, left as they are' in out
    _reload(c, zone, link)
    assert c.status == 'Active' and link.is_active is True and zone.status == 'expired'


def test_cancel_revert_skips_when_a_link_changed(tmp_path):
    c = _contract(_company())
    _, link = _zone_link(c)
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    ContractZone.objects.filter(pk=link.pk).update(end_date=date(2020, 1, 1))
    out = _run('--revert', journal_path, '--execute')
    assert '[SKIPPED:changed_since_apply]' in out
    assert Contract.objects.get(pk=c.pk).status == 'Cancelled'


def test_cancel_rerun_is_already_applied(tmp_path):
    c = _contract(_company(), status='Sent')
    path = _file(tmp_path, [_cancel(c)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'journal2.json')
    assert '[ALREADY-APPLIED]' in out
    assert _audits(c.pk).count() == 1


@pytest.mark.parametrize('status', ['Renewed', 'Expired', 'Cancelled'])
def test_cancel_from_closed_status_is_refused(tmp_path, status):
    c = _contract(_company(), status=status)
    out = _run('--file', _file(tmp_path, [_cancel(c)]))
    assert '[SKIPPED:transition_not_allowed]' in out


def test_cancel_refuses_a_zone_shared_with_a_live_contract(tmp_path):
    company = _company()
    running = _contract(company)
    draft = _contract(company, status='Draft', start=date(2026, 1, 1), renewed_from=running)
    zone, _ = _zone_link(running)
    ContractZone.objects.create(contract=draft, zone=zone, start_date=draft.start_date)
    out, _ = _execute(tmp_path, _file(tmp_path, [_cancel(draft)]))
    assert '[SKIPPED:zone_shared_with_live_contract]' in out
    _reload(draft, zone)
    assert draft.status == 'Draft' and zone.status == 'online'


def test_cancel_allows_a_zone_shared_with_a_contract_cancelled_in_the_same_group(tmp_path):
    company = _company()
    old = _contract(company)
    renewal = _contract(company, status='Sent', start=date(2026, 1, 1), renewed_from=old)
    zone, _ = _zone_link(old)
    ContractZone.objects.create(contract=renewal, zone=zone, start_date=renewal.start_date)
    out, _ = _execute(tmp_path, _file(tmp_path, [_cancel(old, 'D:x'), _cancel(renewal, 'D:x')]))
    assert out.count('[APPLIED]') == 2
    _reload(old, renewal, zone)
    assert old.status == renewal.status == 'Cancelled' and zone.status == 'cancelled'


@pytest.mark.parametrize('change, reason', [
    (lambda c: Contract.objects.filter(pk=c.pk).update(status='Expired'), 'status_changed'),
    (lambda c: Contract.objects.filter(pk=c.pk).update(end_date=date(2030, 1, 1)), 'dates_changed'),
    (lambda c: Contract.objects.filter(pk=c.pk).update(updated_at=timezone.now() + timedelta(seconds=5)),
     'updated_at_changed'),
])
def test_cancel_refuses_a_changed_contract(tmp_path, change, reason):
    c = _contract(_company())
    path = _file(tmp_path, [_cancel(c)])
    change(c)
    out, _ = _execute(tmp_path, path)
    assert f'[SKIPPED:{reason}]' in out
    assert not _audits().exists()


def test_cancel_side_effect_guard_rolls_back(tmp_path):
    c = _contract(_company())
    zone, link = _zone_link(c)
    with mock.patch('crm_app.models.Zone.mark_as_cancelled'):  # the handler would leave the zone live
        out, _ = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    assert '[SKIPPED:unexpected_side_effect]' in out
    _reload(c, link)
    assert c.status == 'Active' and link.is_active is True


# --- mark_renewed and set_renewed_from ---------------------------------------------------------

def _placeholder_and_current(link=False, current_status='Active'):
    company = _company()
    placeholder = _contract(company, status='Active')
    current = _contract(company, status=current_status, start=date(2025, 6, 1),
                        renewed_from=placeholder if link else None)
    return placeholder, current


def test_mark_renewed_is_status_only(tmp_path):
    placeholder, current = _placeholder_and_current(link=True)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_renewed(placeholder, current)]))
    assert '[APPLIED] E mark_renewed' in out
    _reload(placeholder, current)
    assert (placeholder.status, placeholder.is_active) == ('Renewed', False)
    assert placeholder.start_date == PLACEHOLDER_START  # never re-dated
    assert _audits(placeholder.pk).get().additional_data['later_term_id'] == str(current.pk)
    assert not _audits(current.pk).exists()
    _run('--revert', journal_path, '--execute')
    placeholder.refresh_from_db()
    assert (placeholder.status, placeholder.is_active) == ('Active', True)


def test_mark_renewed_with_link_in_the_same_group(tmp_path):
    placeholder, current = _placeholder_and_current(link=False)
    path = _file(tmp_path, [_link(current, placeholder), _renewed(placeholder, current)])
    out, journal_path = _execute(tmp_path, path)
    assert out.count('[APPLIED]') == 2
    _reload(placeholder, current)
    assert placeholder.status == 'Renewed' and current.renewed_from_id == placeholder.pk
    assert current.status == 'Active'
    assert '[ALREADY-APPLIED]' in _execute(tmp_path, path, 'j2.json')[0]
    _run('--revert', journal_path, '--execute')
    _reload(placeholder, current)
    assert placeholder.status == 'Active' and current.renewed_from_id is None


def test_mark_renewed_refusals(tmp_path):
    company = _company()
    p1 = _contract(company)
    other_company_term = _contract(_company(), start=date(2025, 6, 1))
    p2 = _contract(company)
    sent_term = _contract(company, status='Sent', start=date(2025, 6, 1))
    p3 = _contract(company, start=date(2025, 6, 1))
    earlier = _contract(company, start=date(2024, 6, 1))
    p4 = _contract(company)
    elsewhere = _contract(company, start=date(2023, 1, 1), status='Expired')
    renews_other = _contract(company, start=date(2025, 7, 1), renewed_from=elsewhere)
    path = _file(tmp_path, [
        _renewed(p1, other_company_term, 'E:1'),
        _renewed(p2, sent_term, 'E:2'),
        _renewed(p3, earlier, 'E:3'),
        _renewed(p4, renews_other, 'E:4'),
    ])
    out = _run('--file', path)
    for reason in ('successor_other_company', 'successor_not_active', 'successor_not_later',
                   'successor_renews_other_contract'):
        assert f'[SKIPPED:{reason}]' in out


def test_mark_renewed_refuses_a_changed_or_missing_successor(tmp_path):
    placeholder, current = _placeholder_and_current(link=True)
    entry = _renewed(placeholder, current)
    Contract.objects.filter(pk=current.pk).update(updated_at=timezone.now() + timedelta(seconds=3))
    assert '[SKIPPED:successor_changed]' in _run('--file', _file(tmp_path, [entry]))
    entry['successor_id'] = '00000000-0000-4000-8000-00000000abcd'
    assert '[SKIPPED:missing_successor]' in _run('--file', _file(tmp_path, [entry], 'b.json'))


def test_mark_renewed_from_expired_is_refused(tmp_path):
    company = _company()
    placeholder = _contract(company, status='Expired')
    current = _contract(company, start=date(2025, 6, 1))
    assert '[SKIPPED:transition_not_allowed]' in _run('--file', _file(tmp_path, [_renewed(placeholder, current)]))


def test_set_renewed_from_links_without_status_change(tmp_path):
    company = _company()
    placeholder = _contract(company, status='Expired')
    current = _contract(company, start=date(2025, 6, 1))
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_link(current, placeholder)]))
    assert '[APPLIED] E set_renewed_from' in out
    _reload(current, placeholder)
    assert current.renewed_from_id == placeholder.pk and current.status == 'Active'
    assert placeholder.status == 'Expired'
    assert _audits(current.pk).get().changes == {'renewed_from': {'old': None, 'new': str(placeholder.pk)}}
    _run('--revert', journal_path, '--execute')
    current.refresh_from_db()
    assert current.renewed_from_id is None


def test_set_renewed_from_refusals(tmp_path):
    company = _company()
    base = _contract(company, status='Expired')
    conflict = _contract(company, start=date(2025, 6, 1), renewed_from=_contract(company, status='Expired'))
    other = _contract(_company(), status='Expired')
    cross = _contract(company, start=date(2025, 6, 2))
    later_pred = _contract(company, start=date(2026, 1, 1), status='Expired')
    not_earlier = _contract(company, start=date(2025, 6, 3))
    taken = _contract(company, status='Expired', start=date(2024, 1, 1))
    _contract(company, start=date(2024, 6, 1), renewed_from=taken)
    second = _contract(company, start=date(2025, 6, 4))
    active_pred = _contract(company, start=date(2024, 3, 1))
    left_active = _contract(company, start=date(2025, 6, 5))
    path = _file(tmp_path, [
        _link(conflict, base, 'E:1'),
        _link(cross, other, 'E:2'),
        _link(not_earlier, later_pred, 'E:3'),
        _link(second, taken, 'E:4'),
        _link(left_active, active_pred, 'E:5'),
    ])
    out = _run('--file', path)
    for reason in ('renewed_from_conflict', 'different_companies', 'predecessor_not_earlier',
                   'predecessor_renewed_by_other', 'predecessor_left_active'):
        assert f'[SKIPPED:{reason}]' in out


def test_set_renewed_from_self_reference_is_malformed(tmp_path):
    c = _contract(_company())
    with pytest.raises(CommandError, match='reference itself'):
        _run('--file', _file(tmp_path, [_link(c, c)]))


# --- create_successor ---------------------------------------------------------------------------

def test_create_dry_run_writes_nothing_and_reserves_no_number(tmp_path):
    old = _contract(_company(), status='Expired')
    sequences = list(DocumentSequence.objects.values_list('region', 'next_sequence'))
    out = _run('--file', _file(tmp_path, [_create(old)]))
    assert '[WOULD-APPLY] G create_successor' in out
    assert 'creates Active 2026-03-01..2027-02-28 with 2 service location(s) (beatbreeze 2)' in out
    assert _created_for(old) is None
    assert list(DocumentSequence.objects.values_list('region', 'next_sequence')) == sequences
    assert Contract.objects.get(pk=old.pk).status == 'Expired'


def test_create_from_expired_placeholder(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', tax_rate=Decimal('7.00'), property_name='Fixture venue',
                    customer_contact_name='Fixture person', customer_signatory_name='Fixture signer',
                    custom_terms='Fixture custom terms', payment_terms='Net 30', billing_frequency='Annual',
                    auto_renew=True, service_type='beat_breeze_yearly', send_renewal_reminders=False)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert '[APPLIED] G create_successor' in out
    new = _created_for(old)
    old.refresh_from_db()
    assert (old.status, old.is_active, old.start_date) == ('Renewed', False, PLACEHOLDER_START)
    assert new.status == 'Active' and new.is_active is True
    assert (new.start_date, new.end_date) == (date(2026, 3, 1), date(2027, 2, 28))
    assert new.contract_number.startswith(f'{document_region(new)}-CT')
    assert new.contract_number in out
    assert new.value == Decimal('900.00') and new.tax_rate == Decimal('7.00')
    assert new.tax_amount == Decimal('63.00') and new.total_value == Decimal('963.00')
    assert (new.company_id, new.currency, new.billing_entity) == (old.company_id, old.currency, old.billing_entity)
    assert new.lifecycle_type == 'renewal' and new.lifecycle_type_manually_set is True
    assert new.signed_date == date(2026, 2, 10) and new.auto_renew is True
    assert new.service_type == 'beat_breeze_yearly' and new.property_name == 'Fixture venue'
    assert new.send_renewal_reminders is False
    assert new.notes.startswith('Created from renewal funnel row')
    # never copied
    assert new.customer_contact_name == '' and new.customer_signatory_name == ''
    assert new.custom_terms == '' and new.payment_terms == ''
    rows = list(new.service_locations.order_by('sort_order'))
    assert [(r.location_name, r.platform, r.price) for r in rows] == [
        ('Lobby', 'beatbreeze', Decimal('450.00')), ('Restaurant', 'beatbreeze', Decimal('450.00'))]
    assert _audits(new.pk, 'CREATE').get().additional_data['renews_contract_id'] == str(old.pk)
    assert _audits(old.pk, 'UPDATE').get().changes['status'] == {'old': 'Expired', 'new': 'Renewed'}
    journal = json.loads(open(journal_path).read())
    created = journal['groups'][0]['ops'][0]['created']
    assert created['contract_id'] == str(new.pk) and len(created['service_locations']) == 2


def test_create_from_active_old_term_closes_it_through_the_lifecycle_rule(tmp_path):
    old = _contract(_company(), status='Active', start=date(2025, 3, 1))
    _execute(tmp_path, _file(tmp_path, [_create(old)]))
    new = _created_for(old)
    old.refresh_from_db()
    assert old.status == 'Renewed' and new.status == 'Active'
    closure = _audits(old.pk).get()
    assert closure.additional_data['rule'] == 'renewed_predecessor_closed_on_successor_active'
    assert closure.additional_data['batch_id'] and closure.additional_data['op'] == 'create_successor'


def test_create_skips_a_number_already_held_by_an_imported_contract(tmp_path):
    old = _contract(_company(), status='Expired')
    region = document_region(old)
    year = timezone.now().strftime('%y')
    seq, _ = DocumentSequence.objects.get_or_create(region=region, doc_type='CT', year=year,
                                                    defaults={'next_sequence': 1})
    seq.next_sequence = 700
    seq.save()
    _contract(_company(), contract_number=f'{region}-CT{year}700')
    _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert _created_for(old).contract_number == f'{region}-CT{year}701'


def test_create_rerun_is_already_applied(tmp_path):
    old = _contract(_company(), status='Expired')
    path = _file(tmp_path, [_create(old)])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, 'j2.json')
    assert '[ALREADY-APPLIED]' in out
    assert Contract.objects.filter(renewed_from=old).count() == 1


def test_create_with_mixed_platform_rows(tmp_path):
    old = _contract(_company(), status='Expired')
    rows = [{'location_name': 'Zone 1', 'platform': 'beatbreeze', 'price': '380.00'},
            {'location_name': 'Zone 2', 'platform': 'soundtrack', 'price': '430.00'}]
    _execute(tmp_path, _file(tmp_path, [_create(old, value='810.00', service_locations=rows)]))
    new = _created_for(old)
    assert sorted(new.service_locations.values_list('platform', flat=True)) == ['beatbreeze', 'soundtrack']


def test_create_refuses_an_overlapping_contract_of_the_company(tmp_path):
    company = _company()
    old = _contract(company, status='Expired')
    _contract(company, status='Draft', start=date(2026, 6, 1))  # inside the new term, not a renewal
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_for(old) is None


def test_create_refuses_an_overlapping_contract_of_a_twin_company(tmp_path):
    old = _contract(_company(), status='Expired')
    twin = _company()
    _contract(twin, status='Active', start=date(2026, 1, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old, twins=[twin])]))
    assert '[SKIPPED:overlapping_contract]' in out
    assert _created_for(old) is None


def test_create_ignores_cancelled_overlaps_and_the_old_contract_itself(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 6, 1))  # overlaps the new term itself
    _contract(company, status='Cancelled', start=date(2026, 5, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old, start_date='2026-03-01')]))
    assert '[APPLIED]' in out


@pytest.mark.parametrize('renewal_status, reason', [
    ('Draft', 'open_renewal_exists'), ('Sent', 'open_renewal_exists'), ('Active', 'active_renewal_exists')])
def test_create_refuses_when_the_old_contract_already_has_a_renewal(tmp_path, renewal_status, reason):
    company = _company()
    old = _contract(company, status='Expired')
    _contract(company, status=renewal_status, start=date(2028, 1, 1), renewed_from=old)
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert f'[SKIPPED:{reason}]' in out


def test_create_refuses_a_changed_old_contract(tmp_path):
    old = _contract(_company(), status='Expired')
    path = _file(tmp_path, [_create(old)])
    old.notes = 'edited by someone'
    old.save()
    out, _ = _execute(tmp_path, path)
    assert '[SKIPPED:updated_at_changed]' in out
    assert _created_for(old) is None


@pytest.mark.parametrize('overrides, twins, reason', [
    ({'currency': 'THB'}, False, 'currency_mismatch'),
    ({'value': '1000.00'}, False, 'service_location_pricing_mismatch'),
    ({}, True, 'missing_twin_company'),
])
def test_create_value_refusals(tmp_path, overrides, twins, reason):
    old = _contract(_company(), status='Expired')
    entry = _create(old, **overrides)
    if twins:
        entry['twin_company_ids'] = ['00000000-0000-4000-8000-00000000beef']
    out, _ = _execute(tmp_path, _file(tmp_path, [entry]))
    assert f'[SKIPPED:{reason}]' in out
    assert _created_for(old) is None


@pytest.mark.parametrize('status', ['Renewed', 'Draft', 'Sent', 'Cancelled'])
def test_create_from_other_statuses_is_refused(tmp_path, status):
    old = _contract(_company(), status=status)
    assert '[SKIPPED:transition_not_allowed]' in _run('--file', _file(tmp_path, [_create(old)]))


def test_group_is_all_or_nothing(tmp_path):
    company = _company()
    old = _contract(company, status='Expired')
    stale = _contract(company, status='Draft', start=date(2029, 1, 1))
    entries = [_create(old, group='G:x'), _cancel(stale, group='G:x', cls='G')]
    Contract.objects.filter(pk=stale.pk).update(status='Sent')
    sequences = list(DocumentSequence.objects.values_list('region', 'next_sequence'))
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[SKIPPED:status_changed]') == 2
    assert _created_for(old) is None
    assert Contract.objects.get(pk=old.pk).status == 'Expired'
    assert list(DocumentSequence.objects.values_list('region', 'next_sequence')) == sequences


def test_a_failure_after_the_create_rolls_the_group_back(tmp_path):
    old = _contract(_company(), status='Active', start=date(2025, 3, 1))
    not_closed = mock.Mock(outcome='predecessor_not_active', predecessor_id=None)
    with mock.patch.object(v2, 'close_renewed_predecessor', return_value=not_closed):
        out, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert '[SKIPPED:rule_did_not_close_old_term(predecessor_not_active)]' in out
    assert _created_for(old) is None and not _audits().exists()
    assert json.loads(open(journal_path).read())['groups'] == []


def test_revert_deletes_an_untouched_created_contract(tmp_path):
    old = _contract(_company(), status='Expired')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    new = _created_for(old)
    out = _run('--revert', journal_path, '--execute')
    assert f'deletes created {new.pk} {new.contract_number}' in out and '[REVERTED]' in out
    assert not Contract.objects.filter(pk=new.pk).exists()
    assert not ContractServiceLocation.objects.filter(contract_id=new.pk).exists()
    old.refresh_from_db()
    assert (old.status, old.is_active) == ('Expired', False)
    assert _audits(new.pk, 'DELETE').exists()
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


@pytest.mark.parametrize('touch', [
    lambda new: Contract.objects.filter(pk=new.pk).update(notes='edited', updated_at=timezone.now()),
    lambda new: Task.objects.create(company=new.company, title='Follow up', related_contract=new),
    lambda new: _zone_link(new),
    lambda new: ContractServiceLocation.objects.create(contract=new, location_name='Extra', platform='soundtrack'),
])
def test_revert_never_deletes_a_touched_created_contract(tmp_path, touch):
    old = _contract(_company(), status='Expired')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    new = _created_for(old)
    touch(new)
    out = _run('--revert', journal_path, '--execute')
    assert '[SKIPPED:created_contract_touched]' in out
    new.refresh_from_db()
    assert new.status == 'Active'
    assert Contract.objects.get(pk=old.pk).status == 'Renewed'


def test_create_may_start_on_the_old_contracts_start_for_a_longer_term(tmp_path):
    old = _contract(_company(), status='Expired', start=PLACEHOLDER_START)  # 2025 placeholder
    rows = [{'location_name': 'Zone 1', 'platform': 'beatbreeze', 'price': '260.00'}]
    entry = _create(old, start_date='2025-01-01', end_date='2026-12-31', value='260.00', service_locations=rows)
    out, _ = _execute(tmp_path, _file(tmp_path, [entry]))
    assert '[APPLIED]' in out
    new = _created_for(old)
    assert (new.start_date, new.end_date) == (date(2025, 1, 1), date(2026, 12, 31))
    assert Contract.objects.get(pk=old.pk).status == 'Renewed'


# --- create_successor: zone links carried over ------------------------------------------------

def _old_with_links(status='Expired'):
    old = _contract(_company(), status=status, start=date(2025, 3, 1))
    z1, l1 = _zone_link(old)
    z2, l2 = _zone_link(old, status='offline')
    z3, l3 = _zone_link(old)
    ContractZone.objects.filter(pk=l3.pk).update(is_active=False, end_date=date(2025, 9, 1))  # ended: history
    return old, (z1, z2, z3), (l1, l2, l3)


def test_create_copies_the_old_contracts_active_zone_links(tmp_path):
    old, (z1, z2, z3), (l1, l2, l3) = _old_with_links()
    out = _run('--file', _file(tmp_path, [_create(old)]))
    assert 'copies 2 active zone link(s) to the new term' in out
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)], 'b.json'))
    new = _created_for(old)
    links = list(ContractZone.objects.filter(contract=new))
    assert sorted(l.zone_id for l in links) == sorted([z1.pk, z2.pk])
    assert all(l.start_date == date(2026, 3, 1) and l.is_active and l.end_date is None for l in links)
    # the old links to the copied zones are handed over: closed the day before the new term
    for link, active, end in ((l1, False, date(2026, 2, 28)), (l2, False, date(2026, 2, 28)),
                              (l3, False, date(2025, 9, 1))):
        link.refresh_from_db()
        assert (link.is_active, link.end_date, link.contract_id) == (active, end, old.pk)
    _reload(z1, z2)
    assert (z1.status, z2.status) == ('online', 'offline')
    audit = _audits(new.pk, 'CREATE').get()
    assert sorted(audit.additional_data['zone_links_copied']) == sorted([str(z1.pk), str(z2.pk)])
    assert audit.changes['zone_links'] == {'old': 0, 'new': 2}
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    created = op['created']
    assert sorted(z['id'] for z in created['zone_links']) == sorted(str(l.pk) for l in links)
    assert sorted(r['id'] for r in op['old_zone_links_closed']) == sorted([str(l1.pk), str(l2.pk)])
    assert all(r['before'] == {'end_date': None, 'is_active': True} and
               r['after'] == {'end_date': '2026-02-28', 'is_active': False} for r in op['old_zone_links_closed'])
    assert sorted(audit.additional_data['old_zone_links_closed']) == sorted([str(l1.pk), str(l2.pk)])


def test_revert_removes_the_copied_zone_links_only(tmp_path):
    old, (z1, z2, _), (l1, l2, _) = _old_with_links(status='Active')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    new = _created_for(old)
    copied = list(ContractZone.objects.filter(contract=new).values_list('pk', flat=True))
    out = _run('--revert', journal_path, '--execute')
    assert '2 copied zone link(s) removed' in out
    assert not ContractZone.objects.filter(pk__in=copied).exists()
    assert not Contract.objects.filter(pk=new.pk).exists()
    for link in (l1, l2):
        link.refresh_from_db()
        assert link.is_active is True and link.contract_id == old.pk
    assert Zone.objects.filter(pk__in=[z1.pk, z2.pk]).count() == 2
    assert Contract.objects.get(pk=old.pk).status == 'Active'


def test_revert_treats_a_changed_copied_link_as_touched(tmp_path):
    old, _, _ = _old_with_links()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    new = _created_for(old)
    ContractZone.objects.filter(contract=new).update(is_active=False, end_date=date(2026, 6, 1))
    out = _run('--revert', journal_path, '--execute')
    assert '[SKIPPED:created_contract_touched]' in out
    assert Contract.objects.filter(pk=new.pk).exists()


def test_create_is_not_refused_when_a_zone_is_also_held_by_another_live_contract(tmp_path):
    company = _company()
    old = _contract(company, status='Expired', start=date(2025, 3, 1))
    sister = _contract(company, status='Active', start=date(2024, 6, 1), end=date(2025, 5, 31))
    zone, _ = _zone_link(old)
    ContractZone.objects.create(contract=sister, zone=zone, start_date=sister.start_date)
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert '[APPLIED]' in out
    new = _created_for(old)
    assert list(ContractZone.objects.filter(contract=new).values_list('zone_id', flat=True)) == [zone.pk]
    assert ContractZone.objects.filter(contract=sister, zone=zone, is_active=True).exists()
    zone.refresh_from_db()
    assert zone.status == 'online'


# --- cross-entry and revert safety (independent review, 2026-11-14) ------------------------------

def test_two_creates_in_one_group_for_the_same_company_are_refused(tmp_path):
    company = _company()
    old_a = _contract(company, status='Expired', start=date(2025, 1, 1))
    old_b = _contract(company, status='Expired', start=date(2025, 2, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old_a, group='G:x'), _create(old_b, group='G:x')]))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert not Contract.objects.filter(company=company, status='Active').exists()
    assert {_status(old_a), _status(old_b)} == {'Expired'}


def test_two_creates_in_one_group_for_a_company_and_its_twin_are_refused(tmp_path):
    company, twin = _company(), _company()
    old_a = _contract(company, status='Expired', start=date(2025, 1, 1))
    old_b = _contract(twin, status='Expired', start=date(2025, 1, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old_a, group='G:t', twins=[twin]), _create(old_b, group='G:t')]))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert not Contract.objects.filter(company__in=[company, twin], status='Active').exists()


def test_overlapping_creates_in_two_groups_refuse_both_groups(tmp_path):
    company, twin = _company(), _company()
    old_a = _contract(company, status='Expired', start=date(2025, 1, 1))
    old_b = _contract(twin, status='Expired', start=date(2025, 1, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_create(old_a, group='G:1'), _create(old_b, group='G:2', twins=[company])]))
    assert out.count('[SKIPPED:planned_terms_overlap]') == 2
    assert not Contract.objects.filter(company__in=[company, twin], status='Active').exists()


def test_creates_for_one_company_with_consecutive_terms_both_apply(tmp_path):
    company = _company()
    old_a = _contract(company, status='Expired', start=date(2025, 1, 1))
    old_b = _contract(company, status='Expired', start=date(2025, 2, 1))
    entries = [_create(old_a, group='G:1'),
               _create(old_b, group='G:2', start_date='2027-03-01', end_date='2028-02-29')]
    out, _ = _execute(tmp_path, _file(tmp_path, entries))
    assert out.count('[APPLIED]') == 2


def test_a_contract_relied_on_by_one_group_cannot_be_changed_by_another(tmp_path):
    company = _company()
    old = _contract(company, status='Active', start=date(2025, 1, 1))
    succ = _contract(company, status='Active', start=date(2026, 1, 1))
    out, _ = _execute(tmp_path, _file(tmp_path, [_renewed(old, succ, group='E:1'), _cancel(succ, group='D:1', cls='D')]))
    assert out.count('[SKIPPED:contract_in_two_groups]') == 2
    assert (_status(old), _status(succ)) == ('Active', 'Active')


def test_a_link_target_cannot_be_changed_by_another_group(tmp_path):
    company = _company()
    placeholder = _contract(company, status='Active', start=date(2024, 1, 1))
    current = _contract(company, start=date(2025, 6, 1))
    other = _contract(company, start=date(2026, 6, 1))
    out = _run('--file', _file(tmp_path, [_link(current, placeholder, 'E:1', 'E'), _renewed(placeholder, other, 'E:2', 'E')]))
    assert out.count('[SKIPPED:contract_in_two_groups]') == 2


def test_set_renewed_from_rechecks_the_predecessor_under_lock(tmp_path):
    company = _company()
    placeholder = _contract(company, status='Expired')
    current = _contract(company, start=date(2025, 6, 1))
    path = _file(tmp_path, [_link(current, placeholder)])
    Contract.objects.filter(pk=placeholder.pk).update(status='Cancelled')
    out, _ = _execute(tmp_path, path)
    assert '[SKIPPED:predecessor_changed]' in out
    current.refresh_from_db()
    assert current.renewed_from_id is None


def test_revert_of_a_cancel_is_skipped_when_the_zone_was_linked_elsewhere(tmp_path):
    company = _company()
    c = _contract(company, status='Active', start=date(2025, 1, 1))
    zone, link = _zone_link(c)
    _, journal = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    new = _contract(company, status='Active', start=date(2026, 1, 1))
    ContractZone.objects.create(contract=new, zone=zone, start_date=new.start_date)
    Zone.objects.filter(pk=zone.pk).update(status='online')
    out = _run('--revert', journal, '--execute')
    assert '[SKIPPED:changed_since_apply]' in out
    assert ContractZone.objects.filter(zone=zone, is_active=True).count() == 1
    assert _status(c) == 'Cancelled'


def test_a_stale_link_that_existed_before_the_run_does_not_block_the_revert(tmp_path):
    company = _company()
    legacy = _contract(company, status='Cancelled', start=date(2023, 1, 1), is_active=False)
    c = _contract(company, status='Active', start=date(2025, 1, 1))
    zone, link = _zone_link(c)
    stale = ContractZone.objects.create(contract=legacy, zone=zone, start_date=legacy.start_date)  # still active
    out, journal = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    assert '[APPLIED]' in out
    op = json.loads(open(journal).read())['groups'][0]['ops'][0]
    assert op['zones'][0]['other_active_links'] == [str(stale.pk)]
    out = _run('--revert', journal, '--execute')
    assert '[REVERTED]' in out
    link.refresh_from_db()
    stale.refresh_from_db()
    assert link.is_active is True and stale.is_active is True  # the stale link is left as it was
    assert _status(c) == 'Active'


def test_a_link_added_after_the_run_still_blocks_the_revert_next_to_a_stale_one(tmp_path):
    company = _company()
    legacy = _contract(company, status='Cancelled', start=date(2023, 1, 1), is_active=False)
    c = _contract(company, status='Active', start=date(2025, 1, 1))
    zone, _ = _zone_link(c)
    ContractZone.objects.create(contract=legacy, zone=zone, start_date=legacy.start_date)
    _, journal = _execute(tmp_path, _file(tmp_path, [_cancel(c)]))
    new = _contract(company, status='Active', start=date(2026, 1, 1))
    ContractZone.objects.create(contract=new, zone=zone, start_date=new.start_date)
    assert '[SKIPPED:changed_since_apply]' in _run('--revert', journal, '--execute')


def _flaky_commit(really_commit):
    real_commit = connection.commit

    def commit():
        if really_commit:
            real_commit()
        raise OperationalError('server closed the connection unexpectedly')
    return commit


@pytest.mark.django_db(transaction=True)
def test_an_error_at_commit_keeps_the_journal_entry_for_a_group_that_committed(tmp_path):
    c = _contract(_company(), status='Active', start=date(2025, 1, 1))
    path = _file(tmp_path, [_cancel(c)])
    with mock.patch.object(connection, 'commit', side_effect=_flaky_commit(True)):
        out, journal_path = _execute(tmp_path, path)
    assert '[COMMIT-UNCERTAIN:commit_uncertain(OperationalError)]' in out
    assert 'WARNING: 1 group(s) hit an error at COMMIT' in out
    group = json.loads(open(journal_path).read())['groups'][0]
    assert group['commit_uncertain'] is True
    assert _status(c) == 'Cancelled'  # it did commit
    assert '[REVERTED]' in _run('--revert', journal_path, '--execute')
    assert _status(c) == 'Active'


@pytest.mark.django_db(transaction=True)
def test_an_error_at_commit_for_a_group_that_did_not_commit_reverts_nothing(tmp_path):
    c = _contract(_company(), status='Active', start=date(2025, 1, 1))
    path = _file(tmp_path, [_cancel(c)])
    with mock.patch.object(connection, 'commit', side_effect=_flaky_commit(False)):
        out, journal_path = _execute(tmp_path, path)
    assert '[COMMIT-UNCERTAIN:' in out
    assert json.loads(open(journal_path).read())['groups'][0]['commit_uncertain'] is True
    assert _status(c) == 'Active'  # rolled back
    out = _run('--revert', journal_path, '--execute')
    assert '[ALREADY-REVERTED]' in out
    assert not AuditLog.objects.filter(additional_data__mode='revert').exists()


def test_pricing_check_follows_the_pdf_guard(tmp_path):
    rows = [{'location_name': 'Zone 1', 'platform': 'soundtrack', 'price': '100.00'}]
    shown = _contract(_company(), status='Expired', show_zone_pricing_detail=True)
    hidden = _contract(_company(), status='Expired', show_zone_pricing_detail=False)
    path = _file(tmp_path, [_create(shown, group='G:1', service_locations=rows),
                            _create(hidden, group='G:2', service_locations=rows)])
    out, _ = _execute(tmp_path, path)
    assert '[SKIPPED:service_location_pricing_mismatch]' in out  # per-zone prices shown on the PDF
    assert out.count('[APPLIED]') == 1                             # hidden: the PDF guard accepts it
    assert _created_for(hidden) is not None and _created_for(shown) is None


def test_journal_holds_the_group_before_commit_and_a_failed_write_rolls_back(tmp_path):
    old = _contract(_company(), status='Expired')
    with mock.patch.object(cmd, '_write_json_atomic', side_effect=[None, OSError('disk full')]):
        out, _ = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    assert '[SKIPPED:journal_write_failed]' in out
    assert _created_for(old) is None and _status(old) == 'Expired'
    assert not _audits().exists()


# --- file handling ---------------------------------------------------------------------------

def test_duplicate_contract_in_file_refuses_both_groups(tmp_path):
    c = _contract(_company(), status='Sent')
    out = _run('--file', _file(tmp_path, [_cancel(c, 'D:1'), _cancel(c, 'D:2')]))
    assert out.count('[SKIPPED:duplicate_contract_id]') == 2


def test_only_class_filters_v2_labels(tmp_path):
    a = _contract(_company(), status='Sent')
    b = _contract(_company(), status='Sent')
    out, _ = _execute(tmp_path, _file(tmp_path, [_cancel(a, 'D:1', 'D'), _cancel(b, 'X:1', 'X')]))
    assert out.count('[APPLIED]') == 2
    c = _contract(_company(), status='Sent')
    d = _contract(_company(), status='Sent')
    out = _run('--file', _file(tmp_path, [_cancel(c, 'D:1', 'D'), _cancel(d, 'X:1', 'X')], 'b.json'),
               '--only-class', 'X')
    assert out.count('[WOULD-APPLY]') == 1 and 'not selected by --only-class: 1 entries' in out


def test_v1_rejects_unknown_only_class(tmp_path):
    path = tmp_path / 'v1.json'
    path.write_text(json.dumps({'format': cmd.FILE_FORMAT, 'entries': [{
        'contract_id': '00000000-0000-4000-8000-0000000000aa', 'class': 'C', 'group': 'C:1',
        'expected': {'status': 'Sent', 'start_date': '2026-01-01', 'end_date': None,
                     'updated_at': '2026-01-01T00:00:00+07:00'},
        'target_status': 'Active', 'evidence': 'x'}]}))
    with pytest.raises(CommandError, match='v1 classes'):
        _run('--file', str(path), '--only-class', 'D')


def _valid_create():
    return {
        'op': 'create_successor', 'class': 'G', 'group': 'G:1',
        'old_contract_id': '00000000-0000-4000-8000-0000000000aa',
        'old_expected': {'status': 'Expired', 'start_date': '2025-01-01', 'end_date': '2025-12-31',
                         'updated_at': '2026-01-01T00:00:00+00:00'},
        'new': _new_term(), 'evidence': 'Sheet / Tab / row 1',
    }


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(op='delete'), 'op must be'),
    (lambda e: e.update(extra=1), 'unknown keys'),
    (lambda e: e.pop('evidence'), 'missing keys'),
    (lambda e: e.update({'class': 'lower'}), 'class must match'),
    (lambda e: e['new'].update(status='Draft'), 'must be Active'),
    (lambda e: e['new'].update(end_date='2026-01-01'), 'before start_date'),
    (lambda e: e['new'].update(start_date='2024-12-01', end_date='2025-11-30'), 'must not start before'),
    (lambda e: e['new'].update(value='12.345'), 'at most 2 decimals'),
    (lambda e: e['new'].update(value=900), 'decimal string'),
    (lambda e: e['new'].update(currency='EUR'), 'currency'),
    (lambda e: e['new'].update(service_type='gold'), 'service type'),
    (lambda e: e['new'].update(service_locations=[]), 'service_locations'),
    (lambda e: e['new']['service_locations'][0].update(platform='spotify'), 'platform'),
    (lambda e: e['new']['service_locations'][0].update(platform='custom'), 'custom_service_name'),
    (lambda e: e['new'].update(notes='x' * 1001), 'notes'),
    (lambda e: e['new'].update(auto_renew='yes'), 'auto_renew'),
    (lambda e: e['new'].pop('notes'), 'missing keys'),
    (lambda e: e.update(twin_company_ids='abc'), 'twin_company_ids'),
    (lambda e: e['old_expected'].update(updated_at='2026-01-01T00:00:00'), 'no UTC offset'),
])
def test_malformed_v2_entry_exits_non_zero(tmp_path, mutate, message):
    entry = _valid_create()
    mutate(entry)
    with pytest.raises(CommandError, match=message):
        _run('--file', _file(tmp_path, [entry]))


def test_v2_group_mixing_classes_is_malformed(tmp_path):
    a = _contract(_company(), status='Sent')
    b = _contract(_company(), status='Sent')
    with pytest.raises(CommandError, match='mixes classes'):
        _run('--file', _file(tmp_path, [_cancel(a, 'D:1', 'D'), _cancel(b, 'D:1', 'E')]))


# --- no email, no external call ------------------------------------------------------------

def test_no_email_and_no_external_call(tmp_path):
    company = _company()
    cancel_me = _contract(company, status='Active')
    _zone_link(cancel_me)
    placeholder = _contract(company, status='Active', start=date(2024, 1, 1), end=date(2024, 12, 31))
    current = _contract(company, start=date(2024, 6, 1), end=date(2025, 5, 31))
    old = _contract(_company(), status='Expired')
    path = _file(tmp_path, [_cancel(cancel_me, 'D:1', 'D'), _link(current, placeholder, 'E:1'),
                            _renewed(placeholder, current, 'E:1'), _create(old, 'G:1')])

    def no_network(*args, **kwargs):
        raise AssertionError('external call attempted')

    with mock.patch('crm_app.services.soundtrack_api.SoundtrackAPIService.sync_company_zones') as sync_zones, \
            mock.patch('crm_app.services.email_service.EmailService.send_email', side_effect=no_network), \
            mock.patch('requests.sessions.Session.request', side_effect=no_network), \
            mock.patch('urllib.request.urlopen', side_effect=no_network), \
            mock.patch('smtplib.SMTP', side_effect=no_network), \
            mock.patch('smtplib.SMTP_SSL', side_effect=no_network):
        out, journal_path = _execute(tmp_path, path)
        assert out.count('[APPLIED]') == 4
        assert _run('--revert', journal_path, '--execute').count('[REVERTED]') == 4

    assert mail.outbox == []
    sync_zones.assert_not_called()
