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
from crm_app.models import AuditLog, Company, Contract, DocumentSequence, User
from crm_app.services.contract_review import (
    ContractReviewError,
    generate_numbered_contract_review,
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
    year = timezone.localdate().strftime('%y')
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
    # V2 places the final number in the recurring document header, not the
    # legacy metadata-table column. Its visibility remains the contract.
    assert 'PRINCIPAL TERMS' in text
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


@pytest.fixture
def new_contract(db):
    company = Company.objects.create(
        name='New Customer Hotel', country='Cambodia', billing_entity='BMAsia Limited'
    )
    draft = Contract.objects.create(
        company=company, contract_number='DRAFT-8101', contract_type='Annual',
        status='Draft', is_active=False, start_date=date(2026, 10, 15),
        end_date=date(2027, 10, 14), currency='USD',
        value=Decimal('520.00'), total_value=Decimal('520.00'),
    )
    draft.service_locations.create(location_name='Lobby', platform='beatbreeze', price=260)
    draft.service_locations.create(location_name='Rooftop', platform='beatbreeze', price=260)
    return draft


def test_new_contract_pdf_gets_final_number_and_stays_draft(new_contract):
    User.objects.create(username='new-contract-admin', role='Admin')
    result = json.loads(generate_contract_pdf(
        str(new_contract.id), expected_version=rfc3339(new_contract.updated_at),
        reserve_final_number=True,
    ))
    assert 'error' not in result, result
    assert result['contract_number'].startswith('HK-CT')
    pdf = base64.b64decode(result['content_b64'])
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    assert result['contract_number'] in text
    assert 'DRAFT-' not in text
    new_contract.refresh_from_db()
    assert new_contract.status == 'Draft'
    assert new_contract.sent_date is None
    assert new_contract.contract_number == result['contract_number']


def test_new_contract_retry_reuses_number(new_contract):
    first = generate_numbered_contract_review(
        str(new_contract.id), rfc3339(new_contract.updated_at), fake_pdf)[1]
    new_contract.refresh_from_db()
    second = generate_numbered_contract_review(
        str(new_contract.id), rfc3339(new_contract.updated_at), fake_pdf)[1]
    assert second['contract_number'] == first['contract_number']


def test_final_number_requires_draft(new_contract):
    Contract.objects.filter(pk=new_contract.pk).update(status='Active')
    new_contract.refresh_from_db()
    with pytest.raises(ContractReviewError, match='only for a Draft'):
        generate_numbered_contract_review(
            str(new_contract.id), rfc3339(new_contract.updated_at), fake_pdf)
    assert not DocumentSequence.objects.exists()


def test_renewal_only_flag_still_refuses_new_contract(new_contract):
    with pytest.raises(ContractReviewError, match='linked renewal'):
        generate(new_contract)
    assert not DocumentSequence.objects.exists()


# A Sent contract that already carries its final number (for example after a
# revision) renders without reserving or writing anything. Invented names only.

@pytest.fixture
def sent_contract(db):
    company = Company.objects.create(
        name='Example Riverside Spa', country='Thailand',
        billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number='TH-CT26901', contract_type='Annual',
        status='Sent', sent_date=date(2026, 11, 20), is_active=False,
        start_date=date(2026, 12, 1), end_date=date(2027, 11, 30), currency='THB',
        value=Decimal('24000.00'), total_value=Decimal('24000.00'),
    )
    contract.service_locations.create(location_name='Lobby', platform='soundtrack', price=24000)
    contract.refresh_from_db()
    return contract


def review(contract, renderer=fake_pdf):
    return generate_numbered_contract_review(str(contract.id), rfc3339(contract.updated_at), renderer)


def test_sent_contract_with_final_number_renders_without_any_write(sent_contract):
    before = Contract.objects.values().get(pk=sent_contract.pk)
    response, metadata = review(sent_contract)
    assert response.content.startswith(b'%PDF-')
    assert Contract.objects.values().get(pk=sent_contract.pk) == before
    assert not DocumentSequence.objects.exists()
    assert not AuditLog.objects.exists()
    assert metadata == {
        'contract_id': str(sent_contract.id),
        'contract_number': 'TH-CT26901',
        'status': 'Sent',
        'sent_date': '2026-11-20',
        'updated_at': rfc3339(before['updated_at']),
        'customer_delivery_performed': False,
    }


def test_sent_contract_render_still_requires_current_version(sent_contract):
    old = rfc3339(sent_contract.updated_at - timedelta(seconds=1))
    with pytest.raises(ContractReviewError, match='stale_read'):
        generate_numbered_contract_review(
            str(sent_contract.id), old, lambda contract: pytest.fail('rendered stale contract'))
    with pytest.raises(ContractReviewError, match='timezone-aware'):
        generate_numbered_contract_review(str(sent_contract.id), '', fake_pdf)


@pytest.mark.parametrize('number', ['DRAFT-8201', 'C-1234', '', 'TH-CT123', 'HK-QT26901'])
def test_sent_contract_without_final_number_is_refused_and_never_reserved(sent_contract, number):
    Contract.objects.filter(pk=sent_contract.pk).update(contract_number=number)
    sent_contract.refresh_from_db()
    before = Contract.objects.values().get(pk=sent_contract.pk)
    with pytest.raises(ContractReviewError, match='needs reconciliation'):
        review(sent_contract, lambda contract: pytest.fail('rendered unnumbered Sent contract'))
    assert Contract.objects.values().get(pk=sent_contract.pk) == before
    assert not DocumentSequence.objects.exists()


@pytest.mark.parametrize('status', ['Active', 'Renewed', 'Expired', 'Cancelled'])
def test_signed_or_closed_statuses_are_refused_by_name(sent_contract, status):
    Contract.objects.filter(pk=sent_contract.pk).update(status=status)
    sent_contract.refresh_from_db()
    with pytest.raises(ContractReviewError, match=f'this contract is {status}'):
        review(sent_contract, lambda contract: pytest.fail(f'rendered {status} contract'))
    assert not DocumentSequence.objects.exists()


@pytest.mark.parametrize('response', [HttpResponse(status=503), HttpResponse(b'not a PDF')])
def test_failed_render_of_sent_contract_changes_nothing(sent_contract, response):
    before = Contract.objects.values().get(pk=sent_contract.pk)
    with pytest.raises(ContractReviewError, match='generation failed; nothing was changed'):
        review(sent_contract, lambda contract: response)
    assert Contract.objects.values().get(pk=sent_contract.pk) == before
    assert not DocumentSequence.objects.exists()
    assert not AuditLog.objects.exists()


def test_sent_renewal_with_cross_company_predecessor_is_refused(sent_contract):
    other = Company.objects.create(name='Example Other Holdings')
    source = Contract.objects.create(
        company=other, contract_number='TH-CT25901', contract_type='Annual', status='Active',
        start_date=date(2025, 12, 1), end_date=date(2026, 11, 30), currency='THB',
        value=Decimal('24000.00'), total_value=Decimal('24000.00'),
    )
    Contract.objects.filter(pk=sent_contract.pk).update(renewed_from=source)
    sent_contract.refresh_from_db()
    with pytest.raises(ContractReviewError, match='same company'):
        review(sent_contract)


def test_renewal_only_flag_stays_draft_only_for_sent_contract(sent_contract, renewal):
    source, _ = renewal
    Contract.objects.filter(pk=sent_contract.pk).update(renewed_from=source)
    Contract.objects.filter(pk=source.pk).update(company=sent_contract.company)
    sent_contract.refresh_from_db()
    with pytest.raises(ContractReviewError, match='linked renewal in Draft'):
        generate(sent_contract)


def test_mcp_renders_revised_sent_contract_through_final_number_flag(sent_contract):
    User.objects.create(username='sent-render-admin', role='Admin')
    before = Contract.objects.values().get(pk=sent_contract.pk)
    result = json.loads(generate_contract_pdf(
        str(sent_contract.id), expected_version=rfc3339(sent_contract.updated_at),
        reserve_final_number=True,
    ))
    assert 'error' not in result, result
    assert result['contract_number'] == 'TH-CT26901'
    assert result['status'] == 'Sent'
    assert result['sent_date'] == '2026-11-20'
    assert result['updated_at'] == rfc3339(before['updated_at'])
    assert result['customer_delivery_performed'] is False
    pdf = base64.b64decode(result['content_b64'])
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    assert 'TH-CT26901' in text
    assert Contract.objects.values().get(pk=sent_contract.pk) == before
    assert not DocumentSequence.objects.exists()
    assert not AuditLog.objects.exists()


def test_mcp_refuses_active_contract_with_status_in_error(sent_contract):
    Contract.objects.filter(pk=sent_contract.pk).update(status='Active')
    sent_contract.refresh_from_db()
    result = json.loads(generate_contract_pdf(
        str(sent_contract.id), expected_version=rfc3339(sent_contract.updated_at),
        reserve_final_number=True,
    ))
    assert 'this contract is Active' in result['error']
    assert 'content_b64' not in result
