"""Final renewal review numbers must never manufacture customer delivery."""

import base64
import io
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.http import HttpResponse
from django.utils import timezone
from pypdf import PdfReader

from crm_app.mcp import generate_contract_pdf
from crm_app.models import Company, Contract, DocumentSequence, User
from crm_app.services.contract_review import (
    ContractReviewError,
    generate_numbered_renewal_review,
)
from crm_app.services.rene_phase2_common import rfc3339


@pytest.fixture
def renewal(db):
    company = Company.objects.create(
        name='Review Number Hotel', country='Vietnam', billing_entity='BMAsia Limited'
    )
    source = Contract.objects.create(
        company=company, contract_number='HK-CT25990', contract_type='Annual',
        status='Active', start_date=date(2025, 10, 1), end_date=date(2026, 9, 30),
        currency='USD', value=Decimal('380.00'), total_value=Decimal('380.00'),
    )
    draft = Contract.objects.create(
        company=company, renewed_from=source, contract_number='DRAFT-8001',
        contract_type='Annual', lifecycle_type='renewal', status='Draft',
        is_active=False, start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        currency='USD', value=Decimal('380.00'), total_value=Decimal('380.00'),
    )
    draft.service_locations.create(location_name='Lobby', platform='soundtrack', price=380)
    return source, draft


def fake_pdf(contract):
    return HttpResponse(b'%PDF-1.4\n' + contract.contract_number.encode(), content_type='application/pdf')


def generate(draft, renderer=fake_pdf):
    return generate_numbered_renewal_review(str(draft.id), rfc3339(draft.updated_at), renderer)


@pytest.mark.parametrize('is_active', [True, False])
def test_reservation_changes_only_number_and_version_without_lifecycle_effects(renewal, is_active):
    source, draft = renewal
    Contract.objects.filter(pk=draft.pk).update(is_active=is_active)
    draft.refresh_from_db()
    original_source = Contract.objects.values().get(pk=source.pk)
    original_draft = Contract.objects.values().get(pk=draft.pk)
    _, metadata = generate(draft)
    after = Contract.objects.values().get(pk=draft.pk)
    changed = {key for key in after if after[key] != original_draft[key]}
    assert changed == {'contract_number', 'updated_at'}
    assert Contract.objects.values().get(pk=source.pk) == original_source
    assert metadata['status'] == 'Draft'
    assert metadata['sent_date'] is None
    assert metadata['customer_delivery_performed'] is False
    assert after['is_active'] is is_active
    assert after['contract_number'].startswith('HK-CT')
    assert Contract.objects.count() == 2


def test_repeated_review_reuses_reserved_number_and_sent_keeps_it(renewal):
    _, draft = renewal
    _, first = generate(draft)
    sequence = list(DocumentSequence.objects.values())
    draft.refresh_from_db()
    _, second = generate(draft)
    assert second == first
    assert list(DocumentSequence.objects.values()) == sequence
    draft.refresh_from_db()
    draft.status = 'Sent'
    draft.save()
    draft.refresh_from_db()
    assert draft.contract_number == first['contract_number']


def test_reservation_skips_legacy_number_ahead_of_sequence(renewal):
    source, draft = renewal
    year = timezone.now().strftime('%y')
    Contract.objects.filter(pk=source.pk).update(contract_number=f'HK-CT{year}001')
    _, metadata = generate(draft)
    assert metadata['contract_number'] == f'HK-CT{year}002'


@pytest.mark.parametrize('response', [HttpResponse(status=503), HttpResponse(b'not a PDF')])
def test_failed_render_rolls_back_number_and_sequence(renewal, response):
    _, draft = renewal
    before = Contract.objects.values().get(pk=draft.pk)
    with pytest.raises(ContractReviewError, match='generation failed'):
        generate(draft, lambda contract: response)
    assert Contract.objects.values().get(pk=draft.pk) == before
    assert not DocumentSequence.objects.exists()


def test_stale_contract_rejected_before_reservation_or_render(renewal):
    _, draft = renewal
    old = rfc3339(draft.updated_at - timedelta(seconds=1))
    with pytest.raises(ContractReviewError, match='stale_read'):
        generate_numbered_renewal_review(str(draft.id), old, lambda contract: pytest.fail('rendered stale draft'))
    assert not DocumentSequence.objects.exists()


@pytest.mark.parametrize('version', ['', '2026-09-06T12:00:00', 'not-a-date', 12])
def test_missing_or_invalid_version_never_reserves(renewal, version):
    _, draft = renewal
    with pytest.raises(ContractReviewError, match='timezone-aware'):
        generate_numbered_renewal_review(str(draft.id), version, fake_pdf)
    assert not DocumentSequence.objects.exists()


@pytest.mark.parametrize('change', [
    {'renewed_from': None}, {'status': 'Sent'}, {'sent_date': date(2026, 9, 6)},
])
def test_only_unreported_linked_draft_renewals_qualify(renewal, change):
    _, draft = renewal
    Contract.objects.filter(pk=draft.pk).update(**change)
    draft.refresh_from_db()
    with pytest.raises(ContractReviewError):
        generate(draft)
    assert not DocumentSequence.objects.exists()


def test_cross_company_predecessor_rejected(renewal):
    source, draft = renewal
    other = Company.objects.create(name='Another company')
    Contract.objects.filter(pk=source.pk).update(company=other)
    with pytest.raises(ContractReviewError, match='same company'):
        generate(draft)
    assert not DocumentSequence.objects.exists()


def test_opt_in_mcp_pdf_has_visible_final_number_while_contract_remains_draft(renewal):
    source, draft = renewal
    User.objects.create(username='review-test-admin', role='Admin')
    before_source = Contract.objects.values().get(pk=source.pk)
    result = json.loads(generate_contract_pdf(str(draft.id), True, rfc3339(draft.updated_at)))
    assert 'error' not in result, result
    pdf = base64.b64decode(result['content_b64'])
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    assert result['contract_number'] in text
    assert 'Contract Number' in text
    assert 'DRAFT-' not in text
    assert result['status'] == 'Draft'
    draft.refresh_from_db()
    assert draft.status == 'Draft'
    assert draft.sent_date is None
    assert Contract.objects.values().get(pk=source.pk) == before_source


def test_default_mcp_preview_keeps_existing_behavior_and_does_not_reserve(renewal):
    _, draft = renewal
    User.objects.create(username='preview-test-admin', role='Admin')
    before = Contract.objects.values().get(pk=draft.pk)
    result = json.loads(generate_contract_pdf(str(draft.id)))
    assert 'error' not in result, result
    assert 'contract_number' not in result
    assert Contract.objects.values().get(pk=draft.pk) == before
    assert not DocumentSequence.objects.exists()


def test_mcp_review_flag_is_not_truthy_string(renewal):
    _, draft = renewal
    result = json.loads(generate_contract_pdf(str(draft.id), 'false', rfc3339(draft.updated_at)))
    assert 'error' in result
    assert not DocumentSequence.objects.exists()
