"""Zone links when a renewal takes over, when a contract is cancelled, and the
zone's current contract. Covers the lifecycle rule's hand-over (REST, the
duplicate_for_renewal path, dry-run), the cancel end date, the defined order of
Zone.get_current_link, the hand-over inside the v2 corrections command's
create_successor with its revert, the v2 link-repair ops hand_over_zone_links
and redate_zone_link_end with their reverts, and the v1 command's journal of
handed-over links. All data is synthetic.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.management.commands import apply_contract_corrections as cmd
from crm_app.models import AuditLog, Company, Contract, ContractZone, User, Zone
from crm_app.serializers import ZoneSerializer
from crm_app.services import contract_corrections_v2 as v2
from crm_app.services.contract_lifecycle import (
    ALREADY_RENEWED, CLOSED, PREDECESSOR_NOT_ACTIVE, close_renewed_predecessor,
)
from crm_app.views import ContractViewSet

_numbers = iter(range(1, 100_000))


# --- fixtures ------------------------------------------------------------------------

def _company():
    return Company.objects.create(name=f'Handover fixture company {next(_numbers)}', billing_entity='BMAsia Limited')


def _contract(company, status='Active', start=date(2025, 1, 1), end=None, renewed_from=None, **extra):
    values = dict(
        company=company, contract_number=f'TEST-ZH-{next(_numbers):05d}', status=status,
        start_date=start, end_date=end or start + timedelta(days=364),
        value=Decimal('1200.00'), total_value=Decimal('1200.00'), is_active=status == 'Active',
        renewed_from=renewed_from, currency='USD',
    )
    values.update(extra)
    return Contract.objects.create(**values)


def _zone(company, status='online'):
    return Zone.objects.create(company=company, name=f'Zone {next(_numbers)}', status=status)


def _link(contract, zone, start=None, **extra):
    return ContractZone.objects.create(contract=contract, zone=zone, start_date=start or contract.start_date, **extra)


def _user():
    return User.objects.create_user(username=f'handover-tester-{next(_numbers)}', role='Sales')


def _rest_patch(contract, patch):
    request = APIRequestFactory().patch(f'/api/v1/contracts/{contract.pk}/', patch, format='json')
    force_authenticate(request, user=_user())
    return ContractViewSet.as_view({'patch': 'partial_update'})(request, pk=str(contract.pk))


def _state(link):
    link.refresh_from_db()
    return link.is_active, link.end_date


def _rule_audit(predecessor):
    return AuditLog.objects.get(model_name='Contract', record_id=str(predecessor.pk), action='UPDATE',
                                additional_data__rule='renewed_predecessor_closed_on_successor_active')


def _two_terms(successor_status='Sent', successor_start=date(2026, 1, 1)):
    """An Active old term with zones A, B, C and a renewal holding A and B."""
    company = _company()
    old = _contract(company)
    new = _contract(company, status=successor_status, start=successor_start, renewed_from=old)
    za, zb, zc = _zone(company), _zone(company, status='offline'), _zone(company)
    la, lb, lc = _link(old, za), _link(old, zb), _link(old, zc)
    na, nb = _link(new, za), _link(new, zb)
    return old, new, (za, zb, zc), (la, lb, lc), (na, nb)


# --- lifecycle rule ------------------------------------------------------------------

def test_activation_hands_over_the_zones_the_renewal_holds_and_reports_the_rest():
    old, new, (za, zb, zc), (la, lb, lc), (na, nb) = _two_terms()
    response = _rest_patch(new, {'status': 'Active'})
    assert response.status_code == 200, response.data
    old.refresh_from_db()
    assert old.status == 'Renewed'
    assert _state(la) == (False, date(2025, 12, 31)) and _state(lb) == (False, date(2025, 12, 31))
    assert _state(lc) == (True, None)  # not taken over: stays open
    assert _state(na) == (True, None) and _state(nb) == (True, None)
    for z, status in ((za, 'online'), (zb, 'offline'), (zc, 'online')):
        z.refresh_from_db()
        assert z.status == status  # zone status untouched
    audit = _rule_audit(old)
    closed = audit.additional_data['zone_links_closed']
    assert sorted(r['id'] for r in closed) == sorted([str(la.pk), str(lb.pk)])
    assert all(r['end_date'] == '2025-12-31' for r in closed)
    assert audit.additional_data['zones_not_taken_over'] == [str(zc.pk)]
    assert AuditLog.objects.filter(record_id=str(old.pk), action='UPDATE').count() == 1


def test_dry_run_reports_the_hand_over_and_writes_nothing():
    old, new, _, (la, lb, lc), _ = _two_terms(successor_status='Active')
    result = close_renewed_predecessor(new, source='test', dry_run=True)
    assert result.outcome == CLOSED
    assert sorted(r['id'] for r in result.zone_links_closed) == sorted([str(la.pk), str(lb.pk)])
    assert len(result.zones_not_taken_over) == 1
    assert all(_state(link) == (True, None) for link in (la, lb, lc))
    old.refresh_from_db()
    assert old.status == 'Active'


def test_the_end_date_is_never_before_the_links_own_start():
    company = _company()
    old = _contract(company, start=date(2025, 1, 1))
    new = _contract(company, status='Active', start=date(2025, 1, 1), end=date(2026, 12, 31), renewed_from=old)
    zone = _zone(company)
    old_link, _ = _link(old, zone), _link(new, zone)
    assert close_renewed_predecessor(new, source='test').outcome == CLOSED
    assert _state(old_link) == (False, date(2025, 1, 1))


def test_a_predecessor_that_is_not_active_keeps_its_links():
    company = _company()
    for status, outcome in (('Cancelled', PREDECESSOR_NOT_ACTIVE), ('Renewed', ALREADY_RENEWED)):
        old = _contract(company, status=status, start=date(2024, 1, 1))
        new = _contract(company, status='Active', start=date(2025, 1, 1), renewed_from=old)
        zone = _zone(company)
        old_link, _ = _link(old, zone), _link(new, zone)
        assert close_renewed_predecessor(new, source='test').outcome == outcome
        assert _state(old_link) == (True, None)


def test_duplicate_for_renewal_then_activation_moves_every_zone():
    company = _company()
    old = _contract(company)
    zones = [_zone(company) for _ in range(2)]
    old_links = [_link(old, z) for z in zones]
    request = APIRequestFactory().post(f'/api/v1/contracts/{old.pk}/duplicate_for_renewal/')
    force_authenticate(request, user=_user())
    response = ContractViewSet.as_view({'post': 'duplicate_for_renewal'})(request, pk=str(old.pk))
    assert response.status_code == 201, response.data
    new = Contract.objects.get(pk=response.data['new_contract']['id'])
    assert all(_state(link) == (True, None) for link in old_links)  # a Draft takes nothing over
    assert _rest_patch(new, {'status': 'Active'}).status_code == 200
    new.refresh_from_db()
    assert all(_state(link) == (False, new.start_date - timedelta(days=1)) for link in old_links)
    assert all(z.get_active_contract() == new for z in zones)


# --- cancel end date -----------------------------------------------------------------

@pytest.mark.parametrize('term_end, expected', [
    (date(2025, 5, 30), date(2025, 5, 30)),      # term ended earlier: links end with the term
    (date(2099, 12, 31), None),                  # term still running: links end today
])
def test_cancel_closes_links_on_the_earlier_of_today_and_the_term_end(term_end, expected):
    company = _company()
    c = _contract(company, start=date(2024, 6, 1), end=term_end)
    link = _link(c, _zone(company))
    c.status = 'Cancelled'
    c.save()
    assert _state(link) == (False, expected or timezone.now().date())


def test_cancel_never_ends_a_link_before_it_started():
    company = _company()
    c = _contract(company, start=date(2024, 6, 1), end=date(2025, 5, 30))
    link = _link(c, _zone(company), start=date(2025, 7, 1))
    c.status = 'Cancelled'
    c.save()
    assert _state(link) == (False, date(2025, 7, 1))


# --- current contract ----------------------------------------------------------------

def test_the_current_contract_prefers_the_active_holder_whatever_the_row_order():
    company = _company()
    zone = _zone(company)
    new = _contract(company, start=date(2026, 1, 1))
    old = _contract(company, status='Renewed', start=date(2025, 1, 1))
    _link(new, zone)
    _link(old, zone, start=date(2027, 1, 1))  # a later link start must not beat the Active holder
    assert zone.get_active_contract() == new
    assert ZoneSerializer(zone).data['current_contract']['id'] == str(new.pk)


def test_without_an_active_holder_the_latest_link_wins():
    company = _company()
    zone = _zone(company)
    first = _contract(company, status='Expired', start=date(2023, 1, 1))
    second = _contract(company, status='Expired', start=date(2024, 1, 1))
    _link(second, zone)
    _link(first, zone)
    assert zone.get_active_contract() == second
    assert _zone(company).get_active_contract() is None


# --- v2 command helpers --------------------------------------------------------------

def _expected(contract):
    contract.refresh_from_db()
    return {'status': contract.status, 'start_date': contract.start_date.isoformat(),
            'end_date': contract.end_date.isoformat() if contract.end_date else None,
            'updated_at': contract.updated_at.isoformat()}


def _create(old, start='2026-01-01', end='2026-12-31'):
    return {'op': 'create_successor', 'class': 'G', 'group': f'G:{old.pk}', 'old_contract_id': str(old.pk),
            'old_expected': _expected(old), 'evidence': 'Fixture sheet / Tab / row 1',
            'new': {'status': 'Active', 'start_date': start, 'end_date': end, 'value': '1200.00',
                    'currency': 'USD', 'notes': 'fixture', 'service_locations': [
                        {'location_name': 'Lobby', 'platform': 'soundtrack', 'price': '1200.00'}]}}


def _handover(old, new, copy=None):
    entry = {'op': 'hand_over_zone_links', 'class': 'Z', 'group': f'Z:{old.pk}', 'contract_id': str(old.pk),
             'expected': _expected(old), 'successor_id': str(new.pk), 'successor_expected': _expected(new),
             'evidence': 'Fixture repair'}
    if copy is not None:
        entry['copy_missing_links'] = copy
    return entry


def _redate(c, closed_on='2026-11-14'):
    return {'op': 'redate_zone_link_end', 'class': 'Z', 'group': f'Z:{c.pk}', 'contract_id': str(c.pk),
            'expected': _expected(c), 'closed_on': closed_on, 'evidence': 'Fixture repair'}


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


# --- v2 create_successor -------------------------------------------------------------

@pytest.mark.parametrize('old_status', ['Active', 'Expired'])
def test_create_successor_hands_over_and_its_revert_reopens_the_old_links(tmp_path, old_status):
    company = _company()
    old = _contract(company, status=old_status)
    zones = [_zone(company) for _ in range(2)]
    links = [_link(old, z) for z in zones]
    out = _run('--file', _file(tmp_path, [_create(old)]))
    assert 'hands them over (old links end 2025-12-31)' in out
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)], 'b.json'))
    assert '[APPLIED] G create_successor' in out
    assert all(_state(link) == (False, date(2025, 12, 31)) for link in links)
    new = Contract.objects.get(renewed_from=old)
    assert all(z.get_active_contract() == new for z in zones)
    op = json.loads(open(journal_path).read())['groups'][0]['ops'][0]
    assert sorted(r['id'] for r in op['old_zone_links_closed']) == sorted(str(l.pk) for l in links)
    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] G create_successor' in out and '2 old zone link(s) reopened' in out
    assert all(_state(link) == (True, None) for link in links)
    assert not Contract.objects.filter(pk=new.pk).exists()
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path, '--execute')


def test_create_successor_revert_stops_when_a_released_zone_was_linked_elsewhere(tmp_path):
    company = _company()
    old = _contract(company)
    zone = _zone(company)
    link = _link(old, zone)
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    _link(_contract(_company(), start=date(2026, 6, 1)), zone)  # linked to another contract since
    out = _run('--revert', journal_path, '--execute')
    assert 'SKIPPED:changed_since_apply' in out
    assert _state(link) == (False, date(2025, 12, 31))
    assert Contract.objects.filter(renewed_from=old).exists()


def test_a_journal_without_hand_over_rows_still_reverts(tmp_path):
    company = _company()
    old = _contract(company, status='Expired')
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_create(old)]))
    journal = json.loads(open(journal_path).read())
    del journal['groups'][0]['ops'][0]['old_zone_links_closed']  # as written before this change
    old_path = tmp_path / 'old-journal.json'
    old_path.write_text(json.dumps(journal))
    assert '[REVERTED] G create_successor' in _run('--revert', str(old_path), '--execute')


# --- v2 hand_over_zone_links -----------------------------------------------------------

def _renewed_pair(new_links=True):
    company = _company()
    old = _contract(company, status='Renewed')
    new = _contract(company, start=date(2026, 1, 1), renewed_from=old)
    zones = [_zone(company) for _ in range(3)]
    old_links = [_link(old, z) for z in zones]
    new_links = [_link(new, z) for z in zones[:2]] if new_links else []
    return old, new, zones, old_links, new_links


def test_hand_over_closes_the_doubled_links_only_and_reverts(tmp_path):
    old, new, zones, (l1, l2, l3), _ = _renewed_pair()
    out = _run('--file', _file(tmp_path, [_handover(old, new)]))
    assert '[WOULD-APPLY] Z hand_over_zone_links' in out
    assert 'closes 2 link(s) of this contract (end 2025-12-31); 1 zone(s) not held by the renewal stay open' in out
    assert all(_state(l) == (True, None) for l in (l1, l2, l3))
    versions = (old.updated_at, new.updated_at)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_handover(old, new)], 'b.json'))
    assert '[APPLIED] Z hand_over_zone_links' in out
    assert _state(l1) == _state(l2) == (False, date(2025, 12, 31)) and _state(l3) == (True, None)
    old.refresh_from_db(), new.refresh_from_db()
    assert (old.updated_at, new.updated_at) == versions  # link-only: contracts untouched
    audit = AuditLog.objects.get(record_id=str(old.pk), additional_data__op='hand_over_zone_links')
    assert audit.additional_data['zones_not_taken_over'] == [str(zones[2].pk)]
    assert '[ALREADY-APPLIED]' in _run('--file', _file(tmp_path, [_handover(old, new)], 'c.json'))
    out = _run('--revert', journal_path, '--execute')
    assert '[REVERTED] Z hand_over_zone_links' in out and '2 zone link(s) reopened' in out
    assert all(_state(l) == (True, None) for l in (l1, l2, l3))
    assert '[ALREADY-REVERTED]' in _run('--revert', journal_path)


def test_hand_over_with_copy_moves_every_zone_and_reverts(tmp_path):
    old, new, zones, old_links, _ = _renewed_pair(new_links=False)
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_handover(old, new, copy=True)]))
    assert '[APPLIED] Z hand_over_zone_links' in out
    assert all(_state(l) == (False, date(2025, 12, 31)) for l in old_links)
    created = ContractZone.objects.filter(contract=new)
    assert sorted(c.zone_id for c in created) == sorted(z.pk for z in zones)
    assert all(c.start_date == date(2026, 1, 1) and c.is_active for c in created)
    assert all(z.get_active_contract() == new for z in zones)
    out = _run('--revert', journal_path, '--execute')
    assert '3 zone link(s) reopened; 3 link(s) on the renewal removed' in out
    assert not ContractZone.objects.filter(contract=new).exists()
    assert all(_state(l) == (True, None) for l in old_links)


def test_hand_over_without_copy_and_nothing_held_is_already_applied(tmp_path):
    old, new, _, old_links, _ = _renewed_pair(new_links=False)
    assert '[ALREADY-APPLIED]' in _run('--file', _file(tmp_path, [_handover(old, new)]))
    assert all(_state(l) == (True, None) for l in old_links)


def test_hand_over_refusals(tmp_path):
    old, new, zones, _, _ = _renewed_pair(new_links=False)
    other = _contract(old.company, status='Active', start=date(2026, 6, 1))
    _link(other, zones[0])
    out = _run('--file', _file(tmp_path, [_handover(old, new, copy=True)]))
    assert 'SKIPPED:zone_shared_with_live_contract' in out
    stranger = _contract(old.company, start=date(2026, 1, 1))
    assert 'SKIPPED:successor_renews_other_contract' in _run('--file', _file(tmp_path, [_handover(old, stranger)], 'b.json'))
    entry = _handover(old, new)
    Contract.objects.filter(pk=old.pk).update(updated_at=timezone.now())
    assert 'SKIPPED:updated_at_changed' in _run('--file', _file(tmp_path, [entry], 'c.json'))
    active_old = _contract(_company())
    active_new = _contract(active_old.company, start=date(2026, 1, 1), renewed_from=active_old)
    assert 'SKIPPED:transition_not_allowed' in _run('--file', _file(tmp_path, [_handover(active_old, active_new)], 'd.json'))


def test_hand_over_revert_stops_when_a_link_changed(tmp_path):
    old, new, _, (l1, _, _), _ = _renewed_pair()
    _, journal_path = _execute(tmp_path, _file(tmp_path, [_handover(old, new)]))
    ContractZone.objects.filter(pk=l1.pk).update(end_date=date(2025, 6, 30))
    assert 'SKIPPED:changed_since_apply' in _run('--revert', journal_path, '--execute')


# --- v2 redate_zone_link_end -----------------------------------------------------------

def test_redate_moves_only_the_links_closed_on_the_given_day_and_reverts(tmp_path):
    company = _company()
    c = _contract(company, status='Cancelled', start=date(2025, 6, 1), end=date(2026, 5, 30))
    today_link = _link(c, _zone(company), is_active=False, end_date=date(2026, 11, 14))
    earlier = _link(c, _zone(company), is_active=False, end_date=date(2026, 2, 1))
    late_start = _link(c, _zone(company), start=date(2026, 7, 1), is_active=False, end_date=date(2026, 11, 14))
    out = _run('--file', _file(tmp_path, [_redate(c)]))
    assert '2 closed link(s) end 2026-11-14 -> 2026-05-30, 2026-07-01' in out
    out, journal_path = _execute(tmp_path, _file(tmp_path, [_redate(c)], 'b.json'))
    assert '[APPLIED] Z redate_zone_link_end' in out
    assert _state(today_link) == (False, date(2026, 5, 30))
    assert _state(earlier) == (False, date(2026, 2, 1))
    assert _state(late_start) == (False, date(2026, 7, 1))
    assert '[ALREADY-APPLIED]' in _run('--file', _file(tmp_path, [_redate(c)], 'c.json'))
    out = _run('--revert', journal_path, '--execute')
    assert '2 zone link end date(s) restored' in out
    assert _state(today_link) == (False, date(2026, 11, 14)) and _state(late_start) == (False, date(2026, 11, 14))


def test_redate_needs_a_cancelled_contract(tmp_path):
    c = _contract(_company(), status='Active')
    assert 'SKIPPED:transition_not_allowed' in _run('--file', _file(tmp_path, [_redate(c)]))


def test_v2_cancel_then_revert_with_the_term_end_date(tmp_path):
    company = _company()
    c = _contract(company, start=date(2025, 6, 1), end=date(2026, 5, 30))
    zone = _zone(company)
    link = _link(c, zone)
    entry = {'op': 'mark_cancelled', 'class': 'D', 'group': 'D:1', 'contract_id': str(c.pk),
             'expected': _expected(c), 'evidence': 'Fixture'}
    _, journal_path = _execute(tmp_path, _file(tmp_path, [entry]))
    assert _state(link) == (False, date(2026, 5, 30))
    assert '[REVERTED] D mark_cancelled' in _run('--revert', journal_path, '--execute')
    assert _state(link) == (True, None)


# --- v1 command ----------------------------------------------------------------------

def test_v1_journal_carries_the_hand_over_and_revert_reopens_it(tmp_path):
    company = _company()
    old = _contract(company, start=date(2025, 11, 1))
    new = _contract(company, start=date(2026, 11, 1), renewed_from=old)
    zone = _zone(company)
    old_link, _ = _link(old, zone), _link(new, zone)
    old.refresh_from_db()
    entry = {'contract_id': str(old.pk), 'class': 'A', 'group': 'A:1', 'target_status': 'Renewed',
             'evidence': 'Fixture', 'expected': _expected(old)}
    path = tmp_path / 'v1.json'
    path.write_text(json.dumps({'format': cmd.FILE_FORMAT, 'entries': [entry]}))
    out, journal_path = _execute(tmp_path, str(path))
    assert '[APPLIED]' in out
    assert _state(old_link) == (False, date(2026, 10, 31))
    row = json.loads(open(journal_path).read())['groups'][0]['contracts'][0]
    assert [r['id'] for r in row['zone_links_closed']] == [str(old_link.pk)]
    assert '[REVERTED]' in _run('--revert', journal_path, '--execute')
    assert _state(old_link) == (True, None)
    old.refresh_from_db()
    assert old.status == 'Active'


# --- documents fall back to the links that covered the term ------------------------------

def _pdf_text(contract):
    from io import BytesIO
    from pypdf import PdfReader
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(
        username=f'handover-pdf-{next(_numbers)}', role='Admin', is_active=True))
    response = client.get(f'/api/v1/contracts/{contract.pk}/pdf/')
    assert response.status_code == 200, getattr(response, 'data', None)
    return ' '.join(' '.join(p.extract_text() or '' for p in PdfReader(BytesIO(response.content)).pages).split())


def _named_zone(company, name, platform='soundtrack'):
    return Zone.objects.create(company=company, name=name, status='online', platform=platform)


def test_term_links_cover_the_term_only():
    company = _company()
    c = _contract(company, start=date(2025, 1, 1), end=date(2025, 12, 31))
    inside = _link(c, _zone(company), is_active=False, end_date=date(2025, 12, 31))
    open_link = _link(c, _zone(company))
    _link(c, _zone(company), start=date(2024, 1, 1), is_active=False, end_date=date(2024, 12, 31))  # before the term
    _link(c, _zone(company), start=date(2026, 1, 1))                                              # after the term
    assert sorted(l.pk for l in c.get_term_links()) == sorted([inside.pk, open_link.pk])
    assert c.get_term_zone_count() == 2


def test_a_renewed_term_whose_links_were_handed_over_still_shows_its_zones():
    from crm_app.views import ContractViewSet, _contract_zone_count
    company = _company()
    old = _contract(company, start=date(2025, 1, 1), end=date(2025, 12, 31))
    new = _contract(company, status='Sent', start=date(2026, 1, 1), renewed_from=old)
    zones = [_named_zone(company, 'Rooftop Terrace'), _named_zone(company, 'Garden Lounge', platform='beatbreeze')]
    for z in zones:
        _link(old, z), _link(new, z)
    assert _rest_patch(new, {'status': 'Active'}).status_code == 200
    old.refresh_from_db()
    assert old.status == 'Renewed' and not ContractZone.objects.filter(contract=old, is_active=True).exists()
    assert old.get_zone_count() == 0                       # nothing active today ...
    assert _contract_zone_count(old) == 2                  # ... but the documents count the term's zones
    assert ContractViewSet._template_zone_count(old) == 2
    assert sorted(ContractViewSet()._template_service_labels(old)) == ['Beat Breeze', 'Soundtrack Your Brand']
    text = _pdf_text(old)
    assert 'Rooftop Terrace' in text and 'Garden Lounge' in text


def test_a_cancelled_term_whose_links_were_redated_still_shows_its_zones(tmp_path):
    from crm_app.views import _contract_zone_count
    company = _company()
    c = _contract(company, status='Cancelled', start=date(2025, 6, 1), end=date(2026, 5, 30))
    for name in ('Harbour Bar', 'Sky Pool'):
        _link(c, _named_zone(company, name), is_active=False, end_date=date(2026, 11, 14))
    _execute(tmp_path, _file(tmp_path, [_redate(c)]))
    assert set(ContractZone.objects.filter(contract=c).values_list('end_date', flat=True)) == {date(2026, 5, 30)}
    assert _contract_zone_count(c) == 2
    text = _pdf_text(c)
    assert 'Harbour Bar' in text and 'Sky Pool' in text


def test_the_repair_op_hands_over_a_zone_linked_to_the_renewal_after_it_went_active(tmp_path):
    company = _company()
    old = _contract(company, start=date(2025, 1, 1))
    new = _contract(company, status='Sent', start=date(2026, 1, 1), renewed_from=old)
    zone = _zone(company)
    old_link = _link(old, zone)
    assert _rest_patch(new, {'status': 'Active'}).status_code == 200  # the renewal held no zone then
    assert _state(old_link) == (True, None)
    _link(new, zone)                                                   # linked to the renewal afterwards
    out, _ = _execute(tmp_path, _file(tmp_path, [_handover(Contract.objects.get(pk=old.pk), new)]))
    assert '[APPLIED] Z hand_over_zone_links' in out
    assert _state(old_link) == (False, date(2025, 12, 31))
    assert zone.get_active_contract() == new


# --- review fixes ---------------------------------------------------------------------

def test_an_old_create_journal_is_not_reverted_after_the_repair_closed_its_old_links(tmp_path):
    """A create_successor journal written before the hand-over existed (no old_zone_links_closed),
    then the zone-link repair, then a revert of that old journal: refused, naming the repair batch.
    Reverting the repair first, then the old journal, restores everything."""
    company = _company()
    old = _contract(company)
    zone = _zone(company)
    old_link = _link(old, zone)
    _, g_journal = _execute(tmp_path, _file(tmp_path, [_create(old)]), 'g-journal.json')
    new = Contract.objects.get(renewed_from=old)
    # make it look like a run before this change: old links left open, no hand-over record
    journal = json.loads(open(g_journal).read())
    op = journal['groups'][0]['ops'][0]
    for r in op.pop('old_zone_links_closed'):
        ContractZone.objects.filter(pk=r['id']).update(is_active=True, end_date=None)
    open(g_journal, 'w').write(json.dumps(journal))
    assert _state(old_link) == (True, None)
    # the repair closes the doubled link
    old.refresh_from_db()
    z_out, z_journal = _execute(tmp_path, _file(tmp_path, [_handover(old, new)], 'z.json'), 'z-journal.json')
    assert '[APPLIED] Z hand_over_zone_links' in z_out
    z_batch = json.loads(open(z_journal).read())['batch_id']
    # reverting the old journal now is refused and names the repair batch
    out = _run('--revert', g_journal, '--execute')
    assert 'SKIPPED:zone_links_handed_over_since_apply' in out
    assert f'revert the zone-link repair first (batch {z_batch})' in out
    assert Contract.objects.filter(pk=new.pk).exists() and _state(old_link) == (False, date(2025, 12, 31))
    # the right order works
    assert '[REVERTED] Z hand_over_zone_links' in _run('--revert', z_journal, '--execute')
    assert '[REVERTED] G create_successor' in _run('--revert', g_journal, '--execute')
    assert _state(old_link) == (True, None)
    assert zone.get_active_contract() == Contract.objects.get(pk=old.pk)


def test_a_live_contract_document_counts_only_the_links_open_today():
    from crm_app.views import _contract_zone_count, _document_zones
    company = _company()
    c = _contract(company, start=date(2025, 1, 1), end=date(2025, 12, 31))
    gone = _zone(company)
    _link(c, gone, is_active=False, end_date=date(2025, 3, 31))   # left mid-term
    stays = [_zone(company) for _ in range(2)]
    for z in stays:
        _link(c, z)
    assert _contract_zone_count(c) == 2
    assert sorted(z.pk for z in _document_zones(c)) == sorted(z.pk for z in stays)
    Contract.objects.filter(pk=c.pk).update(status='Expired')
    c.refresh_from_db()
    assert _contract_zone_count(c) == 3                            # an ended term shows its whole term


def test_an_expired_old_term_hands_over_when_its_renewal_goes_active():
    company = _company()
    old = _contract(company, status='Expired')
    new = _contract(company, status='Sent', start=date(2026, 1, 1), renewed_from=old)
    zone = _zone(company)
    old_link, _ = _link(old, zone), _link(new, zone)
    assert _rest_patch(new, {'status': 'Active'}).status_code == 200
    old.refresh_from_db()
    assert old.status == 'Renewed' and old.is_active is False
    assert _state(old_link) == (False, date(2025, 12, 31))
    assert len(_rule_audit(old).additional_data['zone_links_closed']) == 1


def test_admin_bulk_activate_runs_the_lifecycle_rule():
    from unittest import mock
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory
    from crm_app.admin import ContractAdmin
    company = _company()
    old = _contract(company)
    new = _contract(company, status='Draft', start=date(2026, 1, 1), renewed_from=old)
    zone = _zone(company)
    old_link, _ = _link(old, zone), _link(new, zone)
    request = RequestFactory().post('/admin/')
    request.user = _user()
    admin_obj = ContractAdmin(Contract, AdminSite())
    with mock.patch.object(ContractAdmin, 'message_user') as message:
        admin_obj.bulk_update_status_active(request, Contract.objects.filter(pk=new.pk))
    new.refresh_from_db(), old.refresh_from_db()
    assert new.status == 'Active' and old.status == 'Renewed'
    assert _state(old_link) == (False, date(2025, 12, 31))
    assert '1 earlier term(s) set to Renewed' in message.call_args[0][1]
    assert _rule_audit(old).additional_data['source'] == 'admin_bulk_activate'


def test_copy_refuses_clearly_when_the_renewal_has_an_ended_link_to_the_zone(tmp_path):
    old, new, zones, _, _ = _renewed_pair(new_links=False)
    _link(new, zones[0], is_active=False, end_date=date(2026, 2, 1))  # same start as the renewal
    out = _run('--file', _file(tmp_path, [_handover(old, new, copy=True)]))
    assert 'SKIPPED:renewal_has_ended_link_to_zone' in out
