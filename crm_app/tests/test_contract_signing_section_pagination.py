"""The execution section of a contract PDF stays on one page when it fits.

17 Nov 2026: with a primary customer signer and two witnesses (three signer
pairs), the supplier and the primary signer printed at the foot of one page
and both witnesses at the top of the next. Two pairs were already kept
together; three or more were not, and the opening line of a section (the
Contacts clause, an IN WITNESS line, the line a template places before its
signature token, the SIGNATURES heading) could be left at a page foot. The
fix changes page flow only.

Each sweep lengthens the content before the execution section one step at a
time, so the page foot falls at every point of the section, and compares each
render with the same render on the old page flow. All names and wording here
are made up; the supplier signer is set explicitly to an invented name.
"""
from datetime import date
from decimal import Decimal
import re

import pytest
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

from crm_app import contract_pdf_v2
from crm_app.commercial_pdf import CONTENT_WIDTH, document_styles
from crm_app.contract_pdf_v2 import _flowables, markup_as_text
from crm_app.models import Company, Contract, ContractTemplate, User
from crm_app.tests.test_contract_layout_regressions import _compact, _render
from crm_app.views import ContractViewSet

pytestmark = pytest.mark.django_db

FILLER = 'The Parties confirm that this clause is part of the agreed principal terms. '
PRIMARY = 'Alex Morgan'
SUPPLIER = 'Casey Provider'
ENTITY = 'BMAsia (Thailand) Co., Ltd.'
IN_WITNESS = 'IN WITNESS WHEREOF, the parties have duly executed this Agreement as of the Effective Date.'
CONTACTS = re.compile(r'\b\d+\. Contacts:')
LONG_TITLE = ('Executive Director for Regional Example Operations, Example Asset Planning, '
              'Example Venue Standards, Example Partner Relations '
              'and Example Guest Programmes')


@pytest.fixture(autouse=True)
def reviewer():
    return User.objects.create_user(username='signing-flow-reviewer', role='Admin', is_active=True)


def _witnesses(count, *, long=False):
    return [{'name': (f'Sam Example-Longername Placeholder {n}' if long else f'Sam Example {n}'),
             'title': (f'{LONG_TITLE} {n}' if long else f'Example Witness Title {n}'), 'role': 'Witness'}
            for n in range(1, count + 1)]


_SERIAL = iter(range(1, 1_000_000))


def _contract(tag, *, preamble='', signers=1, template=None, category='standard', custom_terms='',
              zones=1, long=False):
    # The same tag renders the same document (the old-flow comparison).
    company, _ = Company.objects.get_or_create(name=f'Example Hotel {tag}', defaults=dict(
        legal_entity_name='Example Hotel Co., Ltd.', address_line1='1 Example Road',
        city='Bangkok', country='Thailand', billing_entity=ENTITY,
    ))
    value = Decimal('8000') * zones
    contract = Contract.objects.create(
        company=company, contract_number=f'DRAFT-SIGNING-{tag}-{next(_SERIAL)}',
        contract_type='Annual', contract_category=category, status='Draft',
        is_active=False, start_date=date(2026, 8, 1), end_date=date(2027, 7, 31),
        value=value, price_per_zone=Decimal('8000'), tax_rate=Decimal('7'),
        currency='THB', billing_frequency='Annual',
        customer_contact_name='Jordan Example', customer_contact_email='jordan@example.com',
        bmasia_contact_name='Example Coordinator', bmasia_contact_email='coordinator@example.com',
        bmasia_contact_title='Example Title',
        bmasia_signatory_name=SUPPLIER, bmasia_signatory_title='Director',
        customer_signatory_name=PRIMARY, customer_signatory_title=LONG_TITLE if long else 'Director',
        additional_customer_signatories=_witnesses(signers - 1, long=long),
        preamble_custom=preamble, preamble_template=template, custom_terms=custom_terms,
    )
    for n in range(zones):
        contract.service_locations.create(location_name=f'Example Area {n + 1}', platform='soundtrack',
                                          price=Decimal('8000'))
    tax = (value * Decimal('0.07')).quantize(Decimal('0.01'))
    Contract.objects.filter(pk=contract.pk).update(tax_amount=tax, total_value=value + tax)
    contract.refresh_from_db()
    return contract


def _template(content):
    # A fixed id outside the ids that select maintained corporate sources.
    template, _ = ContractTemplate.objects.update_or_create(pk=901, defaults=dict(
        name='Example execution agreement', template_type='preamble', pdf_format='standard',
        content=content))
    return template


def _lines(count):
    return ''.join(f'Filler line {n}.<br/>' for n in range(1, count + 1))


def _pages(contract):
    return [_compact(page.extract_text() or '') for page in _render(contract).pages]


def _old_flow_pages(build, monkeypatch):
    """The same document on the page flow before this fix."""
    with monkeypatch.context() as patch:
        patch.setattr(contract_pdf_v2, '_keep_execution_section', lambda items, width: items, raising=False)
        patch.setattr(contract_pdf_v2, '_keep_execution_intro_with_table',
                      lambda items, width: items, raising=False)
        patch.setattr(contract_pdf_v2, '_mark_signing_lead', lambda items: None, raising=False)
        return _pages(build())


def _found(pages, phrase):
    return [number for number, text in enumerate(pages) if phrase in text]


def _assert_no_blank_page(pages, contract):
    header = {contract.contract_number, ENTITY, 'bmasiamusic.com', '|'}
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


# --- Whole documents --------------------------------------------------------

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
        return _contract(f'tpl-{step}', signers=3, template=_template(
            '<b>1. Example term</b><br/>The Parties agree to this example wording.<br/><br/>'
            '{{zones_table}}<br/><br/>' + FILLER * step + '<br/><br/>' + IN_WITNESS
            + '<br/><br/>{{signature_blocks}}<br/><br/><b>Annex 1</b><br/>Example annex wording.'))

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

    markers = ['SIGNATURES', f'{SUPPLIER} {PRIMARY}',
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


def test_signer_rows_win_when_the_table_fits_a_page_only_without_its_contacts_clause(monkeypatch):
    # Three signers with long titles: about 640 pt of signer rows, which fit a
    # page alone but not with the Contacts clause. The signers stay together
    # and no page is added where the old flow kept them together.
    names = [PRIMARY] + [w['name'] for w in _witnesses(2, long=True)]
    contacts_apart = 0
    for step in range(0, 56, 2):
        def build():
            return _contract(f'long-{step}', signers=3, zones=3, long=True,
                             preamble='This agreement is made between the Parties.<br/>' + _lines(step))
        contract = build()
        pages = _pages(contract)
        _assert_no_blank_page(pages, contract)
        signer_pages = {_found(pages, name)[0] for name in names} | set(_found(pages, SUPPLIER))
        assert len(signer_pages) == 1, (step, signer_pages)
        heading = [n for n, text in enumerate(pages) if CONTACTS.search(text)]
        # The clause heading never ends a page alone.
        assert heading == _found(pages, 'BMA: Example Coordinator'), step
        contacts_apart += heading[0] not in signer_pages
        old = _old_flow_pages(build, monkeypatch)
        if len({_found(old, name)[0] for name in names}) == 1:
            assert len(pages) <= len(old), step
    # The sweep must reach the band where only the table fits.
    assert contacts_apart > 0


SHAPES = {
    # The shapes the stored templates place before {{signature_blocks}},
    # with invented wording: a Contacts block; an IN WITNESS line with the
    # whole body before it; a numbered clause paragraph; a fee line after a
    # numbered list. Plus a line the text rules do not know, and an IN
    # WITNESS line that the formatting-tag fallback prints as plain text.
    'contacts-block': ('7. Contacts:', True, '<b>7.</b> Contacts:<br/>BMA: Example Coordinator, Example Title'
                       '<br/>E: coordinator@example.com<br/>CLIENT: Example Hotel<br/>E: client@example.com'
                       '<br/><br/><br/>'),
    'in-witness-whole-body': ('IN WITNESS WHEREOF', False, IN_WITNESS + '<br/><br/>'),
    'clause-paragraph': ('3.4 Example', True, '3.3 Example clause about support that runs to a short second line '
                         'of wording here.<br/><br/>3.4 Example clause text: the Client shall give the Provider '
                         'access to the example site promptly, provided that the Provider follows every site '
                         'rule and policy notified to it in writing before the visit.<br/><br/>'),
    'fee-line': ('All example fees exclude VAT', True, '5.1. Example design service - Fee: on request.<br/>'
                 '5.2. Example installation - Fee: on request.<br/>All example fees exclude VAT.<br/><br/>'),
    'unrecognised-line': ('Signed for the Parties by', True,
                          'Signed for the Parties by their authorised representatives:<br/><br/>'),
    'fallback-text': ('IN WITNESS WHEREOF', True,
                      '<b>IN WITNESS WHEREOF</b>, the Parties <i>have signed below.<br/><br/>'),
}


@pytest.mark.parametrize('shape', sorted(SHAPES))
def test_template_closing_shapes_keep_their_line_with_the_signatures(shape, monkeypatch):
    marker, zones_first, closing = SHAPES[shape]
    names = [PRIMARY] + [w['name'] for w in _witnesses(2)]
    section_pages = set()
    for step in range(0, 57, 3):
        def build():
            body = '<b>1. Example term</b><br/>The Parties agree to this example wording.<br/><br/>'
            if zones_first:
                content = (body + '{{zones_table}}<br/><br/>' + _lines(step) + '<br/>' + closing
                           + '{{signature_blocks}}<br/><br/><b>Annex 1</b><br/>Example annex wording.')
            else:
                content = (body + _lines(step) + '<br/>' + closing + '{{signature_blocks}}<br/><br/>'
                           '<b>Attachment A</b><br/>{{zones_table}}')
            return _contract(f'{shape}-{step}', signers=3, template=_template(content))
        contract = build()
        pages = _pages(contract)
        _assert_no_blank_page(pages, contract)
        opening = _found(pages, marker)
        rows = {_found(pages, name)[0] for name in names} | set(_found(pages, SUPPLIER))
        assert len(opening) == 1 and len(rows) == 1 and opening[0] in rows, (step, opening, rows)
        section_pages |= rows
        old = _old_flow_pages(build, monkeypatch)
        assert len(pages) <= len(old) + 1, step
    assert len(section_pages) >= 2, section_pages


# --- Flow units -------------------------------------------------------------

def _body(text):
    return Paragraph(text, document_styles()['body'])


def _rows_table(total, count=3):
    """A signer-pair table of `count` rows measuring `total` points."""
    probe = contract_pdf_v2._signature_rows([[Spacer(1, 10)]], CONTENT_WIDTH, splittable=False)
    padding = contract_pdf_v2._stack_height([probe], CONTENT_WIDTH) - 10
    rows = [[Spacer(1, total / count - padding)] for _ in range(count)]
    table = contract_pdf_v2._signature_rows(rows, CONTENT_WIDTH, splittable=True)
    table._bmasia_signature_pairs = True
    assert contract_pdf_v2._stack_height([table], CONTENT_WIDTH) == pytest.approx(total, abs=0.01)
    return table


def _contacts_lead():
    return [_body('9. Contacts:'), _body('BMA: Example Coordinator, Example Title')]


def _kept(flow):
    return [item for item in flow if isinstance(item, KeepTogether)]


def test_section_just_under_the_page_limit_moves_as_one_unit():
    lead = _contacts_lead()
    height = contract_pdf_v2._stack_height(lead, CONTENT_WIDTH)
    table = _rows_table(contract_pdf_v2._PAGE_FRAME_HEIGHT - height - 10)
    flow = contract_pdf_v2._keep_execution_section(lead + [table], CONTENT_WIDTH)
    assert len(flow) == 1 and isinstance(flow[0], KeepTogether)
    assert flow[0]._content == lead + [table]


def test_table_that_fits_a_page_only_alone_stays_whole_without_its_opening_line():
    lead = _contacts_lead()
    table = _rows_table(contract_pdf_v2._PAGE_FRAME_HEIGHT - 10)
    flow = contract_pdf_v2._keep_execution_section(lead + [table], CONTENT_WIDTH)
    # The opening line flows before the page break, its heading kept with the
    # next line; the signer rows stay whole.
    assert flow[:2] == lead and lead[0].getKeepWithNext()
    assert len(flow) == 3 and isinstance(flow[2], KeepTogether) and flow[2]._content == [table]


def test_section_over_the_page_limit_keeps_its_opening_line_with_the_first_row():
    lead = _contacts_lead()
    table = _rows_table(contract_pdf_v2._PAGE_FRAME_HEIGHT + 20)
    flow = contract_pdf_v2._keep_execution_section(lead + [table], CONTENT_WIDTH)
    assert len(flow) == 2 and isinstance(flow[0], KeepTogether)
    assert flow[0]._content[:2] == lead
    assert len(flow[0]._content[2]._cellvalues) == 1
    assert isinstance(flow[1], Table) and len(flow[1]._cellvalues) == 2 and flow[1].splitByRow


def _signing_source(contract):
    return ContractViewSet()._build_signature_blocks_table(contract, ENTITY, ENTITY)


def _contacts_paragraph():
    return Paragraph('<b>9.</b> Contacts:<br/>BMA: Example Coordinator, Example Title<br/>'
                     'E: coordinator@example.com<br/><br/>Client: Jordan Example<br/>E: jordan@example.com',
                     document_styles()['body'])


def test_real_three_and_four_pair_sections_against_the_page_limit():
    styles = document_styles()
    three = _flowables([_contacts_paragraph(), Spacer(1, 20), KeepTogether([
        Spacer(1, 20), _signing_source(_contract('real-3', signers=3))])], CONTENT_WIDTH, styles)
    assert len(_kept(three)) == 1
    assert CONTACTS.search(_kept(three)[0]._content[0].getPlainText())
    assert len(_kept(three)[0]._content[-1]._cellvalues) == 3

    four = _flowables([_contacts_paragraph(), Spacer(1, 20), KeepTogether([
        Spacer(1, 20), _signing_source(_contract('real-4', signers=4))])], CONTENT_WIDTH, styles)
    kept = _kept(four)
    assert len(kept) == 1 and kept[0] is four[-2]
    section = kept[0]._content + [four[-1]]
    assert contract_pdf_v2._stack_height(section, CONTENT_WIDTH) > contract_pdf_v2._PAGE_FRAME_HEIGHT
    assert CONTACTS.search(kept[0]._content[0].getPlainText())
    assert len(kept[0]._content[-1]._cellvalues) == 1
    assert len(four[-1]._cellvalues) == 3 and four[-1].splitByRow


def test_three_pairs_without_an_opening_line_stay_whole():
    styles = document_styles()
    flow = _flowables([_body('Example closing clause.'), _signing_source(_contract('bare', signers=3))],
                      CONTENT_WIDTH, styles)
    kept = _kept(flow)
    assert len(kept) == 1 and len(kept[0]._content) == 1
    assert len(kept[0]._content[0]._cellvalues) == 3
    assert flow[0].getPlainText() == 'Example closing clause.'


def test_one_pair_closing_above_300_points_stays_on_the_one_pair_rule():
    styles = document_styles()
    wording = 'Example contact wording that runs on for a while. ' * 20
    source = _signing_source(_contract('one', signers=1))
    flow = _flowables([Paragraph('<b>9.</b> Contacts:<br/>' + wording, styles['body']), source],
                      CONTENT_WIDTH, styles)
    closing = flow[-3:]
    assert contract_pdf_v2._stack_height(closing[:2], CONTENT_WIDTH) <= contract_pdf_v2._EXECUTION_LEAD_MAX_HEIGHT
    assert contract_pdf_v2._stack_height(closing, CONTENT_WIDTH) >= 300
    assert not _kept(flow), 'over 300 pt the one-pair rule leaves the closing to flow'


@pytest.mark.parametrize('line', [
    'Signed for the Parties by their authorised representatives:',
    'เพื่อเป็นหลักฐาน คู่สัญญาได้ลงนามไว้เป็นสำคัญ',
    markup_as_text('<b>IN WITNESS WHEREOF</b>, the Parties <i>have signed below.'),
])
def test_line_a_template_places_before_its_signatures_travels_whatever_it_says(line):
    styles = document_styles()
    flow = _flowables([
        Paragraph('Filler line 1.<br/>Filler line 2.', styles['body']),
        KeepTogether([Paragraph('Filler line 3.<br/>' + line, styles['body']),
                      _signing_source(_contract('script', signers=3))]),
    ], CONTENT_WIDTH, styles)
    kept = _kept(flow)
    assert len(kept) == 1
    assert [item.getPlainText() for item in kept[0]._content[:-1]] == [
        Paragraph(line, styles['body']).getPlainText()]
    assert getattr(kept[0]._content[-1], '_bmasia_signature_pairs', False)


def test_long_wording_after_an_in_witness_line_does_not_travel():
    styles = document_styles()
    long_paragraph = 'Example closing wording that continues at length. ' * 9
    flow = _flowables([
        Paragraph('In witness whereof the Parties sign below.<br/>' + '<br/>'.join([long_paragraph] * 4),
                  styles['body']),
        _signing_source(_contract('long-lead', signers=2)),
    ], CONTENT_WIDTH, styles)
    kept = _kept(flow)
    assert len(kept) == 1
    lead = kept[0]._content[:-1]
    assert contract_pdf_v2._stack_height(lead, CONTENT_WIDTH) <= contract_pdf_v2._EXECUTION_LEAD_MAX_HEIGHT
    assert all(not item.getPlainText().startswith('In witness') for item in lead)


def test_contacts_clause_is_found_behind_a_status_line_and_an_extra_contact_line():
    styles = document_styles()
    flow = _flowables([
        Paragraph('<b>9.</b> Contacts:<br/>BMA: Example Coordinator<br/>E: coordinator@example.com<br/>'
                  'T: +00 0000 0000<br/><br/>Client: Jordan Example<br/>E: jordan@example.com',
                  styles['body']),
        Spacer(1, 20),
        Paragraph('<b>ACTIVE CONTRACT</b>', styles['body']),
        Spacer(1, 14),
        KeepTogether([Spacer(1, 20), _signing_source(_contract('status', signers=3))]),
    ], CONTENT_WIDTH, styles)
    kept = _kept(flow)
    assert len(kept) == 1
    assert len(kept[0]._content) > 8
    assert CONTACTS.search(kept[0]._content[0].getPlainText())


def test_in_witness_line_and_three_signer_pairs_form_one_kept_group():
    styles = document_styles()
    flow = _flowables([
        _body('Example closing clause.'),
        Spacer(1, 20),
        _body(IN_WITNESS),
        Spacer(1, 20),
        _signing_source(_contract('unit', signers=3)),
    ], CONTENT_WIDTH, styles)
    kept = _kept(flow)
    assert len(kept) == 1
    content = kept[0]._content
    assert content[0].getPlainText() == IN_WITNESS
    assert getattr(content[-1], '_bmasia_signature_pairs', False)
    assert len(content[-1]._cellvalues) == 3
    assert flow[0].getPlainText() == 'Example closing clause.'
