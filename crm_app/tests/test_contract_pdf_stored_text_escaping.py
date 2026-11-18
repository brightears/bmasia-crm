"""Stored CRM text must print exactly as stored in every contract PDF.

ReportLab parses Paragraph source as markup. A stored value such as
"Senior F&B Executive" used to print as "Senior F&B; Executive" (``&B`` was
read as an unknown entity), and a value such as "Head <Ops>" lost "<Ops>".

Two kinds of stored text reach contract Paragraphs:

* plain values (names, titles, emails, legal names, addresses, zone and
  service names, template variables). Each must be escaped exactly once, so
  ``&``, ``<``, ``>``, a literal ``&amp;`` and an already-escaped-looking
  ``&lt;x&gt;`` all print verbatim;
* wording fields that are markup by design (custom preamble, payment and
  activation wording in the standard agreement, additional terms, template and
  corporate clause text). Their tags and entities keep working; only a bare
  ``&`` or a stray ``<`` that cannot start a tag is escaped.

All fixtures are synthetic. Rendering runs with PDF activity logging
suppressed and must not write to the database.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
import re
from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from pypdf import PdfReader

from crm_app.models import (
    Company, Contact, Contract, ContractLineItem, ContractTemplate, CorporatePdfTemplate,
)
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db


# Plain stored values. Every one contains a bare "&" between letters (the
# reported corruption), and most carry a tag-like "<...>", a literal "&amp;",
# quotes or an already-escaped-looking "&lt;...&gt;".
LEGAL_NAME = 'Example A&B Hotel Co., Ltd. <HQ>'
ADDRESS_LINE = '9 R&D Road <Unit 3>'
PROPERTY_NAME = 'Example P&L Property'
ZONE_NAME = 'F&B Lounge <L1>'
CUSTOM_ZONE_NAME = 'Spa &amp; Pool'
CUSTOM_SERVICE = 'Mood&Tone <Pro>'
CONTACT_NAME = 'Jo "Sam" O\'Neil & Co'
CONTACT_TITLE = 'Senior F&B Executive &amp; <Ops>'
CONTACT_EMAIL = 'ops&b@example.com'
BMA_CONTACT_NAME = 'Example Lead & Q<A Desk'
BMA_CONTACT_TITLE = 'Q&A Manager <Ops>'
BMA_CONTACT_EMAIL = 'lead+q&a@example.com'
SIGNER_NAME = 'Signer &lt;One&gt;'
SIGNER_TITLE = 'CEO R&D'
BMA_SIGNER_NAME = 'Supplier T&T Signer'
BMA_SIGNER_TITLE = 'Director <Sales>'
WITNESS_NAME = 'Witness W&W'
WITNESS_TITLE = 'F&A Officer'
SERVICE_ITEM_NAME = 'Playlist A&B <Set>'
SERVICE_ITEM_DESCRIPTION = 'Covers F&B "lounge" areas'
LINE_ITEM = 'Music&Media <Pack>'
PAYMENT_SCHEDULE = 'Two parts: 50&50 <split>'

PLAIN_VALUES = [
    LEGAL_NAME, ADDRESS_LINE, ZONE_NAME, CUSTOM_ZONE_NAME, CUSTOM_SERVICE,
    CONTACT_NAME, CONTACT_TITLE, CONTACT_EMAIL, BMA_CONTACT_NAME, BMA_CONTACT_TITLE,
    BMA_CONTACT_EMAIL, SIGNER_NAME, SIGNER_TITLE, BMA_SIGNER_NAME,
    BMA_SIGNER_TITLE, WITNESS_NAME, WITNESS_TITLE, SERVICE_ITEM_NAME,
    SERVICE_ITEM_DESCRIPTION, LINE_ITEM, PAYMENT_SCHEDULE,
]

# Wording fields that are markup by design, with the text each must print.
PREAMBLE_CUSTOM = '<b>Preamble</b> for the F&B outlets of {{legal_entity_name}}; price < 100.'
PREAMBLE_PRINTED = f'Preamble for the F&B outlets of {LEGAL_NAME}; price < 100.'
PAYMENT_CUSTOM = 'Pay F&B invoices &amp; fees within 30 days to {{issuer_name}}.'
PAYMENT_PRINTED = 'Pay F&B invoices & fees within 30 days to BMAsia Limited.'
ACTIVATION_CUSTOM = 'Activate F&B zones <b>promptly</b>; x<y applies.'
ACTIVATION_PRINTED = 'Activate F&B zones promptly; x<y applies.'
ADDITIONAL_TERMS = 'Extra F&B term with <b>bold</b> words.'
ADDITIONAL_PRINTED = 'Extra F&B term with bold words.'
PLACED_DURATION = 'Duration note for R&D <i>teams</i>.'
PLACED_DURATION_PRINTED = 'Duration note for R&D teams.'
CUSTOM_TERMS = f'{ADDITIONAL_TERMS}\n[under: duration]\n{PLACED_DURATION}'

# ReportLab's misreading of a bare "&" leaves e.g. "F&B;" in the text layer.
ENTITY_ARTEFACT = re.compile(r'\w&\w+;')


def _company(name='Example Hotel Co.', **extra):
    return Company.objects.create(
        name=name, legal_entity_name=LEGAL_NAME, country='Vietnam', city='Example City',
        address_line1=ADDRESS_LINE, billing_entity='BMAsia Limited', **extra,
    )


@pytest.fixture
def agreement():
    agreement = Contract.objects.create(
        company=_company(), contract_number='DRAFT-ESCAPE-TEST',
        contract_type='Annual', contract_category='standard', status='Draft',
        start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('1000.00'), total_value=Decimal('1000.00'),
        tax_rate=Decimal('0.00'), currency='USD', billing_frequency='Annual',
        property_name=PROPERTY_NAME,
        customer_contact_name=CONTACT_NAME, customer_contact_title=CONTACT_TITLE,
        customer_contact_email=CONTACT_EMAIL,
        bmasia_contact_name=BMA_CONTACT_NAME, bmasia_contact_title=BMA_CONTACT_TITLE,
        bmasia_contact_email=BMA_CONTACT_EMAIL,
        customer_signatory_name=SIGNER_NAME, customer_signatory_title=SIGNER_TITLE,
        bmasia_signatory_name=BMA_SIGNER_NAME, bmasia_signatory_title=BMA_SIGNER_TITLE,
        additional_customer_signatories=[
            {'name': WITNESS_NAME, 'title': WITNESS_TITLE, 'role': 'Witness'},
        ],
        custom_service_items=[{'name': SERVICE_ITEM_NAME, 'description': SERVICE_ITEM_DESCRIPTION}],
        payment_schedule=PAYMENT_SCHEDULE,
    )
    agreement.service_locations.create(location_name=ZONE_NAME, platform='soundtrack', sort_order=0)
    agreement.service_locations.create(
        location_name=CUSTOM_ZONE_NAME, platform='custom',
        custom_service_name=CUSTOM_SERVICE, sort_order=1,
    )
    ContractLineItem.objects.create(
        contract=agreement, product_service=LINE_ITEM, quantity=Decimal('1'),
        unit_price=Decimal('1000.00'), line_total=Decimal('1000.00'),
    )
    return agreement


def _render(agreement):
    before = Contract.objects.values().get(pk=agreement.pk)
    view = ContractViewSet()
    view.get_object = lambda: agreement
    view.request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=False),
        _bmasia_suppress_pdf_activity=True,
    )
    with CaptureQueriesContext(connection) as queries:
        response = view.pdf(view.request, pk=agreement.pk)
    assert response.status_code == 200, getattr(response, 'data', None)
    assert response['X-BMAsia-Renderer'] == 'contract-v2'
    assert not [q['sql'] for q in queries.captured_queries
                if re.match(r'^\s*(INSERT|UPDATE|DELETE)\b', q['sql'], re.I)]
    assert Contract.objects.values().get(pk=agreement.pk) == before
    reader = PdfReader(BytesIO(response.content))
    return ' '.join(' '.join(page.extract_text() for page in reader.pages).split())


def _assert_printed(text, *expected):
    missing = [value for value in expected if ' '.join(value.split()) not in text]
    assert not missing, (missing, text)
    # Outside the expected values (one of which legitimately looks escaped),
    # no "&" may have been read as an entity.
    residue = text
    for value in sorted({*expected, *PLAIN_VALUES}, key=len, reverse=True):
        residue = residue.replace(' '.join(value.split()), ' ')
    assert not ENTITY_ARTEFACT.findall(residue), ENTITY_ARTEFACT.findall(residue)
    # Code-built markup still renders as formatting, never as visible tags.
    assert '<b>' not in text and '</b>' not in text and '<br/>' not in text


def _category(agreement, category):
    agreement.contract_category = category
    if category == 'participation':
        master_company = Company.objects.create(
            name='Example Group', legal_entity_name='Example Group Q&A Holdings <Parent>',
            country='Vietnam', billing_entity='BMAsia Limited',
        )
        agreement.master_contract = Contract.objects.create(
            company=master_company, contract_number='MASTER-ESCAPE-TEST',
            contract_category='corporate_master', status='Draft',
            start_date=agreement.start_date, end_date=agreement.end_date,
            value=agreement.value, currency=agreement.currency,
        )
    agreement.save()


def test_standard_agreement_prints_every_plain_stored_value_as_stored(agreement):
    text = _render(agreement)
    _assert_printed(
        text, f'{LEGAL_NAME}, with registered address at {ADDRESS_LINE}, Example City, Vietnam (Client).',
        ADDRESS_LINE, PROPERTY_NAME, ZONE_NAME, CUSTOM_ZONE_NAME,
        CUSTOM_SERVICE, f'{CONTACT_NAME}, {CONTACT_TITLE}', f'E: {CONTACT_EMAIL}',
        f'{BMA_CONTACT_NAME}, {BMA_CONTACT_TITLE}', f'E: {BMA_CONTACT_EMAIL}',
        SIGNER_NAME, SIGNER_TITLE, BMA_SIGNER_NAME, BMA_SIGNER_TITLE,
        WITNESS_NAME, WITNESS_TITLE, SERVICE_ITEM_NAME, SERVICE_ITEM_DESCRIPTION,
        LINE_ITEM, PAYMENT_SCHEDULE,
    )
    # The legal name prints in the preamble, the identity card and the
    # customer signature block; the witness repeats it once more.
    assert text.count(LEGAL_NAME) >= 4


def test_standard_agreement_default_custom_package_prints_service_name(agreement):
    agreement.custom_service_items = []
    agreement.save()
    agreement.service_locations.filter(platform='soundtrack').delete()
    text = _render(agreement)
    _assert_printed(text, f'Curation and content lease for the {CUSTOM_SERVICE} package')


def test_standard_agreement_keeps_markup_in_wording_fields(agreement):
    agreement.preamble_custom = PREAMBLE_CUSTOM
    agreement.payment_custom = PAYMENT_CUSTOM
    agreement.activation_custom = ACTIVATION_CUSTOM
    agreement.custom_terms = CUSTOM_TERMS
    agreement.save()
    text = _render(agreement)
    _assert_printed(
        text, PREAMBLE_PRINTED, PAYMENT_PRINTED, ACTIVATION_PRINTED,
        ADDITIONAL_PRINTED, PLACED_DURATION_PRINTED, CONTACT_TITLE,
    )
    # Markup in these fields is formatting, and their entities are decoded.
    assert '<i>' not in text and 'invoices &amp;' not in text


def test_standard_agreement_template_wording_substitutes_escaped_values(agreement):
    agreement.payment_template = ContractTemplate.objects.create(
        name='Example payment wording', template_type='payment', pdf_format='standard',
        content='Invoices go to <b>{{legal_entity_name}}</b> at {{client_address}}.',
    )
    agreement.activation_template = ContractTemplate.objects.create(
        name='Example activation wording', template_type='activation', pdf_format='standard',
        content='Activation contact: {{contact_title}} for {{venue_names}}.',
    )
    agreement.save()
    text = _render(agreement)
    _assert_printed(
        text,
        f'Invoices go to {LEGAL_NAME} at {ADDRESS_LINE}, Example City, Vietnam.',
        f'Activation contact: {CONTACT_TITLE} for {ZONE_NAME}, {CUSTOM_ZONE_NAME}.',
    )


def test_full_template_agreement_escapes_variables_once_and_keeps_template_markup(agreement):
    agreement.preamble_template = ContractTemplate.objects.create(
        name='Example full agreement', template_type='preamble', pdf_format='standard',
        content=(
            '<b>Client:</b> {{legal_entity_name}}<br/>'
            'Trading as {{hotel_trading_name}}<br/>'
            'Contact: {{contact_name}}, {{contact_title}}, {{contact_email}}<br/>'
            'Venues: {{venue_names}}<br/>'
            'Address: {{client_address}}<br/>'
            'Signer: {{client_signatory_name}}, {{client_signatory_title}}<br/>'
            'Services: {{service_items}}<br/>'
            '{{zones_table}}<br/>{{additional_terms}}<br/>{{signature_blocks}}'
        ),
    )
    agreement.custom_terms = 'Template-mode terms for F&B <Ops> stay plain &amp; literal.'
    agreement.save()
    text = _render(agreement)
    _assert_printed(
        text,
        f'Client: {LEGAL_NAME}',
        f'Trading as {PROPERTY_NAME}',
        f'Contact: {CONTACT_NAME}, {CONTACT_TITLE}, {CONTACT_EMAIL}',
        f'Venues: {ZONE_NAME}, {CUSTOM_ZONE_NAME}',
        f'Address: {ADDRESS_LINE}, Example City, Vietnam',
        f'Signer: {SIGNER_NAME}, {SIGNER_TITLE}',
        f'Services: {SERVICE_ITEM_NAME}: {SERVICE_ITEM_DESCRIPTION}',
        'Template-mode terms for F&B <Ops> stay plain &amp; literal.',
        BMA_SIGNER_NAME, BMA_SIGNER_TITLE, WITNESS_NAME, WITNESS_TITLE,
        CUSTOM_SERVICE,
    )


@pytest.mark.parametrize('category', ['corporate_master', 'participation'])
def test_master_and_participation_agreements_print_stored_values(agreement, category):
    _category(agreement, category)
    agreement.billing_frequency = 'Q&A <Yr>'
    agreement.custom_terms = CUSTOM_TERMS
    agreement.preamble_custom = 'Plain preamble for F&B <Ops>.'
    agreement.save()
    text = _render(agreement)
    expected = [
        LEGAL_NAME, SIGNER_NAME, SIGNER_TITLE, BMA_SIGNER_NAME, BMA_SIGNER_TITLE,
        ADDITIONAL_PRINTED, PLACED_DURATION_PRINTED, PAYMENT_SCHEDULE,
        'Plain preamble for F&B <Ops>.',
    ]
    if category == 'corporate_master':
        expected.append('Billing Frequency: Q&A <Yr>')
    else:
        expected += ['Example Group Q&A Holdings <Parent>', ZONE_NAME, CUSTOM_ZONE_NAME,
                     'Q&A <Yr>']
    _assert_printed(text, *expected)


def test_corporate_participation_format_prints_stored_values(agreement):
    parent = Company.objects.create(
        name='Example Corporate Parent', country='Vietnam',
        billing_entity='BMAsia Limited', is_corporate_parent=True,
    )
    corporate_format = next(
        key for key, _label in CorporatePdfTemplate.TEMPLATE_FORMAT_CHOICES if key.endswith('_hpa')
    )
    CorporatePdfTemplate.objects.create(
        name='Example corporate layout', template_format=corporate_format, company=parent,
        warranty_text='Warranty covers F&B <b>areas</b> &amp; lounges.',
        legal_terms='Legal terms for F&B <b>lounges</b>; rate A<B applies.',
    )
    agreement.company.parent_company = parent
    agreement.company.save()
    Contact.objects.create(
        company=agreement.company, name=CONTACT_NAME, email=CONTACT_EMAIL,
        contact_type='Primary', title=CONTACT_TITLE,
    )
    _category(agreement, 'participation')
    agreement.payment_terms = 'Net 30 for F&B <Ops>'
    agreement.save()
    text = _render(agreement)
    _assert_printed(
        text, f'and {LEGAL_NAME} ("Hotel")', ZONE_NAME, CUSTOM_ZONE_NAME, 'Net 30 for F&B <Ops>.',
        'Warranty covers F&B areas & lounges.', 'Legal terms for F&B lounges; rate A<B applies.',
        CONTACT_NAME, CONTACT_EMAIL,
        SIGNER_NAME, SIGNER_TITLE, BMA_SIGNER_NAME, BMA_SIGNER_TITLE,
    )


def test_plain_values_are_escaped_once_and_wording_markup_is_left_intact():
    from crm_app.contract_pdf_v2 import paragraph_markup, paragraph_text

    for value in PLAIN_VALUES:
        escaped = paragraph_text(value)
        assert '<' not in escaped and '>' not in escaped
        assert re.sub(r'&(amp|lt|gt);', '', escaped).count('&') == 0
    assert paragraph_text(None) == ''
    assert paragraph_text('&amp;') == '&amp;amp;'

    markup = '<b>Bold</b> F&B &amp; &#160; &nbsp; <br/> x<y and 1 < 2 <font size="9">z</font>'
    guarded = paragraph_markup(markup)
    assert guarded == (
        '<b>Bold</b> F&amp;B &amp; &#160; &nbsp; <br/> x&lt;y and 1 &lt; 2 z'
    )
    # Guarding is idempotent, so already-guarded or escaped text never doubles.
    assert paragraph_markup(guarded) == guarded
    assert paragraph_markup(paragraph_text(CONTACT_TITLE)) == paragraph_text(CONTACT_TITLE)
