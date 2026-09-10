"""Hilton full-body tailoring and mistaken FK IDs must never partially succeed."""
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from crm_app.contract_pdf_v2 import (
    ContractTailoringClarification, tailored_template_content,
)
from crm_app.mcp import create_record, update_record
from crm_app.models import Company, Contract, ContractTemplate
from crm_app.tests.test_hilton_template_rendering import _contract
from crm_app.views import ContractViewSet


def test_full_body_override_preserves_approved_removal_and_shared_template():
    contract = _contract('{{service_product_managed_name}}<br/>{{zones_table}}<br/>RETIRED-CONTACT')
    original = contract.preamble_template.content
    contract.preamble_custom = original.replace('<br/>RETIRED-CONTACT', '')
    assert tailored_template_content(contract) == contract.preamble_custom
    assert contract.preamble_template.content == original


def test_full_body_override_cannot_drop_required_signature_slot():
    contract = _contract('{{zones_table}} {{signature_blocks}}')
    contract.preamble_custom = '{{zones_table}}'
    with pytest.raises(ContractTailoringClarification):
        tailored_template_content(contract)


def test_clause_override_without_named_slot_still_fails_closed():
    contract = _contract('{{zones_table}}')
    contract.preamble_custom = 'A new introductory clause.'
    with pytest.raises(ContractTailoringClarification):
        tailored_template_content(contract)


def test_full_body_override_still_checks_supplier_issuer_conflicts():
    contract = _contract('{{zones_table}}')
    contract.preamble_custom = 'BMAsia (Thailand) Co., Ltd. {{zones_table}}'
    with pytest.raises(ContractTailoringClarification):
        tailored_template_content(contract)


def test_unbound_custom_body_is_rejected_before_pdf_generation():
    contract = _contract()
    contract.preamble_template = None
    contract.preamble_custom = '{{zones_table}}'
    response = ContractViewSet()._generate_principal_terms_pdf(contract)
    assert response.status_code == 422
    assert response.data['code'] == 'clarification_required'


def test_hilton_guards_validate_effective_custom_body_not_original():
    contract = _contract()
    contract.preamble_custom = '{{service_product_managed_name}} {{zones_table}} {{unknown_legal_source}}'
    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
    assert any(item['code'] == 'unresolved_template_variables' for item in blockers)


def test_stream_only_template_remains_hilton_after_cosmetic_rename():
    contract = _contract()
    contract.preamble_template.pk = 19
    contract.preamble_template.name = 'Renamed by CRM'
    assert ContractViewSet._is_hilton_full_template(contract)


def test_hilton_long_section_keeps_its_final_line_on_the_same_page():
    lines = '<br/>'.join(f'PAGE-FIT-LINE-{number:02d}' for number in range(1, 51))
    contract = _contract('{{service_product_managed_name}} {{zones_table}}<br/>---<br/>' + lines)
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
    response = view._generate_principal_terms_pdf(contract)
    assert response.status_code == 200
    final_page = PdfReader(BytesIO(response.content)).pages[-1].extract_text()
    assert 'PAGE-FIT-LINE-01' in final_page
    assert 'PAGE-FIT-LINE-50' in final_page


@pytest.mark.django_db
def test_mistaken_fk_name_does_not_create_partial_contract():
    company = Company.objects.create(name='Schema regression fixture', billing_entity='BMAsia Limited')
    before = Contract.objects.count()
    result = json.loads(create_record('contract', json.dumps({
        'company': str(company.pk), 'start_date': '2026-11-01', 'end_date': '2027-10-31',
        'value': '800.00', 'preamble_template_id': 19,
    })))
    assert result['created'] is False
    assert 'preamble_template' in result['ignored_keys']['preamble_template_id']
    assert Contract.objects.count() == before


@pytest.mark.django_db
def test_mistaken_fk_name_cannot_partially_update_existing_contract():
    company = Company.objects.create(name='Update regression fixture', billing_entity='BMAsia Limited')
    contract = Contract.objects.create(company=company, start_date=date(2026, 11, 1),
        end_date=date(2027, 10, 31), value=Decimal('800'), preamble_custom='Original')
    result = json.loads(update_record('contract', str(contract.pk), json.dumps({
        'preamble_template_id': 19, 'preamble_custom': 'Must not be partially saved',
    })))
    assert result['updated'] is False
    contract.refresh_from_db()
    assert contract.preamble_custom == 'Original'


@pytest.mark.django_db
def test_canonical_template_field_persists_and_full_body_renders_without_writes():
    from django.db import connection
    from django.test import override_settings
    from django.test.utils import CaptureQueriesContext
    company = Company.objects.create(name='Hilton Garden Inn Fixture',
        legal_entity_name='Fixture Legal Limited', country='Malaysia',
        address_line1='1 Verified Road', billing_entity='BMAsia Limited')
    template = ContractTemplate.objects.create(name='Hilton International — Stream-only',
        template_type='preamble', pdf_format='standard',
        content='{{service_product_managed_name}}<br/>{{zones_table}}<br/>RETIRED-CONTACT')
    custom = template.content.replace('<br/>RETIRED-CONTACT', '')
    result = json.loads(create_record('contract', json.dumps({
        'company': str(company.pk), 'start_date': '2026-11-01', 'end_date': '2027-10-31',
        'value': '800.00', 'currency': 'USD', 'preamble_template': template.pk,
        'preamble_custom': custom, 'customer_contact_name': 'Verified Contact',
        'customer_contact_email': 'verified@example.com',
        'service_locations': [
            {'location_name': 'Lobby Area', 'platform': 'soundtrack', 'price': '400.00'},
            {'location_name': 'Rooftop Bar', 'platform': 'soundtrack', 'price': '400.00'},
        ],
    })))
    assert 'id' in result, result
    contract = Contract.objects.select_related('company', 'preamble_template').get(pk=result['id'])
    assert contract.preamble_template_id == template.pk
    view = ContractViewSet()
    view.log_action = lambda *args, **kwargs: None
    with override_settings(COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True):
        with CaptureQueriesContext(connection) as queries:
            response = view._generate_principal_terms_pdf(contract)
    assert response.status_code == 200, getattr(response, 'data', None)
    assert not any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                   for query in queries.captured_queries)
    text = ' '.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert 'Lobby Area' in text and 'Rooftop Bar' in text
    assert '{{' not in text and 'RETIRED-CONTACT' not in text
    template.refresh_from_db()
    assert template.content.endswith('RETIRED-CONTACT')
