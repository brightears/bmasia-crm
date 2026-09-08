from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from crm_app.views import ContractViewSet


class FakeQuerySet(list):
    def all(self):
        return self

    def exists(self):
        return bool(self)

    def count(self):
        return len(self)

    def first(self):
        return self[0] if self else None

    def filter(self, *args, **kwargs):
        rows = self
        for key, expected in kwargs.items():
            if key == 'title__icontains':
                rows = [row for row in rows if expected.casefold() in row.title.casefold()]
            else:
                rows = [row for row in rows if getattr(row, key, None) == expected]
        return FakeQuerySet(rows)

    def order_by(self, *fields):
        return self


class FakeRelatedManager(FakeQuerySet):
    pass


def _contact(name, email, title='', is_primary=False, is_active=True):
    return SimpleNamespace(
        name=name,
        email=email,
        title=title,
        is_primary=is_primary,
        is_active=is_active,
    )


def _service_location(platform='custom', custom_service_name='Beat Breeze', location_name='Lobby', price='260.00'):
    return SimpleNamespace(
        platform=platform,
        custom_service_name=custom_service_name,
        location_name=location_name,
        price=Decimal(price),
    )


def _contract(template_content='{{service_product_managed_name}} {{music_zone_label}} {{zones_table}}'):
    company = SimpleNamespace(
        name='Lihe Hilton Garden Inn',
        legal_entity_name='Lihe Garden Inn Co., Ltd.',
        billing_entity='BMAsia Limited',
        address_line1='1 Garden Road',
        address_line2='',
        city='Guangzhou',
        state='Guangdong',
        postal_code='510000',
        country='China',
        contacts=FakeRelatedManager([
            _contact('Wrong Linked Contact', 'wrong@example.com', is_primary=True),
        ]),
    )
    locations = FakeRelatedManager([_service_location()])
    contract = SimpleNamespace(
        company=company,
        preamble_template=SimpleNamespace(
            name='Hilton International',
            pdf_format='standard',
            content=template_content,
        ),
        contract_documents=FakeRelatedManager([]),
        contract_category='standard',
        contract_number='HK-TEST-1',
        status='Draft',
        start_date=date(2026, 10, 1),
        end_date=date(2027, 9, 30),
        value=Decimal('260.00'),
        currency='USD',
        billing_frequency='Annual',
        payment_terms='',
        tax_rate=Decimal('0'),
        property_name='Lihe Hilton Garden Inn',
        customer_contact_name='Joan Deng',
        customer_contact_email='Joan.Deng@hilton.com',
        customer_contact_title='Purchasing Manager',
        customer_signatory_name='',
        customer_signatory_title='',
        bmasia_contact_name='',
        bmasia_contact_email='',
        bmasia_contact_title='',
        show_zone_pricing_detail=True,
        price_per_zone=Decimal('260.00'),
        service_locations=locations,
    )
    contract.get_active_zones = lambda: FakeQuerySet([])
    contract.get_zone_count = lambda: ContractViewSet._template_zone_count(contract)
    return contract


def _pdf_page(label):
    output = BytesIO()
    page = canvas.Canvas(output)
    page.drawString(72, 720, label)
    page.save()
    return output.getvalue()


def test_template_contact_prefers_complete_contract_fields_and_exposes_aliases():
    contract = _contract(
        '{{contact_name}}|{{contact_email}}|{{contact_title}}|'
        '{{customer_contact_name}}|{{customer_contact_email}}|{{customer_contact_title}}'
    )

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    )

    assert rendered == (
        'Joan Deng|Joan.Deng@hilton.com|Purchasing Manager|'
        'Joan Deng|Joan.Deng@hilton.com|Purchasing Manager'
    )


def test_hilton_contact_falls_back_only_to_unique_active_company_primary():
    contract = _contract()
    contract.customer_contact_name = ''
    contract.customer_contact_email = ''
    contract.customer_contact_title = ''
    contract.company.contacts = FakeRelatedManager([
        _contact('Primary Person', 'primary@example.com', is_primary=True),
        _contact('Arbitrary Person', 'other@example.com'),
    ])

    resolved = ContractViewSet()._resolve_template_contact(contract)

    assert resolved['name'] == 'Primary Person'
    assert resolved['email'] == 'primary@example.com'

    contract.company.contacts = FakeRelatedManager([
        _contact('Arbitrary Person', 'other@example.com'),
    ])
    resolved = ContractViewSet()._resolve_template_contact(contract)
    assert resolved['source'] == 'missing'
    assert resolved['name'] == ''


def test_non_hilton_partial_contract_contact_preserves_company_fallback():
    contract = _contract('{{contact_name}}|{{contact_email}}')
    contract.preamble_template.name = 'Standard International'
    contract.customer_contact_name = ''
    contract.customer_contact_email = ''
    contract.customer_contact_title = 'Purchasing Manager'

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    )

    assert rendered == 'Wrong Linked Contact|wrong@example.com'


def test_custom_beat_breeze_location_drives_product_and_singular_zone_tokens():
    contract = _contract('{{service_product_name}}|{{service_product_managed_name}}|{{music_zone_label}}')

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    )

    assert rendered == 'Beat Breeze|Beat Breeze - Managed|1 music zone'


def test_hilton_dynamic_values_are_escaped_without_changing_template_markup():
    contract = _contract(
        '<b>{{hotel_legal_name}}</b> (trading as {{hotel_trading_name}})'
    )
    contract.company.legal_entity_name = 'HOAN KIEM T&T CO., LTD'
    contract.property_name = 'Hilton Garden Inn A&B'

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
        escape_for_paragraph=True,
    )

    assert rendered == (
        '<b>HOAN KIEM T&amp;T CO., LTD</b> '
        '(trading as Hilton Garden Inn A&amp;B)'
    )
    assert ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    ) == (
        '<b>HOAN KIEM T&T CO., LTD</b> '
        '(trading as Hilton Garden Inn A&B)'
    )


def test_hilton_pdf_renders_ampersands_literally_in_parties_and_zone_table():
    contract = _contract(
        '{{hotel_legal_name}} (trading as {{hotel_trading_name}})<br/>'
        '{{service_product_managed_name}}<br/>{{zones_table}}'
    )
    contract.company.legal_entity_name = 'HOAN KIEM T&T CO., LTD'
    contract.property_name = 'Hilton Garden Inn A&B'
    contract.service_locations = FakeRelatedManager([
        _service_location(
            custom_service_name='Rhythm&Breeze',
            location_name='Lobby&Atrium',
        ),
    ])
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    response = view._generate_principal_terms_pdf(contract)
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(response.content)).pages)

    assert response.status_code == 200
    assert 'HOAN KIEM T&T CO., LTD' in text
    assert 'Hilton Garden Inn A&B' in text
    assert 'Rhythm&Breeze - Managed' in text
    assert 'Lobby&Atrium' in text
    assert 'T&T;' not in text
    assert 'A&B;' not in text
    assert 'Rhythm&Breeze;' not in text
    assert 'Lobby&Atrium;' not in text


def test_existing_numeric_zone_variable_gets_singular_grammar():
    contract = _contract('{{number_of_zones}} music zones')

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    )

    assert rendered == '1 music zone'


def test_multiline_service_location_counts_rendered_zones():
    contract = _contract('{{number_of_zones}}|{{music_zone_label}}')
    contract.service_locations = FakeRelatedManager([
        _service_location(location_name='Lobby\nPool Bar'),
    ])

    rendered = ContractViewSet()._substitute_template_variables(
        contract.preamble_template.content,
        contract,
    )

    assert rendered == '2|2 music zones'


def test_hilton_blockers_report_concrete_source_and_contract_conflicts():
    contract = _contract(
        '{{hotel_trading_name}} (trading as {{hotel_legal_name}})<br/>'
        'Soundtrack Your Brand - Managed<br/>'
        "Supplier Business License: 0105548025073<br/>[Enter Workman's Comp #]<br/>"
        'The insurance requirements are attached as Attachment B.'
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
    codes = {blocker['code'] for blocker in blockers}

    assert codes == {
        'service_product_mismatch',
        'unresolved_source_placeholders',
        'supplier_entity_identifier_mismatch',
        'reversed_legal_trading_names',
        'missing_attachment_b',
    }


def test_reversed_legal_trading_guard_handles_ampersands():
    contract = _contract(
        '{{hotel_trading_name}} (trading as {{hotel_legal_name}})<br/>'
        '{{service_product_managed_name}}'
    )
    contract.company.legal_entity_name = 'HOAN KIEM T&T CO., LTD'
    contract.property_name = 'Hilton Garden Inn Hanoi'

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert 'reversed_legal_trading_names' in {item['code'] for item in blockers}


def test_matching_attachment_stays_blocked_until_package_assembly_is_verified():
    contract = _contract(
        '{{hotel_legal_name}} (trading as {{hotel_trading_name}})<br/>'
        '{{service_product_managed_name}}<br/>{{music_zone_label}}<br/>'
        'The insurance requirements are attached as Attachment B.<br/>'
        '{{zones_table}} {{signature_blocks}}'
    )
    contract.contract_documents = FakeRelatedManager([
        SimpleNamespace(
            id='attachment-b-1',
            title='Hilton Attachment B - Insurance Requirements',
            document_type='insurance',
            is_official=True,
            uploaded_at=date(2026, 9, 7),
        ),
    ])

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert {item['code'] for item in blockers} == {'attachment_b_not_assembled'}


def test_attachment_gate_rejects_wrong_title_or_document_type():
    contract = _contract('{{service_product_managed_name}} The insurance requirements are attached as Attachment B.')
    contract.contract_documents = FakeRelatedManager([
        SimpleNamespace(
            id='wrong-type',
            title='Hilton Attachment B',
            document_type='generated',
            is_official=True,
            uploaded_at=date(2026, 9, 7),
        ),
        SimpleNamespace(
            id='wrong-title',
            title='General insurance certificate',
            document_type='insurance',
            is_official=True,
            uploaded_at=date(2026, 9, 7),
        ),
    ])

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert {item['code'] for item in blockers} == {'missing_attachment_b'}


def test_unresolved_variable_is_blocked_but_signature_execution_blanks_are_allowed():
    contract = _contract(
        'Authorized Representative: ____________________ Date: __________ '
        '{{service_product_managed_name}} {{unknown_legal_source}} {{zones_table}} {{ signature_blocks }}'
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert [item['code'] for item in blockers] == ['unresolved_template_variables']
    assert blockers[0]['evidence']['variables'] == ['unknown_legal_source']


def test_malformed_unresolved_template_tokens_are_blocked():
    contract = _contract(
        '{{service_product_managed_name}} {{workmans-comp-number}} '
        '{{ policy.number }} {{zones_table}}'
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
    unresolved = next(item for item in blockers if item['code'] == 'unresolved_template_variables')

    assert unresolved['evidence']['variables'] == ['policy.number', 'workmans-comp-number']


def test_unbalanced_template_token_delimiters_are_blocked():
    for malformed in (
        '{{unfinished_legal_source',
        'unfinished_legal_source}}',
        '{{zones_table}}}',
    ):
        contract = _contract(
            '{{service_product_managed_name}} {{zones_table}} ' + malformed
        )

        blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
        unresolved = next(item for item in blockers if item['code'] == 'unresolved_template_variables')

        assert unresolved['evidence']['variables'] == ['<malformed-template-delimiter>']


def test_unclosed_bracketed_source_placeholder_is_blocked():
    contract = _contract(
        "{{service_product_managed_name}} {{zones_table}} [Enter Workman's Comp #"
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
    unresolved = next(item for item in blockers if item['code'] == 'unresolved_source_placeholders')

    assert unresolved['evidence']['placeholders'] == ['<unclosed-bracketed-source-placeholder>']


def test_known_bmasia_contact_tokens_do_not_resolve_to_silent_blanks():
    contract = _contract(
        '{{service_product_managed_name}} {{bmasia_contact_name}} '
        '{{bmasia_contact_email}} {{zones_table}}'
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert 'missing_bmasia_contact' in {item['code'] for item in blockers}


def test_zone_heading_is_moved_across_trailing_template_page_break():
    bulk, heading, force_page_break = ContractViewSet._split_template_zones_preamble(
        'Prior legal text<br/><br/><b>Description of the Services:</b><br/>---<br/>'
    )

    assert bulk == 'Prior legal text'
    assert heading == '<b>Description of the Services:</b>'
    assert force_page_break is True


def test_zone_splitter_keeps_prior_page_content_out_of_heading_bundle():
    bulk, heading, force_page_break = ContractViewSet._split_template_zones_preamble(
        'Page six text<br/>---<br/>A. Products<br/><br/>B. Services<br/><br/>'
        '<b>Description of the Services:</b>'
    )

    assert 'Page six text<br/>---<br/>A. Products<br/><br/>B. Services' == bulk
    assert heading == '<b>Description of the Services:</b>'
    assert force_page_break is False


def test_template_render_has_no_footer_only_page_after_trailing_separator():
    contract = _contract('{{service_product_managed_name}}<br/>{{zones_table}}<br/>FINAL-HILTON-BODY<br/>---')
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    response = view._generate_principal_terms_pdf(contract)
    reader = PdfReader(BytesIO(response.content))
    final_page_text = reader.pages[-1].extract_text()

    assert 'FINAL-HILTON-BODY' in final_page_text
    assert 'Page ' in final_page_text


def test_separator_immediately_after_zones_starts_a_new_page():
    contract = _contract('{{service_product_managed_name}}<br/>{{zones_table}}<br/>---<br/>AFTER-EXPLICIT-BREAK')
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    response = view._generate_principal_terms_pdf(contract)
    page_text = [page.extract_text() or '' for page in PdfReader(BytesIO(response.content)).pages]
    zones_page = next(i for i, text in enumerate(page_text) if 'Zone 1: Lobby' in text)
    after_page = next(i for i, text in enumerate(page_text) if 'AFTER-EXPLICIT-BREAK' in text)

    assert after_page > zones_page


def test_pdf_endpoint_returns_actionable_conflict_without_touching_existing_documents(monkeypatch):
    from crm_app.services import contract_service_locations

    contract = _contract("{{service_product_managed_name}} [Enter Workman's Comp #] {{zones_table}}")
    existing_document = SimpleNamespace(title='Previously signed HPA', is_official=True)
    contract.contract_documents = FakeRelatedManager([existing_document])
    view = ContractViewSet()
    view.get_object = lambda: contract
    monkeypatch.setattr(contract_service_locations, 'service_location_pricing_mismatch', lambda value: None)

    response = view.pdf(SimpleNamespace(), pk='ignored')

    assert response.status_code == 409
    assert response.data['contract_number'] == 'HK-TEST-1'
    assert existing_document in contract.contract_documents
    assert {item['code'] for item in response.data['blockers']} == {'unresolved_source_placeholders'}


def test_internal_rene_style_direct_render_cannot_bypass_hilton_preflight():
    contract = _contract("{{service_product_managed_name}} [Enter Workman's Comp #] {{zones_table}}")
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    response = view._generate_principal_terms_pdf(contract)

    assert response.status_code == 409
    assert {item['code'] for item in response.data['blockers']} == {'unresolved_source_placeholders'}


def test_mixed_contract_cannot_pass_with_one_static_product_label():
    contract = _contract('Soundtrack Your Brand - Managed {{zones_table}}')
    contract.service_locations = FakeRelatedManager([
        _service_location(platform='soundtrack', custom_service_name='', location_name='Lobby', price='380.00'),
        _service_location(platform='custom', custom_service_name='Beat Breeze', location_name='Pool', price='260.00'),
    ])

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    mismatch = next(item for item in blockers if item['code'] == 'service_product_mismatch')
    assert mismatch['evidence']['contract_labels'] == ['Soundtrack Your Brand', 'Beat Breeze']


def test_dynamic_product_token_cannot_mask_conflicting_static_product_label():
    contract = _contract(
        '{{service_product_managed_name}} Soundtrack Your Brand - Managed {{zones_table}}'
    )

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    mismatch = next(item for item in blockers if item['code'] == 'service_product_mismatch')
    assert mismatch['evidence']['template_labels'] == ['soundtrack your brand']
    assert mismatch['evidence']['contract_labels'] == ['Beat Breeze']


def test_whitespace_only_custom_product_is_missing():
    contract = _contract('{{service_product_managed_name}} {{zones_table}}')
    contract.service_locations = FakeRelatedManager([
        _service_location(custom_service_name='   '),
    ])

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert 'missing_service_product' in {item['code'] for item in blockers}


def test_hilton_template_cannot_switch_to_legacy_participation_renderer():
    contract = _contract('{{service_product_managed_name}} {{zones_table}}')
    contract.preamble_template.pdf_format = 'participation'
    view = ContractViewSet()

    response = view._generate_participation_agreement_pdf(contract)

    assert response.status_code == 409
    assert 'unsupported_hilton_pdf_format' in {item['code'] for item in response.data['blockers']}


def test_hilton_guard_survives_a_cosmetic_template_rename():
    contract = _contract('{{service_product_managed_name}} {{zones_table}}')
    contract.preamble_template.id = 12
    contract.preamble_template.name = 'Hilton 2026 refreshed display name'
    contract.preamble_template.pdf_format = 'participation'

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert ContractViewSet._is_hilton_full_template(contract) is True
    assert 'unsupported_hilton_pdf_format' in {item['code'] for item in blockers}


def test_stream_only_hilton_alias_stays_on_full_template_safety_path():
    contract = _contract(
        '{{service_product_managed_name}} {{zones_table}} '
        'The insurance requirements are attached as Attachment B.'
    )
    contract.preamble_template.name = 'Hilton International — Stream-only'

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert ContractViewSet._is_hilton_full_template(contract) is True
    assert 'missing_attachment_b' in {item['code'] for item in blockers}

    contract.preamble_template.pdf_format = 'participation'
    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)
    assert 'unsupported_hilton_pdf_format' in {item['code'] for item in blockers}


def test_spaced_zones_token_is_rendered_once_without_literal_leak():
    contract = _contract('{{service_product_managed_name}} {{ zones_table }}')
    view = ContractViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    response = view._generate_principal_terms_pdf(contract)
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(response.content)).pages)

    assert response.status_code == 200
    assert '{{ zones_table }}' not in text
    assert text.count('Zone 1: Lobby') == 1



def test_blank_service_location_name_is_blocked():
    contract = _contract('{{service_product_managed_name}} {{zones_table}}')
    contract.service_locations = FakeRelatedManager([
        _service_location(location_name=''),
    ])

    blockers = ContractViewSet()._hilton_template_pdf_blockers(contract)

    assert 'missing_service_location_name' in {item['code'] for item in blockers}


def test_hilton_pdf_conflict_stops_contract_email_before_log_or_smtp(monkeypatch):
    from rest_framework.response import Response

    from crm_app.services import email_service as email_service_module

    contract = SimpleNamespace(
        id='contract-1',
        company=SimpleNamespace(
            name='Lihe Hilton Garden Inn',
            legal_entity_name='Lihe Garden Inn Co., Ltd.',
            contacts=FakeRelatedManager([]),
        ),
        preamble_template=SimpleNamespace(name='Hilton International'),
        contract_number='HK-TEST-1',
        currency='USD',
        value=Decimal('260.00'),
        end_date=date(2027, 9, 30),
        status='Draft',
    )
    contract_lookup = SimpleNamespace(get=lambda **kwargs: contract)
    monkeypatch.setattr(
        email_service_module.Contract.objects,
        'select_related',
        lambda *args, **kwargs: contract_lookup,
    )

    calls = {'email_logs': 0, 'smtp': 0}

    def unexpected_email_log(*args, **kwargs):
        calls['email_logs'] += 1
        raise AssertionError('blocked PDF must not create an EmailLog')

    def unexpected_smtp_send(*args, **kwargs):
        calls['smtp'] += 1
        raise AssertionError('blocked PDF must not reach SMTP')

    monkeypatch.setattr(email_service_module.EmailLog.objects, 'create', unexpected_email_log)
    monkeypatch.setattr(email_service_module.EmailMultiAlternatives, 'send', unexpected_smtp_send)

    blocker = {
        'code': 'unresolved_source_placeholders',
        'detail': "Replace [Enter Workman's Comp #] with verified source data.",
    }
    monkeypatch.setattr(
        ContractViewSet,
        'pdf',
        lambda self, request, pk=None: Response(
            {
                'error': 'Contract PDF generation blocked',
                'contract_number': contract.contract_number,
                'blockers': [blocker],
            },
            status=409,
        ),
    )

    success, message = email_service_module.EmailService().send_contract_email(
        contract_id=contract.id,
        recipients=['joan.deng@hilton.com'],
        subject='Hilton Participation Agreement',
        body='Please review the attached agreement.',
    )

    assert success is False
    assert message == {
        'error': 'Contract PDF generation blocked',
        'contract_number': 'HK-TEST-1',
        'blockers': [blocker],
        'status_code': 409,
    }
    assert calls == {'email_logs': 0, 'smtp': 0}
    assert contract.status == 'Draft'


def test_contract_send_endpoint_preserves_structured_pdf_blockers(monkeypatch):
    from crm_app.services.email_service import EmailService

    contract = SimpleNamespace(
        id='contract-1',
        status='Draft',
        refresh_from_db=lambda: (_ for _ in ()).throw(
            AssertionError('blocked send must not refresh a supposedly sent contract')
        ),
    )
    blocker = {
        'code': 'missing_attachment_b',
        'detail': 'Attach the verified Hilton insurance exhibit before rendering.',
    }
    service_payload = {
        'error': 'Contract PDF generation blocked',
        'contract_number': 'HK-TEST-1',
        'blockers': [blocker],
        'status_code': 409,
    }
    monkeypatch.setattr(
        EmailService,
        'send_contract_email',
        lambda self, **kwargs: (False, service_payload),
    )

    view = ContractViewSet()
    view.get_object = lambda: contract
    view.log_action = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError('blocked send must not write a sent audit action')
    )
    response = view.send(
        SimpleNamespace(
            data={
                'recipients': ['joan.deng@hilton.com'],
                'subject': 'Hilton Participation Agreement',
                'body': 'Please review the attached agreement.',
            },
        ),
        pk=contract.id,
    )

    assert response.status_code == 409
    assert response.data == {
        'error': 'Contract PDF generation blocked',
        'contract_number': 'HK-TEST-1',
        'blockers': [blocker],
    }
