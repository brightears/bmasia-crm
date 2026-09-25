"""Regression coverage for the one-record Hilton layout recovery guard."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from mcp_server.djangomcp import django_request_ctx

from crm_app import mcp
from crm_app.mcp import update_record
from crm_app.models import AuditLog, Company, Contract, ContractDocument, ContractTemplate
from crm_app.serializers import ContractSerializer


@contextmanager
def _as_caller(username):
    user, _ = get_user_model().objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'role': 'Admin'},
    )
    token = django_request_ctx.set(SimpleNamespace(user=user))
    try:
        yield user
    finally:
        django_request_ctx.reset(token)


def _source():
    return (
        "Synthetic legal preamble\n"
        "{{client_signatory_title}}\n"
        "[Enter Workman's Comp #].\n"
        "{{signature_blocks}}\n"
    )


def _fixture(monkeypatch):
    manifest = dict(mcp._CONTRACT_LAYOUT_CORRECTION_MANIFEST)
    source = _source()
    manifest['template_sha256'] = hashlib.sha256(source.encode('utf-8')).hexdigest()
    monkeypatch.setattr(mcp, '_CONTRACT_LAYOUT_CORRECTION_MANIFEST', manifest)
    template = ContractTemplate.objects.create(
        id=manifest['template_id'], name='Hilton Thailand', template_type='preamble',
        content=source,
    )
    company = Company.objects.create(
        id=UUID(manifest['company_id']), name='Layout guard fixture',
        billing_entity='BMAsia Limited',
    )
    contract = Contract.objects.create(
        id=UUID(manifest['record_id']), company=company,
        contract_number=manifest['contract_number'],
        start_date=date(2026, 9, 1), end_date=date(2027, 8, 31),
        value=Decimal('1.00'), tax_rate=Decimal('0.00'), tax_amount=Decimal('0.00'), total_value=Decimal('1.00'), status='Draft',
        preamble_template=template, preamble_custom='', sent_date=None,
        additional_customer_signatories=[],
    )
    expected = mcp._contract_layout_correction_body(source)
    observed = ContractSerializer(contract).data
    patch = {'preamble_custom': expected}
    context = {
        'kind': 'contract_layout_correction',
        'source_reference': manifest['source_reference'],
        'record_id': manifest['record_id'],
        'authorized_changes': patch,
    }
    return contract, patch, observed, context, manifest


def _call(contract, patch, observed, context):
    return json.loads(update_record(
        'contract', str(contract.pk), json.dumps(patch),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({'preamble_custom': ''}),
        authorization_context=json.dumps(context),
    ))


@pytest.mark.django_db
def test_contract_layout_correction_is_cira_only_source_bound_and_audited(monkeypatch):
    contract, patch, observed, context, manifest = _fixture(monkeypatch)
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)

    assert result['updated'] is True, result
    assert result['contract_number'] == manifest['contract_number']
    assert result['post_version']
    assert result['audit_log_id']
    contract.refresh_from_db()
    assert contract.preamble_custom == patch['preamble_custom']
    assert contract.status == 'Draft'
    assert contract.sent_date is None
    assert contract.customer_signatory_name == ''
    assert contract.customer_signatory_title == ''
    audit = AuditLog.objects.get(pk=result['audit_log_id'])
    assert audit.changes == {'preamble_custom': {
        'before_sha256': hashlib.sha256(b'').hexdigest(),
        'after_sha256': hashlib.sha256(patch['preamble_custom'].encode('utf-8')).hexdigest(),
    }}
    assert audit.additional_data['kind'] == 'contract_layout_correction'
    assert audit.additional_data['prior_pdf_sha256'] == manifest['prior_pdf_sha256']
    assert patch['preamble_custom'] not in json.dumps(audit.additional_data)


@pytest.mark.django_db
@pytest.mark.parametrize('username, expected', [
    ('vera', 'Contract layout correction requires an authenticated Cira writer.'),
    ('cira', 'Contract layout correction source reference is not the approved recovery.'),
])
def test_contract_layout_correction_rejects_writer_or_source(monkeypatch, username, expected):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    if username == 'cira':
        context['source_reference'] = 'codex:other'
    with _as_caller(username):
        result = _call(contract, patch, observed, context)
    assert result['updated'] is False
    assert result['error'] == expected
    contract.refresh_from_db()
    assert contract.preamble_custom == ''


@pytest.mark.django_db
def test_contract_layout_correction_rejects_stale_before_and_mixed_patch(monkeypatch):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    contract.notes = 'unrelated concurrent update'
    contract.save()
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Stale expected_version; nothing was saved.'
    contract.refresh_from_db()
    observed = ContractSerializer(contract).data
    with _as_caller('cira'):
        result = json.loads(update_record(
            'contract', str(contract.pk), json.dumps(patch),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'preamble_custom': 'wrong'}),
            authorization_context=json.dumps(context),
        ))
    assert result['error'] == 'Contract layout correction requires an empty preamble before value.'
    mixed = {'preamble_custom': patch['preamble_custom'], 'status': 'Sent'}
    with _as_caller('cira'):
        result = json.loads(update_record(
            'contract', str(contract.pk), json.dumps(mixed),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'preamble_custom': '', 'status': 'Draft'}),
            authorization_context=json.dumps(context),
        ))
    assert result['error'] == 'Guarded patch contains fields outside the approved correction scope.'


@pytest.mark.django_db
@pytest.mark.parametrize('field, value', [
    ('status', 'Sent'),
    ('sent_date', date(2026, 9, 2)),
    ('customer_signatory_name', 'Existing signer'),
    ('preamble_custom', 'existing custom body'),
])
def test_contract_layout_correction_rejects_changed_preconditions(monkeypatch, field, value):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    setattr(contract, field, value)
    contract.save()
    observed = ContractSerializer(contract).data
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Contract layout correction preconditions no longer match; nothing was saved.'


@pytest.mark.django_db
def test_contract_layout_correction_rejects_body_or_template_digest(monkeypatch):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    altered = {'preamble_custom': patch['preamble_custom'] + 'x'}
    altered_context = dict(context, authorized_changes=altered)
    with _as_caller('cira'):
        result = _call(contract, altered, observed, altered_context)
    assert result['error'] == 'Contract layout correction body does not match the pinned source transform; nothing was saved.'

    contract.preamble_template.content += 'changed'
    contract.preamble_template.save()
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Contract layout correction body does not match the pinned source transform; nothing was saved.'


@pytest.mark.django_db
@pytest.mark.parametrize('content', [
    "{{client_signatory_title}}\n[Enter Workman's Comp #].\n",
    "{{client_signatory_title}}\n[Enter Workman's Comp #].\n{{signature_blocks}}\n{{signature_blocks}}\n",
])
def test_contract_layout_correction_rejects_missing_or_duplicate_source_tokens(monkeypatch, content):
    contract, patch, observed, context, manifest = _fixture(monkeypatch)
    contract.preamble_template.content = content
    contract.preamble_template.save()
    manifest['template_sha256'] = hashlib.sha256(content.encode('utf-8')).hexdigest()
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Contract layout correction body does not match the pinned source transform; nothing was saved.'


@pytest.mark.django_db
def test_contract_layout_correction_rolls_back_unrelated_save_hook_mutation(monkeypatch):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    original_save = Contract.save

    def mutating_save(self, *args, **kwargs):
        self.value = Decimal('99.00')
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(Contract, 'save', mutating_save)
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['updated'] is False
    assert result['error'] == 'Contract layout correction readback changed protected state; nothing was saved.'
    contract.refresh_from_db()
    assert contract.preamble_custom == ''
    assert contract.value == Decimal('1.00')


@pytest.mark.django_db
def test_contract_layout_correction_rejects_signed_document(monkeypatch, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    ContractDocument.objects.create(
        contract=contract, document_type='generated', title='Synthetic signed record',
        file=SimpleUploadedFile('synthetic.pdf', b'%PDF-1.4'),
        is_signed=True, signed_date=date(2026, 9, 2),
    )
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Signed contract document blocks layout correction; nothing was saved.'


@pytest.mark.django_db
@pytest.mark.parametrize('change', ['company', 'template'])
def test_contract_layout_correction_rejects_wrong_company_or_template(monkeypatch, change):
    contract, patch, observed, context, _ = _fixture(monkeypatch)
    if change == 'company':
        contract.company = Company.objects.create(
            name='Different company', billing_entity='BMAsia Limited',
        )
    else:
        contract.preamble_template = ContractTemplate.objects.create(
            name='Different template', template_type='preamble', content=_source(),
        )
    contract.save()
    observed = ContractSerializer(contract).data
    with _as_caller('cira'):
        result = _call(contract, patch, observed, context)
    assert result['error'] == 'Contract layout correction preconditions no longer match; nothing was saved.'
