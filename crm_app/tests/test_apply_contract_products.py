"""apply_contract_products: additive product/zone back-fill of contract service-location rows.

Covers dry-run and execute, every refusal reason, the PDF pricing guard, the Player Box rule,
idempotent re-runs, the journal and --revert (only rows the run created are removed), audit rows,
that the row digest matches the REST representation, rollback on a failed write, and that nothing
emails or calls out. All data is synthetic. No test relies on primary-key order or values.
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
from django.db import DatabaseError

from crm_app.management.commands import apply_contract_products as cmd
from crm_app.models import AuditLog, Company, Contract, ContractLineItem, ContractServiceLocation
from crm_app.serializers import ContractSerializer

pytestmark = pytest.mark.django_db
_numbers = iter(range(1, 100_000))
START = date(2026, 1, 1)


# --- fixtures ------------------------------------------------------------------

def _company():
    return Company.objects.create(name=f'Products fixture company {next(_numbers)}',
                                  billing_entity='BMAsia Limited')


def _contract(status='Active', **extra):
    values = dict(
        company=_company(), contract_number=f'TEST-PZ-{next(_numbers):05d}', status=status,
        start_date=START, end_date=START + timedelta(days=364),
        value=Decimal('1200.00'), total_value=Decimal('1200.00'), is_active=True,
    )
    values.update(extra)
    return Contract.objects.create(**values)


def _row(contract, name='Lobby', platform='soundtrack', custom='', sort_order=0, price=None):
    return ContractServiceLocation.objects.create(
        contract=contract, location_name=name, platform=platform, custom_service_name=custom,
        sort_order=sort_order, price=price)


def _rows(contract):
    return list(ContractServiceLocation.objects.filter(contract=contract))


def _expected(contract):
    contract.refresh_from_db()
    rows = _rows(contract)
    return {
        'status': contract.status,
        'start_date': contract.start_date.isoformat(),
        'end_date': contract.end_date.isoformat() if contract.end_date else None,
        'updated_at': contract.updated_at.isoformat(),
        'service_type': contract.service_type or '',
        'service_locations': {'count': len(rows), 'digest': cmd.rows_digest([cmd._row_tuple(r) for r in rows])},
    }


def _entry(contract, add=None, set_platform=None, service_type=None):
    entry = {'contract_id': str(contract.pk), 'evidence': 'Fixture sheet / Tab / row 7', 'expected': _expected(contract)}
    if add is not None:
        entry['add_locations'] = add
    if set_platform is not None:
        entry['set_platform'] = set_platform
    if service_type is not None:
        entry['set_service_type'] = service_type
    return entry


def _add(*names, platform='soundtrack', start=0):
    return [{'location_name': n, 'platform': platform, 'sort_order': start + i} for i, n in enumerate(names)]


def _file(tmp_path, entries, name='products.json'):
    path = tmp_path / name
    path.write_text(json.dumps({'format': cmd.FILE_FORMAT, 'source': 'fixture', 'entries': entries}))
    return str(path)


def _run(*args):
    out = StringIO()
    call_command('apply_contract_products', *args, stdout=out)
    return out.getvalue()


def _execute(tmp_path, path, journal='journal.json'):
    journal_path = str(tmp_path / journal)
    return _run('--file', path, '--execute', '--journal', journal_path), journal_path


def _audits(contract=None):
    qs = AuditLog.objects.filter(model_name='Contract', additional_data__command=cmd.COMMAND)
    if contract is not None:
        qs = qs.filter(record_id=str(contract.pk))
    return qs


# --- dry-run and execute -----------------------------------------------------------

def test_dry_run_writes_nothing(tmp_path):
    c = _contract()
    before = _expected(c)
    out = _run('--file', _file(tmp_path, [_entry(c, add=_add('Lobby', 'Pool'))]))
    assert '[WOULD-APPLY]' in out and 'zones 0 -> 2' in out
    assert _rows(c) == [] and _expected(c) == before and not _audits().exists()


def test_execute_adds_rows_and_keeps_existing(tmp_path):
    c = _contract()
    keep = _row(c, 'Restaurant', sort_order=0, price=Decimal('600.00'))
    c.value = Decimal('1800.00')
    c.save()
    old_updated = _expected(c)['updated_at']
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_entry(c, add=_add('Lobby', 'Pool', start=1))]))
    assert '[APPLIED]' in out
    rows = {r.location_name: r for r in _rows(c)}
    assert set(rows) == {'Restaurant', 'Lobby', 'Pool'}
    assert rows['Restaurant'].id == keep.id and rows['Restaurant'].price == Decimal('600.00')
    assert rows['Lobby'].platform == 'soundtrack' and rows['Lobby'].price is None
    assert [rows['Lobby'].sort_order, rows['Pool'].sort_order] == [1, 2]
    c.refresh_from_db()
    assert c.updated_at.isoformat() != old_updated and c.value == Decimal('1800.00')
    assert ContractSerializer(c).data['total_zone_count'] == 3
    audit = _audits(c).get()
    assert audit.changes['service_locations']['old']['count'] == 1
    assert audit.changes['service_locations']['new']['count'] == 3
    assert len(audit.additional_data['created_row_ids']) == 2 and audit.additional_data['evidence']
    journal = json.loads(open(journal_path).read())
    assert journal['format'] == cmd.JOURNAL_FORMAT and len(journal['contracts']) == 1
    assert {r['location_name'] for r in journal['contracts'][0]['created_rows']} == {'Lobby', 'Pool'}


def test_set_platform_keeps_row_identity(tmp_path):
    c = _contract()
    r = _row(c, 'Lobby', platform='custom', custom='Beat Breeze', sort_order=3, price=Decimal('1200.00'))
    _execute(tmp_path, _file(tmp_path, [_entry(c, set_platform=[{'id': str(r.id), 'from': 'custom', 'to': 'beatbreeze'}])]))
    r2 = ContractServiceLocation.objects.get(id=r.id)
    assert r2.platform == 'beatbreeze'
    assert (r2.location_name, r2.custom_service_name, r2.sort_order, r2.price) == (
        'Lobby', 'Beat Breeze', 3, Decimal('1200.00'))
    assert _audits(c).get().additional_data['platform_changes'] == [
        {'id': str(r.id), 'old': 'custom', 'new': 'beatbreeze'}]


def test_set_service_type(tmp_path):
    c = _contract()
    _execute(tmp_path, _file(tmp_path, [_entry(c, add=_add('Lobby'), service_type='soundtrack_unlimited_yearly')]))
    c.refresh_from_db()
    assert c.service_type == 'soundtrack_unlimited_yearly'
    assert _audits(c).get().changes['service_type'] == {'old': '', 'new': 'soundtrack_unlimited_yearly'}


def test_player_box_rule_refuses_beat_breeze_variant(tmp_path):
    c = _contract()
    ContractLineItem.objects.create(contract=c, product_service='Player Box', description='',
                                    quantity=1, unit_price=Decimal('100'), line_total=Decimal('100'))
    out = _run('--file', _file(tmp_path, [_entry(c, service_type='beat_breeze_yearly')]))
    assert '[SKIPPED:player_box_variant]' in out


# --- pricing guard ------------------------------------------------------------------

def test_pricing_guard_refuses_contradicting_rows(tmp_path):
    c = _contract(price_per_zone=Decimal('600.00'), value=Decimal('600.00'), show_zone_pricing_detail=True)
    out, _ = _execute(tmp_path, _file(tmp_path, [_entry(c, add=_add('Lobby', 'Pool'))]))
    assert '[SKIPPED:pdf_pricing_guard]' in out and _rows(c) == [] and not _audits().exists()


def test_pricing_guard_passes_when_rows_reconcile(tmp_path):
    c = _contract(price_per_zone=Decimal('600.00'), value=Decimal('1200.00'), show_zone_pricing_detail=True)
    out, _ = _execute(tmp_path, _file(tmp_path, [_entry(c, add=_add('Lobby', 'Pool'))]))
    assert '[APPLIED]' in out and len(_rows(c)) == 2


# --- refusals -------------------------------------------------------------------------

def _refusal(tmp_path, entry_fn, mutate):
    c = _contract()
    existing = _row(c, 'Lobby', platform='custom', custom='Beat Breeze')
    entry = entry_fn(c, existing)
    path = _file(tmp_path, [entry])
    mutate(c, existing)
    before_rows = sorted((str(r.id), r.platform, r.location_name) for r in _rows(c))
    out, _ = _execute(tmp_path, path)
    assert sorted((str(r.id), r.platform, r.location_name) for r in _rows(c)) == before_rows
    assert not _audits().exists()
    return out


def _bump(c):
    Contract.objects.filter(pk=c.pk).update(notes='edited elsewhere')
    c.refresh_from_db()
    c.save()


@pytest.mark.parametrize('mutate, reason', [
    (lambda c, r: Contract.objects.filter(pk=c.pk).update(status='Renewed'), 'status_changed'),
    (lambda c, r: Contract.objects.filter(pk=c.pk).update(end_date=date(2027, 6, 30)), 'dates_changed'),
    (lambda c, r: _bump(c), 'updated_at_changed'),
    (lambda c, r: Contract.objects.filter(pk=c.pk).update(service_type='custom_package'), 'service_type_changed'),
    (lambda c, r: ContractServiceLocation.objects.filter(id=r.id).update(location_name='Renamed'),
     'service_locations_changed'),
    (lambda c, r: _row(c, 'Another'), 'service_locations_changed'),
    (lambda c, r: ContractServiceLocation.objects.filter(id=r.id).update(platform='soundtrack'),
     'service_locations_changed'),
])
def test_refusals_on_drift(tmp_path, mutate, reason):
    out = _refusal(tmp_path, lambda c, r: _entry(c, add=_add('Pool', start=1),
                                                set_platform=[{'id': str(r.id), 'from': 'custom', 'to': 'beatbreeze'}]),
                   mutate)
    assert f'[SKIPPED:{reason}]' in out


def test_refuses_row_of_another_contract(tmp_path):
    other = _contract()
    foreign = _row(other, 'Elsewhere', platform='custom', custom='Beat Breeze')
    out = _refusal(tmp_path, lambda c, r: _entry(c, set_platform=[{'id': str(foreign.id), 'from': 'custom',
                                                                     'to': 'beatbreeze'}]),
                   lambda c, r: None)
    assert '[SKIPPED:row_not_on_contract]' in out
    assert ContractServiceLocation.objects.get(id=foreign.id).platform == 'custom'


def test_refuses_when_from_platform_differs(tmp_path):
    out = _refusal(tmp_path, lambda c, r: _entry(c, set_platform=[{'id': str(r.id), 'from': 'soundtrack',
                                                                     'to': 'beatbreeze'}]),
                   lambda c, r: None)
    assert '[SKIPPED:platform_differs_from_file]' in out


def test_missing_and_duplicate_contracts(tmp_path):
    c = _contract()
    ghost = _entry(c, add=_add('Lobby'))
    ghost['contract_id'] = '00000000-0000-4000-8000-00000000abcd'
    dup = _entry(c, add=_add('Lobby'))
    out, _ = _execute(tmp_path, _file(tmp_path, [ghost, dup, dict(dup)]))
    assert '[SKIPPED:missing_contract]' in out and out.count('[SKIPPED:duplicate_contract_id]') == 2
    assert _rows(c) == []


def test_failed_write_rolls_back_the_contract(tmp_path):
    c = _contract()
    real_create = ContractServiceLocation.objects.create
    calls = {'n': 0}

    def flaky(**kwargs):
        calls['n'] += 1
        if calls['n'] == 2:
            raise DatabaseError('boom')
        return real_create(**kwargs)

    with mock.patch.object(ContractServiceLocation.objects, 'create', side_effect=flaky):
        out, _ = _execute(tmp_path, _file(tmp_path, [_entry(c, add=_add('Lobby', 'Pool'))]))
    assert '[SKIPPED:write_failed(DatabaseError)]' in out
    assert _rows(c) == [] and not _audits().exists()


# --- idempotence ----------------------------------------------------------------------

def test_rerun_is_already_applied(tmp_path):
    c = _contract()
    r = _row(c, 'Lobby', platform='custom', custom='Beat Breeze')
    path = _file(tmp_path, [_entry(c, add=_add('Pool', 'Lobby', platform='beatbreeze', start=1),
                                   set_platform=[{'id': str(r.id), 'from': 'custom', 'to': 'beatbreeze'}],
                                   service_type='beat_breeze_yearly')])
    _execute(tmp_path, path)
    out, _ = _execute(tmp_path, path, journal='journal2.json')
    assert '[ALREADY-APPLIED]' in out
    assert len(_rows(c)) == 3 and _audits(c).count() == 1
    assert _run('--file', path).count('[ALREADY-APPLIED]') == 1


# --- revert ---------------------------------------------------------------------------

def _applied(tmp_path):
    c = _contract()
    pre = _row(c, 'Lobby', platform='custom', custom='Beat Breeze', price=Decimal('1200.00'))
    c.value = Decimal('1200.00')
    c.save()
    _, journal = _execute(tmp_path, _file(tmp_path, [_entry(
        c, add=_add('Pool', platform='beatbreeze', start=1),
        set_platform=[{'id': str(pre.id), 'from': 'custom', 'to': 'beatbreeze'}],
        service_type='beat_breeze_yearly')]))
    return c, pre, journal


def test_revert_dry_run_then_execute(tmp_path):
    c, pre, journal = _applied(tmp_path)
    assert '[WOULD-REVERT]' in _run('--revert', journal)
    assert len(_rows(c)) == 2
    out = _run('--revert', journal, '--execute')
    assert '[REVERTED]' in out
    rows = _rows(c)
    assert [r.id for r in rows] == [pre.id] and rows[0].platform == 'custom'
    c.refresh_from_db()
    assert c.service_type == ''
    revert_audit = _audits(c).filter(additional_data__mode='revert').get()
    assert len(revert_audit.additional_data['deleted_row_ids']) == 1
    assert '[ALREADY-REVERTED]' in _run('--revert', journal, '--execute')


@pytest.mark.parametrize('touch', [
    lambda c, pre: _bump(c),
    lambda c, pre: _row(c, 'Added by hand', sort_order=9),
    lambda c, pre: ContractServiceLocation.objects.filter(id=pre.id).update(location_name='Renamed by hand'),
])
def test_revert_refuses_when_touched_since(tmp_path, touch):
    c, pre, journal = _applied(tmp_path)
    touch(c, pre)
    count = len(_rows(c))
    out = _run('--revert', journal, '--execute')
    assert '[SKIPPED:changed_since_apply]' in out and len(_rows(c)) == count


# --- argument handling and malformed files -------------------------------------------

def test_execute_requires_new_journal(tmp_path):
    path = _file(tmp_path, [_entry(_contract(), add=_add('Lobby'))])
    with pytest.raises(CommandError, match='requires --journal'):
        _run('--file', path, '--execute')
    existing = tmp_path / 'taken.json'
    existing.write_text('{}')
    with pytest.raises(CommandError, match='already exists'):
        _run('--file', path, '--execute', '--journal', str(existing))
    with pytest.raises(CommandError, match='only used with --execute'):
        _run('--file', path, '--journal', str(tmp_path / 'j.json'))


def _valid_entry():
    return {
        'contract_id': '00000000-0000-4000-8000-0000000000aa', 'evidence': 'Sheet / Tab / row 1',
        'expected': {'status': 'Active', 'start_date': '2026-01-01', 'end_date': None,
                     'updated_at': '2026-01-01T00:00:00+07:00', 'service_type': '',
                     'service_locations': {'count': 0, 'digest': '0' * 64}},
        'add_locations': [{'location_name': 'Lobby', 'platform': 'soundtrack', 'sort_order': 0}],
    }


@pytest.mark.parametrize('mutate, message', [
    (lambda e: e.update(company='x'), 'unknown keys'),
    (lambda e: e.pop('evidence'), 'missing keys'),
    (lambda e: e.update(contract_id='nope'), 'not a UUID'),
    (lambda e: e.pop('add_locations'), 'no operation'),
    (lambda e: e['expected'].update(updated_at='2026-01-01T00:00:00'), 'no UTC offset'),
    (lambda e: e['expected'].update(service_type='syb'), 'service_type'),
    (lambda e: e['expected']['service_locations'].update(digest='abc'), 'service_locations'),
    (lambda e: e['add_locations'][0].update(platform='custom'), 'platform must be'),
    (lambda e: e['add_locations'][0].update(location_name=''), 'location_name'),
    (lambda e: e['add_locations'][0].update(location_name='x' * 201), 'location_name'),
    (lambda e: e['add_locations'][0].update(sort_order=-1), 'sort_order'),
    (lambda e: e.update(set_platform=[{'id': '00000000-0000-4000-8000-0000000000bb', 'to': 'beatbreeze'}]),
     'needs exactly id, from, to'),
    (lambda e: e.update(set_platform=[{'id': '00000000-0000-4000-8000-0000000000bb', 'from': 'custom',
                                       'to': 'custom'}]), 'from must be'),
    (lambda e: e.update(set_service_type='spotify'), 'not a service_type choice'),
    (lambda e: e.update(set_service_type=''), 'not a service_type choice'),
    (lambda e: e.update(evidence='two\nlines'), 'evidence'),
])
def test_malformed_files_stop_before_reading_the_database(tmp_path, mutate, message):
    entry = _valid_entry()
    mutate(entry)
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps({'format': cmd.FILE_FORMAT, 'entries': [entry]}))
    with mock.patch.object(Contract.objects, 'select_for_update', side_effect=AssertionError('db read')):
        with pytest.raises(CommandError, match=message):
            _run('--file', str(path))


def test_multiline_location_name_is_allowed():
    entry = _valid_entry()
    entry['add_locations'][0]['location_name'] = 'Lobby\nPool'
    entries, _ = cmd.parse_products({'format': cmd.FILE_FORMAT, 'entries': [entry]})
    assert entries[0].add[0]['location_name'] == 'Lobby\nPool'


# --- digest compatibility --------------------------------------------------------------

def test_digest_matches_rest_representation():
    c = _contract()
    _row(c, 'Pool', sort_order=2, price=Decimal('14000'))
    _row(c, 'Lobby', platform='custom', custom='Beat Breeze', sort_order=1)
    api_rows = ContractSerializer(c).data['service_locations']
    from_api = cmd.rows_digest([(r['id'], r['location_name'], r['platform'], r.get('custom_service_name'),
                                 r['sort_order'], r['price']) for r in api_rows])
    from_db = cmd.rows_digest([cmd._row_tuple(r) for r in _rows(c)])
    assert from_api == from_db
    assert cmd.rows_digest(list(reversed([cmd._row_tuple(r) for r in _rows(c)]))) == from_db


# --- no email, no external call ------------------------------------------------------

def test_no_email_and_no_external_call(tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError('external call attempted')

    with mock.patch('crm_app.services.soundtrack_api.SoundtrackAPIService.sync_company_zones') as sync_zones, \
            mock.patch('crm_app.models.Zone.mark_as_cancelled') as cancel_zone, \
            mock.patch('crm_app.services.email_service.EmailService.send_email', side_effect=no_network), \
            mock.patch('requests.sessions.Session.request', side_effect=no_network), \
            mock.patch('urllib.request.urlopen', side_effect=no_network), \
            mock.patch('smtplib.SMTP', side_effect=no_network), \
            mock.patch('smtplib.SMTP_SSL', side_effect=no_network):
        c, _, journal = _applied(tmp_path)
        _run('--revert', journal, '--execute')
    assert mail.outbox == []
    sync_zones.assert_not_called()
    cancel_zone.assert_not_called()
    company = Company.objects.get(pk=c.company_id)
    assert company.contracted_product == '' and company.contracted_zone_count is None
