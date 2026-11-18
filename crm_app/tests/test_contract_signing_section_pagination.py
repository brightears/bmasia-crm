"""The execution section of a contract PDF stays on one page when it fits.

17 Nov 2026: with a primary customer signer and two witnesses (three signer
pairs), the supplier and the primary signer printed at the foot of one page
and both witnesses at the top of the next. Two pairs were already kept
together; three or more were not, and the heading of the opt-in witness
layout and of the master and participation formats could be left at a page
foot. The fix changes page flow only.

Each sweep lengthens the content before the execution section one step at a
time, so the page foot falls at every point of the section, and compares each
render with the same render on the old page flow. All names and wording here
are made up.
"""
from datetime import date
from decimal import Decimal
import re

import pytest
from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app import contract_pdf_v2
from crm_app.commercial_pdf import CONTENT_WIDTH, document_styles
from crm_app.contract_pdf_v2 import _flowables
from crm_app.models import Company, Contract, ContractTemplate, User
from crm_app.tests.test_contract_layout_regressions import _compact, _render
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db

FILLER = 'The Parties confirm that this clause is part of the agreed principal terms. '
PRIMARY = 'Alex Morgan'
SUPPLIER = 'Chris Andrews'
IN_WITNESS = 'IN WITNESS WHEREOF, the parties have duly executed this Agreement as of the Effective Date.'
CONTACTS = re.compile(r'\b\d+\. Contacts:')


@pytest.fixture(autouse=True)
def reviewer():
    return User.objects.create_user(username='signing-flow-reviewer', role='Admin', is_active=True)


def _witnesses(count):
    return [{'name': f'Sam Example {n}', 'title': f'Example Witness Title {n}', 'role': 'Witness'}
            for n in range(1, count + 1)]


_SERIAL = iter(range(1, 1_000_000))


def _contract(tag, *, preamble='', signers=1, template=None, category='standard', custom_terms=''):
    # The same tag renders the same document (the old-flow comparison).
    company, _ = Company.objects.get_or_create(name=f'Example Hotel {tag}', defaults=dict(
        legal_entity_name='Example Hotel Co., Ltd.', address_line1='1 Example Road',
        city='Bangkok', country='Thailand', billing_entity='BMAsia (Thailand) Co., Ltd.',
    ))
    contract = Contract.objects.create(
        company=company, contract_number=f'DRAFT-SIGNING-{tag}-{next(_SERIAL)}',
        contract_type='Annual', contract_category=category, status='Draft',
        is_active=False, start_date=date(2026, 8, 1), end_date=date(2027, 7, 31),
        value=Decimal('8000'), price_per_zone=Decimal('8000'), tax_rate=Decimal('7'),
        currency='THB', billing_frequency='Annual',
        customer_contact_name='Jordan Example', customer_contact_email='jordan@example.com',
        bmasia_contact_name='Example Coordinator', bmasia_contact_email='coordinator@example.com',
        bmasia_contact_title='Example Title',
        customer_signatory_name=PRIMARY, customer_signatory_title='Director',
        additional_customer_signatories=_witnesses(signers - 1),
        preamble_custom=preamble, preamble_template=template, custom_terms=custom_terms,
    )
    contract.service_locations.create(location_name='Lobby', platform='soundtrack', price=Decimal('8000'))
    Contract.objects.filter(pk=contract.pk).update(tax_amount=Decimal('560'), total_value=Decimal('8560'))
    contract.refresh_from_db()
    return contract


def _pages(contract):
    return [_compact(page.extract_text() or '') for page in _render(contract).pages]


def _old_flow_pages(build, monkeypatch):
    """The same document on the page flow before this fix."""
    with monkeypatch.context() as patch:
        patch.setattr(contract_pdf_v2, '_keep_execution_section', lambda items, width: items, raising=False)
        patch.setattr(contract_pdf_v2, '_keep_execution_intro_with_table',
                      lambda items, width: items, raising=False)
        return _pages(build())


def _found(pages, phrase):
    return [number for number, text in enumerate(pages) if phrase in text]


def _assert_no_blank_page(pages, contract):
    header = {contract.contract_number, 'BMAsia (Thailand) Co., Ltd.', 'bmasiamusic.com', '|'}
    for number, text in enumerate(pages):
        body = re.sub(r'\b\d+ / \d+\b', ' ', text)
        for word in header:
            body = body.replace(word, ' ')
        body = re.sub(r'\b[A-Z ]{6,}\b', ' ', body, count=1)  # running title
        assert body.strip(), f'page {number + 1} carries only the page header'


def _sweep(build, markers, monkeypatch, steps):
    """Render each step; every marker must sit on one page, which must vary."""
    section_pages, split_before = set(), 0
    for step in steps:
        contract = build(step)
        pages = _pages(contract)
        where = {marker: _found(pages, marker) for marker in markers}
        assert all(len(found) == 1 for found in where.values()), (step, where)
        assert len({found[0] for found in where.values()}) == 1, (step, where)
        section_pages.add(where[markers[0]][0])
        _assert_no_blank_page(pages, contract)
        old = _old_flow_pages(lambda: build(step), monkeypatch)
        assert len(pages) <= len(old) + 1, (step, len(old), len(pages))
        old_where = {marker: _found(old, marker) for marker in markers}
        if len({found[0] for found in old_where.values() if found}) > 1:
            split_before += 1
        else:
            # A section that was not split keeps its page breaks.
            assert pages == old, step
    # The sweep must cross a page foot, or it proves nothing.
    assert len(section_pages) >= 2, section_pages
    return split_before


def _standard_markers(signers):
    return ['Contacts:', SUPPLIER, f'{PRIMARY} Director'] + [
        witness['name'] for witness in _witnesses(signers - 1)]


@pytest.mark.parametrize('signers', [1, 2, 3])
def test_standard_execution_section_shares_one_page_at_every_page_foot(signers, monkeypatch):
    def build(step):
        return _contract(f'std-{signers}-{step}', signers=signers,
                         preamble='This agreement is made between the Parties. ' + FILLER * step)

    # One step adds less than a line, so the page foot meets every line.
    steps = range(0, 72, 2 if signers == 1 else 1)
    split_before = _sweep(build, _standard_markers(signers), monkeypatch, steps)
    if signers == 3:
        # The reported defect: three pairs split on the old page flow.
        assert split_before > 0


def test_template_execution_section_keeps_its_in_witness_line(monkeypatch):
    def build(step):
        # A fixed id outside the ids that select maintained corporate sources.
        template, _ = ContractTemplate.objects.update_or_create(pk=901, defaults=dict(
            name='Example execution agreement', template_type='preamble', pdf_format='standard',
            content=('<b>1. Example term</b><br/>The Parties agree to this example wording.<br/><br/>'
                     '{{zones_table}}<br/><br/>' + FILLER * step + '<br/><br/>' + IN_WITNESS
                     + '<br/><br/>{{signature_blocks}}<br/><br/><b>Annex 1</b><br/>Example annex wording.'),
        ))
        return _contract(f'tpl-{step}', signers=3, template=template)

    markers = ['IN WITNESS WHEREOF', SUPPLIER, PRIMARY] + [w['name'] for w in _witnesses(2)]
    assert _sweep(build, markers, monkeypatch, range(0, 96, 2)) > 0


def test_opt_in_witness_layout_keeps_its_in_witness_line(monkeypatch):
    def build(step):
        # The opt-in layout is limited to approved template sources; the
        # synthetic template takes one of their ids and a made-up name.
        template, _ = ContractTemplate.objects.update_or_create(pk=11, defaults=dict(
            name='Example hotel agreement', template_type='preamble', pdf_format='standard',
            content=('<b>1. Example term</b><br/>The Parties agree to this example wording.<br/><br/>'
                     '{{zones_table}}<br/><br/>' + FILLER * step + '<br/><br/>' + IN_WITNESS
                     + '<br/><br/>{{signature_blocks_hotel_2_witness_4}}<br/><br/>'
                       '<b>Annex 1</b><br/>Example annex wording.'),
        ))
        contract = _contract(f'wit-{step}', template=template)
        Contract.objects.filter(pk=contract.pk).update(
            customer_signatory_name='', customer_signatory_title='', additional_customer_signatories=[])
        contract.refresh_from_db()
        return contract

    markers = ['IN WITNESS WHEREOF', SUPPLIER, 'Authorized Signatory Name:']
    split_before = _sweep(build, markers, monkeypatch, range(0, 96, 1))
    assert split_before > 0
    pages = _pages(build(40))
    signing = [text for text in pages if SUPPLIER in text]
    assert signing[0].count('Witness') == 4
    assert signing[0].count('Authorized Signatory') == 2


@pytest.mark.parametrize('category', ['corporate_master', 'participation'])
def test_signatures_heading_stays_with_the_signature_table(category, monkeypatch):
    def build(step):
        return _contract(f'{category}-{step}', category=category,
                         custom_terms='Example additional wording. ' + FILLER * step)

    markers = ['SIGNATURES', f'Authorized Representative {PRIMARY}',
               'Date: _________________ Date: _________________']
    assert _sweep(build, markers, monkeypatch, range(0, 120, 2)) > 0


def test_execution_section_taller_than_a_page_splits_only_between_signer_rows(monkeypatch):
    # Seven customer signers: taller than one page, so the section may split.
    witnesses = _witnesses(6)
    for step in range(0, 40, 3):
        contract = _contract(f'tall-{step}', signers=7,
                             preamble='This agreement is made between the Parties. ' + FILLER * step)
        pages = _pages(contract)
        _assert_no_blank_page(pages, contract)
        heading = [n for n, text in enumerate(pages) if CONTACTS.search(text)]
        assert len(heading) == 1
        # The heading never sits alone: the supplier and primary signer follow it.
        assert _found(pages, SUPPLIER) == heading == _found(pages, f'{PRIMARY} Director')
        for witness in witnesses:
            # Each signer block (line, name, title, entity, date) stays whole.
            block = (f"{witness['name']} WITNESS {witness['title']} "
                     'Example Hotel Co., Ltd. Date: _________________')
            assert len(_found(pages, block)) == 1, (step, witness['name'])
        old = _old_flow_pages(lambda: _contract(f'tall-{step}', signers=7, preamble=(
            'This agreement is made between the Parties. ' + FILLER * step)), monkeypatch)
        assert len(pages) <= len(old) + 1


def test_in_witness_line_and_three_signer_pairs_form_one_kept_group():
    styles = document_styles()
    contract = _contract('unit', signers=3)
    source = ContractViewSet()._build_signature_blocks_table(
        contract, 'BMAsia (Thailand) Co., Ltd.', 'BMAsia (Thailand) Co., Ltd.')
    flow = _flowables([
        Paragraph('Example closing clause.', styles['body']),
        Spacer(1, 20),
        Paragraph(IN_WITNESS, styles['body']),
        Spacer(1, 20),
        source,
    ], CONTENT_WIDTH, styles)
    kept = [item for item in flow if isinstance(item, KeepTogether)]
    assert len(kept) == 1
    content = kept[0]._content
    assert content[0].getPlainText() == IN_WITNESS
    assert getattr(content[-1], '_bmasia_signature_pairs', False)
    assert len(content[-1]._cellvalues) == 3
    assert flow[0].getPlainText() == 'Example closing clause.'
