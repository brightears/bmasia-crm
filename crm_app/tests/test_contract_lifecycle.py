"""Contract lifecycle: a renewal going Active closes its Active predecessor.

Covers the rule in services/contract_lifecycle.py through every write path that
reaches it (REST PATCH, MCP create/update plain and guarded), signed_date, the
fixed duplicate_for_renewal action, and the close_renewed_predecessors backfill.
All data is synthetic.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
import json

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIRequestFactory, force_authenticate

from crm_app.mcp import create_record, update_record
from crm_app.models import (
    AuditLog, Company, Contract, ContractLineItem, ContractServiceLocation,
    ContractZone, ServicePackageItem, User, Zone,
)
from crm_app.serializers import ContractSerializer
from crm_app.services.contract_lifecycle import (
    ALREADY_RENEWED, CLOSED, DIFFERENT_COMPANY, PREDECESSOR_NOT_ACTIVE,
    close_renewed_predecessor,
)
from crm_app.views import ContractViewSet

_numbers = iter(range(1, 10_000))


def _company(name='Lifecycle fixture company'):
    return Company.objects.create(name=name, billing_entity='BMAsia Limited')


def _contract(company, status='Active', renewed_from=None, start=date(2025, 11, 1), **extra):
    values = dict(
        company=company, contract_number=f'TEST-CT-{next(_numbers):04d}',
        status=status, start_date=start, end_date=start + timedelta(days=364),
        value=Decimal('1200.00'), total_value=Decimal('1200.00'),
        is_active=status == 'Active', renewed_from=renewed_from,
    )
    values.update(extra)
    return Contract.objects.create(**values)


def _pair(predecessor_status='Active', successor_status='Sent', successor_company=None):
    company = _company()
    predecessor = _contract(company, status=predecessor_status)
    successor = _contract(
        successor_company or company, status=successor_status, renewed_from=predecessor,
        start=date(2026, 11, 1),
    )
    return predecessor, successor


def _user(username=None):
    return User.objects.create_user(username=username or f'lifecycle-tester-{next(_numbers)}', role='Sales')


def _rest_patch(contract, patch, user=None):
    user = user or _user()
    request = APIRequestFactory().patch(f'/api/v1/contracts/{contract.pk}/', patch, format='json')
    force_authenticate(request, user=user)
    return ContractViewSet.as_view({'patch': 'partial_update'})(request, pk=str(contract.pk))


def _closure_audits(predecessor):
    return AuditLog.objects.filter(
        model_name='Contract', record_id=str(predecessor.pk), action='UPDATE',
        additional_data__rule='renewed_predecessor_closed_on_successor_active',
    )


def _assert_closed(predecessor, successor):
    predecessor.refresh_from_db()
    assert predecessor.status == 'Renewed'
    assert predecessor.is_active is False
    audits = list(_closure_audits(predecessor))
    assert len(audits) == 1
    assert audits[0].changes == {
        'status': {'old': 'Active', 'new': 'Renewed'},
        'is_active': {'old': True, 'new': False},
    }
    assert audits[0].additional_data['successor_id'] == str(successor.pk)
    return audits[0]


# --- signed_date ---------------------------------------------------------------

def test_signed_date_is_null_by_default_and_writable_through_serializer():
    _, successor = _pair()
    assert successor.signed_date is None
    assert ContractSerializer(successor).data['signed_date'] is None

    response = _rest_patch(successor, {'signed_date': '2026-10-28'})

    assert response.status_code == 200, response.data
    successor.refresh_from_db()
    assert successor.signed_date == date(2026, 10, 28)
    assert response.data['signed_date'] == '2026-10-28'
    assert successor.status == 'Sent'  # recording a signature does not activate


def test_activation_does_not_invent_a_signed_date():
    predecessor, successor = _pair()
    _rest_patch(successor, {'status': 'Active'})
    successor.refresh_from_db()
    assert successor.signed_date is None


def test_mcp_update_record_writes_signed_date():
    _, successor = _pair(successor_status='Draft')
    result = json.loads(update_record('contract', str(successor.pk), json.dumps({'signed_date': '2026-10-30'})))
    assert result['updated'] is True, result
    successor.refresh_from_db()
    assert successor.signed_date == date(2026, 10, 30)


# --- rule via REST -------------------------------------------------------------

def test_rest_patch_activation_closes_active_predecessor():
    predecessor, successor = _pair()
    user = _user('rest-activator')

    response = _rest_patch(successor, {'status': 'Active', 'is_active': True}, user=user)

    assert response.status_code == 200, response.data
    successor.refresh_from_db()
    assert successor.status == 'Active'
    audit = _assert_closed(predecessor, successor)
    assert audit.user == user
    assert audit.additional_data['source'] == 'contract_serializer'


def test_rest_patch_activation_rolls_back_closure_if_request_fails(monkeypatch):
    predecessor, successor = _pair()

    def fail_audit(*args, **kwargs):
        raise ValueError('synthetic audit failure')

    monkeypatch.setattr(ContractViewSet, 'log_action', fail_audit)
    with pytest.raises(ValueError, match='synthetic audit failure'):
        _rest_patch(successor, {'status': 'Active'})

    predecessor.refresh_from_db()
    successor.refresh_from_db()
    assert successor.status == 'Sent'
    assert predecessor.status == 'Active' and predecessor.is_active is True
    assert not _closure_audits(predecessor).exists()


@pytest.mark.parametrize('status', ['Draft', 'Sent', 'Cancelled'])
def test_predecessor_in_other_status_is_untouched(status):
    predecessor, successor = _pair(predecessor_status=status)
    before_updated_at = predecessor.updated_at

    response = _rest_patch(successor, {'status': 'Active'})

    assert response.status_code == 200, response.data
    predecessor.refresh_from_db()
    assert predecessor.status == status
    assert predecessor.updated_at == before_updated_at
    assert not _closure_audits(predecessor).exists()
    result = close_renewed_predecessor(successor, source='test')
    assert result.outcome == PREDECESSOR_NOT_ACTIVE
    assert result.predecessor_status == status


def test_predecessor_on_different_company_is_untouched():
    predecessor, successor = _pair(successor_company=_company('Other lifecycle company'))

    response = _rest_patch(successor, {'status': 'Active'})

    assert response.status_code == 200, response.data
    predecessor.refresh_from_db()
    assert predecessor.status == 'Active' and predecessor.is_active is True
    assert not _closure_audits(predecessor).exists()
    assert close_renewed_predecessor(successor, source='test').outcome == DIFFERENT_COMPANY


def test_rule_is_idempotent():
    predecessor, successor = _pair()
    _rest_patch(successor, {'status': 'Active'})
    first_updated_at = Contract.objects.get(pk=predecessor.pk).updated_at

    again = close_renewed_predecessor(successor, source='test')
    _rest_patch(successor, {'notes': 'ordinary edit after activation'})

    assert again.outcome == ALREADY_RENEWED
    predecessor.refresh_from_db()
    assert predecessor.updated_at == first_updated_at
    assert _closure_audits(predecessor).count() == 1


def test_ordinary_edit_of_already_active_pair_does_not_fire():
    # Legacy data: both Active. Only the backfill (or a real transition) closes it.
    predecessor, successor = _pair(successor_status='Active')
    _rest_patch(successor, {'notes': 'unrelated edit'})
    predecessor.refresh_from_db()
    assert predecessor.status == 'Active'


def test_linking_an_active_contract_to_an_active_predecessor_fires():
    company = _company()
    predecessor = _contract(company)
    successor = _contract(company, start=date(2026, 11, 1))

    response = _rest_patch(successor, {'renewed_from': str(predecessor.pk)})

    assert response.status_code == 200, response.data
    _assert_closed(predecessor, successor)


def test_closing_bumps_predecessor_version_for_guarded_writers():
    predecessor, successor = _pair()
    observed = ContractSerializer(predecessor).data
    _rest_patch(successor, {'status': 'Active'})

    result = json.loads(update_record(
        'contract', str(predecessor.pk), json.dumps({'notes': 'stale writer'}),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'notes': observed['notes']}),
    ))

    assert result['updated'] is False
    assert 'Stale expected_version' in result['error']


# --- rule via MCP --------------------------------------------------------------

def test_mcp_plain_update_record_activation_closes_predecessor():
    predecessor, successor = _pair()

    result = json.loads(update_record('contract', str(successor.pk), json.dumps({'status': 'Active'})))

    assert result['updated'] is True, result
    audit = _assert_closed(predecessor, successor)
    assert audit.user is None  # no MCP request context in this test
    assert result['predecessor_lifecycle']['outcome'] == 'closed'
    assert result['predecessor_lifecycle']['predecessor_id'] == str(predecessor.pk)


def test_mcp_update_record_reports_untouched_predecessor():
    predecessor, successor = _pair(predecessor_status='Cancelled')

    result = json.loads(update_record('contract', str(successor.pk), json.dumps({'status': 'Active'})))

    assert result['updated'] is True, result
    assert result['predecessor_lifecycle']['outcome'] == 'predecessor_not_active'
    assert result['predecessor_lifecycle']['predecessor_status'] == 'Cancelled'
    predecessor.refresh_from_db()
    assert predecessor.status == 'Cancelled'


def test_mcp_guarded_update_record_activation_closes_predecessor():
    predecessor, successor = _pair()
    observed = ContractSerializer(successor).data

    result = json.loads(update_record(
        'contract', str(successor.pk), json.dumps({'status': 'Active'}),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'status': 'Sent'}),
    ))

    assert result['updated'] is True, result
    assert result['predecessor_lifecycle']['outcome'] == 'closed'
    _assert_closed(predecessor, successor)
    guarded_audit = AuditLog.objects.get(record_id=str(successor.pk), additional_data__kind='guarded_update')
    assert guarded_audit.changes == {'status': {'before': 'Sent', 'after': 'Active'}}


def test_mcp_guarded_refusal_leaves_predecessor_alone():
    predecessor, successor = _pair()
    observed = ContractSerializer(successor).data

    result = json.loads(update_record(
        'contract', str(successor.pk), json.dumps({'status': 'Active'}),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'status': 'Draft'}),  # wrong before-value
    ))

    assert result['updated'] is False
    predecessor.refresh_from_db()
    assert predecessor.status == 'Active'
    assert not _closure_audits(predecessor).exists()


def test_mcp_create_record_born_active_renewal_closes_predecessor():
    company = _company()
    predecessor = _contract(company)

    result = json.loads(create_record('contract', json.dumps({
        'company': str(company.pk), 'status': 'Active', 'renewed_from': str(predecessor.pk),
        'start_date': '2026-11-01', 'end_date': '2027-10-31', 'value': '1200.00',
    })))

    assert 'id' in result, result
    assert result['predecessor_lifecycle']['outcome'] == 'closed'
    _assert_closed(predecessor, Contract.objects.get(pk=result['id']))


# --- duplicate_for_renewal -----------------------------------------------------

def _rich_original():
    company = _company('Renewal source company')
    original = _contract(company, renewal_period_months=12, notes='source notes')
    lobby = Zone.objects.create(company=company, name='Lobby')
    bar = Zone.objects.create(company=company, name='Bar')
    removed = Zone.objects.create(company=company, name='Removed zone')
    ContractZone.objects.create(contract=original, zone=lobby, start_date=original.start_date)
    ContractZone.objects.create(contract=original, zone=bar, start_date=original.start_date)
    ContractZone.objects.create(
        contract=original, zone=removed, start_date=original.start_date,
        end_date=date(2026, 3, 1), is_active=False,
    )
    ContractServiceLocation.objects.create(contract=original, location_name='Lobby', platform='soundtrack')
    ContractServiceLocation.objects.create(contract=original, location_name='Bar', platform='beatbreeze')
    ContractLineItem.objects.create(
        contract=original, product_service='Music subscription', quantity=2,
        unit_price=Decimal('600.00'), line_total=Decimal('1200.00'),
    )
    item = ServicePackageItem.objects.create(name='Curation', description='Playlist curation')
    original.service_items.add(item)
    return original


def _duplicate(original, user=None):
    request = APIRequestFactory().post(f'/api/v1/contracts/{original.pk}/duplicate_for_renewal/')
    force_authenticate(request, user=user or _user())
    return ContractViewSet.as_view({'post': 'duplicate_for_renewal'})(request, pk=str(original.pk))


def test_plain_zones_add_on_through_model_fails_without_start_date():
    """The bug the old copy loop hit: ContractZone.start_date is required."""
    original = _rich_original()
    target = _contract(original.company, status='Draft')
    zone = original.zones.first()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            target.zones.add(zone)


def test_duplicate_for_renewal_copies_everything_and_leaves_original_active():
    original = _rich_original()
    before_updated_at = original.updated_at

    response = _duplicate(original)

    assert response.status_code == 201, response.data
    assert response.data['original_status'] == 'Active'
    new = Contract.objects.get(pk=response.data['new_contract']['id'])
    assert new.status == 'Draft' and new.is_active is False
    assert new.contract_number.startswith('DRAFT-')
    assert new.renewed_from_id == original.pk
    assert new.start_date == original.end_date
    assert new.signed_date is None
    links = list(new.contract_zones.all())
    assert sorted(link.zone.name for link in links) == ['Bar', 'Lobby']
    assert all(link.start_date == new.start_date and link.is_active for link in links)
    assert sorted(new.service_locations.values_list('location_name', flat=True)) == ['Bar', 'Lobby']
    assert list(new.line_items.values_list('product_service', flat=True)) == ['Music subscription']
    assert list(new.service_items.values_list('name', flat=True)) == ['Curation']

    original.refresh_from_db()
    assert original.status == 'Active' and original.is_active is True
    assert original.updated_at == before_updated_at
    assert not AuditLog.objects.filter(record_id=str(original.pk)).exists()
    create_audit = AuditLog.objects.get(record_id=str(new.pk), action='CREATE')
    assert create_audit.changes['original_status'] == 'Active'
    assert create_audit.changes['original_status_changed'] is False


def test_duplicate_for_renewal_rolls_back_fully_on_failure(monkeypatch):
    original = _rich_original()
    contracts_before = Contract.objects.count()
    links_before = ContractZone.objects.count()
    locations_before = ContractServiceLocation.objects.count()
    items_before = ContractLineItem.objects.count()

    def fail_audit(*args, **kwargs):
        raise RuntimeError('synthetic failure after copy')

    monkeypatch.setattr(ContractViewSet, 'log_action', fail_audit)
    with pytest.raises(RuntimeError, match='synthetic failure after copy'):
        _duplicate(original)

    assert Contract.objects.count() == contracts_before
    assert ContractZone.objects.count() == links_before
    assert ContractServiceLocation.objects.count() == locations_before
    assert ContractLineItem.objects.count() == items_before
    original.refresh_from_db()
    assert original.status == 'Active'


def test_duplicate_for_renewal_refuses_second_in_flight_renewal():
    original = _rich_original()
    first = _duplicate(original)
    assert first.status_code == 201

    second = _duplicate(original)

    assert second.status_code == 409
    assert second.data['existing_renewal_id'] == first.data['new_contract']['id']
    assert Contract.objects.filter(renewed_from=original).count() == 1


def test_duplicate_for_renewal_without_end_date_is_a_clean_400():
    original = _contract(_company(), end_date=None)
    response = _duplicate(original)
    assert response.status_code == 400
    assert not Contract.objects.filter(renewed_from=original).exists()


def test_renewal_draft_activation_then_closes_original():
    original = _rich_original()
    new_id = _duplicate(original).data['new_contract']['id']
    new = Contract.objects.get(pk=new_id)
    new.status = 'Sent'
    new.save()

    response = _rest_patch(new, {'status': 'Active', 'is_active': True})

    assert response.status_code == 200, response.data
    _assert_closed(original, new)


# --- is_active on activation ---------------------------------------------------

def _rest_audit(contract):
    return AuditLog.objects.get(
        model_name='Contract', record_id=str(contract.pk), action='UPDATE',
        additional_data__view='ContractViewSet',
    )


def test_renewal_draft_goes_live_when_activated_over_rest():
    original = _rich_original()
    new = Contract.objects.get(pk=_duplicate(original).data['new_contract']['id'])
    assert (new.status, new.is_active) == ('Draft', False)

    response = _rest_patch(new, {'status': 'Active'})

    assert response.status_code == 200, response.data
    new.refresh_from_db()
    assert (new.status, new.is_active) == ('Active', True)
    assert _rest_audit(new).changes['is_active'] == {'old': False, 'new': True}
    _assert_closed(original, new)


def test_activation_respects_explicit_is_active_in_same_patch():
    _, successor = _pair()
    assert successor.is_active is False

    response = _rest_patch(successor, {'status': 'Active', 'is_active': False})

    assert response.status_code == 200, response.data
    successor.refresh_from_db()
    assert (successor.status, successor.is_active) == ('Active', False)
    assert 'is_active' not in _rest_audit(successor).changes


def test_activation_of_already_live_contract_leaves_is_active_alone():
    _, successor = _pair()
    Contract.objects.filter(pk=successor.pk).update(is_active=True)
    successor.refresh_from_db()

    response = _rest_patch(successor, {'status': 'Active'})

    assert response.status_code == 200, response.data
    successor.refresh_from_db()
    assert successor.is_active is True
    changes = _rest_audit(successor).changes
    assert changes['status'] == {'old': 'Sent', 'new': 'Active'}
    assert 'is_active' not in changes


def test_edit_of_already_active_contract_does_not_touch_is_active():
    contract = _contract(_company(), status='Active', is_active=False)
    response = _rest_patch(contract, {'status': 'Active', 'notes': 'edited'})
    assert response.status_code == 200, response.data
    contract.refresh_from_db()
    assert contract.is_active is False


def test_non_active_transition_does_not_touch_is_active():
    _, successor = _pair(successor_status='Draft')
    response = _rest_patch(successor, {'status': 'Sent'})
    assert response.status_code == 200, response.data
    successor.refresh_from_db()
    assert (successor.status, successor.is_active) == ('Sent', False)


@pytest.mark.parametrize('supplied, expected', [(None, True), (False, False), (True, True)])
def test_contract_born_active_is_live_unless_told_otherwise(supplied, expected):
    company = _company()
    data = {'company': str(company.pk), 'status': 'Active', 'start_date': '2026-11-01',
            'end_date': '2027-10-31', 'value': '1200.00'}
    if supplied is not None:
        data['is_active'] = supplied
    serializer = ContractSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    contract = serializer.save()
    contract.refresh_from_db()
    assert contract.is_active is expected


def test_mcp_update_record_activation_sets_is_active():
    _, successor = _pair()
    result = json.loads(update_record('contract', str(successor.pk), json.dumps({'status': 'Active'})))
    assert result['updated'] is True, result
    successor.refresh_from_db()
    assert (successor.status, successor.is_active) == ('Active', True)


# --- backfill command ----------------------------------------------------------

def _run_backfill(**kwargs):
    out = StringIO()
    call_command('close_renewed_predecessors', stdout=out, **kwargs)
    return out.getvalue()


def _backfill_fixture():
    today = date.today()
    company = _company('Backfill company')
    stale = _contract(company, start=today - timedelta(days=730))
    live = _contract(company, renewed_from=stale, start=today - timedelta(days=300))  # both Active
    pending_pred = _contract(company, start=today - timedelta(days=400))
    _contract(company, status='Sent', renewed_from=pending_pred, start=today - timedelta(days=35))
    lonely = _contract(company, start=today - timedelta(days=500))
    other_company_pred = _contract(company, start=today - timedelta(days=600))
    _contract(_company('Elsewhere'), renewed_from=other_company_pred, start=today - timedelta(days=200))
    return stale, live, pending_pred, lonely, other_company_pred


def test_backfill_dry_run_reports_and_changes_nothing():
    stale, live, pending_pred, lonely, other = _backfill_fixture()

    out = _run_backfill()

    assert '[DRY-RUN]' in out
    assert f'[WOULD-CLOSE] Active -> Renewed: {stale.contract_number} ({stale.pk})' in out
    assert 'would_close=1' in out
    assert 'active_past_end_with_sent_or_draft_successor=1' in out
    # Past end: stale (to be closed, so excluded), pending_pred (Sent successor), lonely
    # (no successor) and the cross-company predecessor (has a successor row, so not counted).
    assert 'active_past_end_without_successor=1' in out
    for contract in (stale, live, pending_pred, lonely, other):
        contract.refresh_from_db()
        assert contract.status == 'Active'
    assert not AuditLog.objects.exists()


def test_backfill_execute_closes_and_is_idempotent():
    stale, live, pending_pred, lonely, other = _backfill_fixture()

    out = _run_backfill(execute=True)

    assert f'[CLOSED] Active -> Renewed: {stale.contract_number} ({stale.pk})' in out
    assert 'closed=1' in out
    audit = _assert_closed(stale, live)
    assert audit.user is None
    assert audit.additional_data['source'] == 'close_renewed_predecessors'
    for contract in (live, pending_pred, lonely, other):
        contract.refresh_from_db()
        assert contract.status == 'Active'

    second = _run_backfill(execute=True)
    assert 'closed=0' in second
    assert _closure_audits(stale).count() == 1


# --- renewal reminder enrollment -----------------------------------------------

def test_renewal_enrollment_skips_contract_with_renewal_in_flight():
    """The original now stays Active while its renewal is Draft/Sent; it must not
    receive automated expiry reminders (it used to be Renewed at draft time)."""
    from crm_app.models import Contact, EmailSequence, EmailTemplate, SequenceEnrollment, SequenceStep
    from crm_app.services.auto_enrollment_service import AutoEnrollmentService

    template = EmailTemplate.objects.create(
        name='Lifecycle renewal template', template_type='renewal_30_days',
        subject='Renewal', body_text='Renewal reminder',
    )
    sequence = EmailSequence.objects.create(
        name='Lifecycle renewal sequence', created_by=_user(), sequence_type='auto_renewal',
    )
    SequenceStep.objects.create(
        sequence=sequence, step_number=1, name='First', email_template=template, delay_days=30,
    )
    target_end = date.today() + timedelta(days=30)
    in_flight_company = _company('In-flight renewal company')
    plain_company = _company('No renewal company')
    in_flight = _contract(in_flight_company, end_date=target_end)
    _contract(in_flight_company, status='Draft', renewed_from=in_flight, start=target_end)
    plain = _contract(plain_company, end_date=target_end)
    for company in (in_flight_company, plain_company):
        Contact.objects.create(company=company, name='Synthetic contact', email=f'{company.pk}@example.test')

    enrolled = AutoEnrollmentService().process_renewal_triggers()

    assert enrolled == 1
    ids = set(SequenceEnrollment.objects.values_list('trigger_entity_id', flat=True))
    assert ids == {str(plain.pk)}


def test_expired_predecessor_becomes_renewed_when_its_renewal_goes_active():
    """Widened with the zone hand-over: a term that has a successor is Renewed."""
    predecessor, successor = _pair(predecessor_status='Expired')

    response = _rest_patch(successor, {'status': 'Active'})

    assert response.status_code == 200, response.data
    predecessor.refresh_from_db()
    assert predecessor.status == 'Renewed' and predecessor.is_active is False
    audit = _closure_audits(predecessor).get()
    assert audit.changes['status'] == {'old': 'Expired', 'new': 'Renewed'}


def test_expired_predecessor_of_another_company_is_untouched():
    predecessor, successor = _pair(predecessor_status='Expired', successor_company=_company('Other expired company'))
    assert _rest_patch(successor, {'status': 'Active'}).status_code == 200
    predecessor.refresh_from_db()
    assert predecessor.status == 'Expired'
