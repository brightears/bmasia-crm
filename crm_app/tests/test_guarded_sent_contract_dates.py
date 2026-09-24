"""Routine Cira date corrections preserve an unsigned Sent contract's identity."""

import json
from datetime import date
from decimal import Decimal
from unittest import mock
from uuid import uuid4

import pytest

from crm_app.mcp import update_record
from crm_app.models import AuditLog, Company, Contract, ContractDocument
from crm_app.serializers import ContractSerializer


def _contract(*, status='Sent'):
    company = Company.objects.create(name=f'Date correction test {uuid4()}')
    contract = Contract.objects.create(
        company=company, contract_number=f'HK-CT{str(uuid4().int)[:12]}',
        status=status, start_date=date(2026, 9, 1), end_date=date(2028, 8, 31),
        value=Decimal('100.00'), total_value=Decimal('100.00'),
    )
    return contract


def _context(**changes):
    context = {
        'kind': 'routine_contract_date_correction',
        'requested_by': 'lyra',
        'source_reference': 'spaces/AAA/messages/BBB',
        'reason': 'Correct the agreed service term.',
    }
    context.update(changes)
    return context


def _update(contract, patch, *, context=None, before=None, version=None, record_id=None):
    record = ContractSerializer(contract).data
    return json.loads(update_record(
        'contract', str(record_id or contract.pk), json.dumps(patch),
        expected_version=version or record['updated_at'],
        expected_values=json.dumps(before or {key: record[key] for key in patch}),
        authorization_context=json.dumps(context if context is not None else _context()),
    ))


@pytest.mark.django_db
def test_two_date_correction_preserves_identity_and_writes_atomic_audit():
    contract = _contract()
    original = (contract.company_id, contract.contract_number, contract.status, contract.sent_date)
    patch = {'start_date': '2026-10-01', 'end_date': '2028-09-30'}
    with mock.patch('crm_app.services.email_service.EmailService.send_contract_email',
                    side_effect=AssertionError('customer send')):
        result = _update(contract, patch)
    contract.refresh_from_db()
    assert result['updated'] is True
    assert result['applied'] == patch
    assert result['company_id'] == str(contract.company_id)
    assert result['contract_number'] == original[1]
    assert result['post_version'] == ContractSerializer(contract).data['updated_at']
    assert (contract.company_id, contract.contract_number, contract.status, contract.sent_date) == original
    assert contract.start_date.isoformat() == patch['start_date']
    assert contract.end_date.isoformat() == patch['end_date']
    audit = AuditLog.objects.get(pk=result['audit_log_id'])
    assert audit.model_name == 'Contract'
    assert audit.record_id == str(contract.pk)
    assert audit.changes == {
        'start_date': {'before': '2026-09-01', 'after': '2026-10-01'},
        'end_date': {'before': '2028-08-31', 'after': '2028-09-30'},
    }
    assert audit.additional_data['requested_by'] == 'lyra'


@pytest.mark.django_db
@pytest.mark.parametrize('requested_by', ['norbert', 'lyra', 'theo'])
@pytest.mark.parametrize('patch', [
    {'start_date': '2026-10-01'},
    {'end_date': '2028-09-30'},
])
def test_single_date_subset_with_verified_source(requested_by, patch):
    contract = _contract()
    result = _update(contract, patch, context=_context(requested_by=requested_by))
    assert result['updated'] is True
    assert AuditLog.objects.filter(record_id=str(contract.pk)).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('signed_fields', [
    {'is_signed': True},
    {'signed_date': date(2026, 9, 10)},
])
def test_signed_document_blocks_change_without_audit(signed_fields):
    contract = _contract()
    ContractDocument.objects.create(
        contract=contract, document_type='generated', title='Signed copy',
        file='contract_documents/test-signed.pdf', **signed_fields,
    )
    result = _update(contract, {'start_date': '2026-10-01'})
    contract.refresh_from_db()
    assert result['updated'] is False
    assert 'Signed contract document' in result['error']
    assert contract.start_date == date(2026, 9, 1)
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()


@pytest.mark.django_db
def test_signed_document_appearing_during_save_rolls_back_date_and_audit():
    contract = _contract()
    original_save = ContractSerializer.save

    def save_with_new_signature(serializer, *args, **kwargs):
        saved = original_save(serializer, *args, **kwargs)
        ContractDocument.objects.create(
            contract=saved, document_type='generated', title='Concurrent signed copy',
            file='contract_documents/concurrent-signed.pdf', is_signed=True,
        )
        return saved

    with mock.patch.object(ContractSerializer, 'save', save_with_new_signature):
        result = _update(contract, {'start_date': '2026-10-01'})
    contract.refresh_from_db()
    assert result['updated'] is False
    assert 'readback or signed state changed' in result['error']
    assert contract.start_date == date(2026, 9, 1)
    assert not contract.contract_documents.exists()
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['Draft', 'Active', 'Renewed', 'Cancelled'])
def test_only_sent_contracts_can_use_routine_date_lane(status):
    contract = _contract(status=status)
    result = _update(contract, {'start_date': '2026-10-01'})
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 9, 1)


@pytest.mark.django_db
def test_stale_version_and_wrong_before_value_hold_without_audit():
    contract = _contract()
    record = ContractSerializer(contract).data
    contract.notes = 'A concurrent edit'
    contract.save()
    stale = _update(contract, {'start_date': '2026-10-01'}, version=record['updated_at'])
    mismatch = _update(contract, {'start_date': '2026-10-01'}, before={'start_date': '2026-08-01'})
    assert stale['updated'] is False and 'Stale expected_version' in stale['error']
    assert mismatch['updated'] is False and 'Expected values' in mismatch['error']
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 9, 1)
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()


@pytest.mark.django_db
def test_wrong_record_identity_cannot_reuse_another_records_preconditions():
    source = _contract()
    target = _contract()
    record = ContractSerializer(source).data
    result = _update(
        source, {'start_date': '2026-10-01'},
        record_id=target.pk, version=record['updated_at'],
    )
    assert result['updated'] is False
    target.refresh_from_db()
    assert target.start_date == date(2026, 9, 1)
    assert not AuditLog.objects.filter(record_id=str(target.pk)).exists()


@pytest.mark.django_db
def test_unguarded_sent_date_edit_cannot_bypass_correction_lane():
    contract = _contract()
    result = json.loads(update_record(
        'contract', str(contract.pk), json.dumps({'start_date': '2026-10-01'}),
    ))
    contract.refresh_from_db()
    assert result['updated'] is False
    assert 'guarded correction authorization' in result['error']
    assert contract.start_date == date(2026, 9, 1)
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('patch', [
    {'start_date': '2028-10-01'},
    {'end_date': '2026-08-01'},
    {'start_date': '2026-10-01', 'status': 'Active'},
    {'start_date': '2026-10-01', 'value': '0.00'},
])
def test_invalid_interval_or_mixed_patch_holds(patch):
    contract = _contract()
    result = _update(contract, patch)
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 9, 1)
    assert contract.end_date == date(2028, 8, 31)
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('context', [
    {},
    _context(kind='other'),
    _context(requested_by='other'),
    _context(requested_by=['lyra']),
    _context(requested_by={'name': 'lyra'}),
    _context(source_reference=''),
    _context(reason=''),
    _context(extra='not allowed'),
])
def test_invalid_provenance_context_holds(context):
    contract = _contract()
    result = _update(contract, {'start_date': '2026-10-01'}, context=context)
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.start_date == date(2026, 9, 1)
    assert not AuditLog.objects.filter(record_id=str(contract.pk)).exists()
