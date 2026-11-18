"""Clause 3 (Commencement Date) never sits alone at a page foot before clause 4.

18 Nov 2026: a one-zone Draft with renewal wording placed under clause 4
("[under: duration]") printed "3. Commencement Date" alone at the bottom of
page 1 and "4. Duration" at the top of page 2. The fix changes page flow only.
All names and wording here are made up; the preamble length is swept so the
clauses cross the foot of page 1.
"""
from datetime import date
from decimal import Decimal

import pytest
from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app import contract_pdf_v2
from crm_app.commercial_pdf import document_styles
from crm_app.contract_pdf_v2 import _flowables
from crm_app.models import Company, Contract, User
from crm_app.tests.test_contract_layout_regressions import _compact, _render

pytestmark = pytest.mark.django_db

UNDER_DURATION = (
    '[under: duration]\n'
    'Ahead of the end of the term, the Example Provider will send the Example Client '
    'a written offer to continue the service at least forty-five days in advance. The '
    'offer will list the fees, the music zones and any other changes proposed.\n\n'
    'A continuation takes effect only once both sides have agreed to it in writing.'
)
# One paragraph of roughly fifteen lines with no line break inside it.
TALL_UNDER_DURATION = '[under: duration]\n' + ' '.join(
    f'Sentence {n} of the example continuation wording is a plain filler line.'
    for n in range(1, 25)
)
NUMBERED_UNDER_COMMENCEMENT = (
    '[under: commencement]\n'
    '1. Example installation of the player at the venue.\n'
    '2. Example staff training on the music app.\n'
)
PREAMBLE = (
    'This agreement is made on 01 August 2026 between: BMAsia (Thailand) Co., Ltd. (BMA) '
    'and Example Leisure Co., Ltd., with registered address at 1 Example Tower, 20th Floor, '
    'Example Road, Example Subdistrict, Example District, Bangkok 10330, Thailand (Client). '
    '(Together "The Parties") Whereas BMA provides Beat Breeze, its own background-music '
    'service, together with music design and management services to hospitality and '
    'commercial clients. '
) + ' '.join(
    'BMA shall be responsible for obtaining and maintaining every licence, right or '
    'permission required to provide the music to the Client under this Agreement.'
    for _ in range(2)
)
# One extra line of preamble per step moves clause 3 down page 1 by one line.
FILLER = 'The Parties confirm that this clause is part of the agreed principal terms. '


@pytest.fixture
def reviewer():
    return User.objects.create_user(username='clause-flow-reviewer', role='Admin', is_active=True)


def _contract(extra_lines, custom_terms=UNDER_DURATION, tag='a'):
    company = Company.objects.create(
        name=f'Example Venue {tag} {extra_lines}', legal_entity_name='Example Leisure Co., Ltd.',
        address_line1='1 Example Tower, 20th Floor, Example Road, Example Subdistrict, '
                      'Example District, Bangkok 10330',
        city='Bangkok', country='Thailand', billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number=f'DRAFT-CLAUSE-{tag}-{extra_lines}',
        contract_type='Annual', contract_category='standard', status='Draft',
        is_active=False, start_date=date(2026, 8, 1), end_date=date(2027, 7, 31),
        value=Decimal('8000'), price_per_zone=Decimal('8000'), tax_rate=Decimal('7'),
        currency='THB', billing_frequency='Annual',
        customer_contact_name='Example Contact', customer_contact_email='contact@example.com',
        bmasia_contact_name='Example Coordinator', bmasia_contact_email='coordinator@example.com',
        bmasia_contact_title='Example Title',
        preamble_custom=PREAMBLE + FILLER * extra_lines,
        custom_terms=custom_terms,
        custom_service_items=[{'name': 'Example playlist service', 'description': ''}],
    )
    contract.service_locations.create(
        location_name='Example Lobby', platform='custom',
        custom_service_name='Beat Breeze', price=None,
    )
    Contract.objects.filter(pk=contract.pk).update(
        tax_amount=Decimal('560'), total_value=Decimal('8560'),
    )
    contract.refresh_from_db()
    return contract


def _pages(contract):
    return [_compact(page.extract_text() or '') for page in _render(contract).pages]


def _page_of(pages, phrase):
    found = [number for number, text in enumerate(pages) if phrase in text]
    assert len(found) == 1, (phrase, found)
    return found[0]


COMMENCEMENT = '3. Commencement Date: 01 August 2026'
DURATION = '4. Duration: 1 year from 01 August 2026 to 31 July 2027'


def test_commencement_and_duration_clauses_share_a_page_across_page_one_foot(reviewer):
    pair_pages = set()
    for extra_lines in range(0, 20):
        pages = _pages(_contract(extra_lines))
        commencement = _page_of(pages, COMMENCEMENT)
        duration = _page_of(pages, DURATION)
        # The first paragraph placed under clause 4 travels with its line.
        under_duration = _page_of(pages, 'Ahead of the end of the term')
        assert commencement == duration == under_duration, (
            extra_lines, commencement, duration, under_duration)
        pair_pages.add(commencement)
        # Wording and order are untouched: clause 4's own wording follows it.
        text = ' '.join(pages)
        order = [text.index(phrase) for phrase in (
            '3. Commencement Date:', '4. Duration:', 'Ahead of the end of the term',
            'A continuation takes effect', '5. Service Packages',
        )]
        assert order == sorted(order)
    # The sweep must cross the page-one foot, or it proves nothing.
    assert pair_pages == {0, 1}


def test_tall_first_duration_paragraph_never_adds_a_page(reviewer, monkeypatch):
    pair_pages = set()
    for extra_lines in range(0, 30, 2):
        with_fix = _pages(_contract(extra_lines, TALL_UNDER_DURATION, 'fix'))
        commencement = _page_of(with_fix, COMMENCEMENT)
        assert commencement == _page_of(with_fix, DURATION), extra_lines
        pair_pages.add(commencement)
        with monkeypatch.context() as patch:
            patch.setattr(contract_pdf_v2, '_keep_commencement_with_duration',
                          lambda items, width: items)
            without_fix = _pages(_contract(extra_lines, TALL_UNDER_DURATION, 'main'))
        assert len(with_fix) == len(without_fix), extra_lines
    assert pair_pages == {0, 1}


def test_numbered_wording_under_commencement_still_keeps_clause_four(reviewer):
    pair_pages = set()
    for extra_lines in range(0, 20):
        pages = _pages(_contract(extra_lines, NUMBERED_UNDER_COMMENCEMENT + UNDER_DURATION, 'num'))
        found = [_page_of(pages, phrase) for phrase in (
            COMMENCEMENT, '1. Example installation', '2. Example staff training',
            DURATION, 'Ahead of the end of the term',
        )]
        assert len(set(found)) == 1, (extra_lines, found)
        pair_pages.add(found[0])
    assert pair_pages == {0, 1}


def _paragraphs(markup):
    styles = document_styles()
    return _flowables([Paragraph(markup, styles['body'])], 480, styles)


def _kept(flow):
    return [[part.getPlainText() for part in item._content]
            for item in flow if isinstance(item, KeepTogether)]


def test_short_commencement_keeps_its_wording_with_the_duration_joint():
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/>Service starts once installed.'
        '<br/><br/><b>4.</b> Duration: 1 year<br/>First renewal paragraph.<br/><br/>'
        'Second renewal paragraph.<br/><br/><b>5.</b> Service Packages'
    )
    assert _kept(flow) == [[
        '3. Commencement Date: 01 August 2026', 'Service starts once installed.',
        '4. Duration: 1 year', 'First renewal paragraph.',
    ]]
    # Later duration wording flows on its own, in the same order.
    assert [item.getPlainText() for item in flow if isinstance(item, Paragraph)] == [
        'Second renewal paragraph.', '5. Service Packages',
    ]


def test_numbered_lines_in_the_commencement_paragraph_are_its_wording():
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/>1. Installation.<br/>2. Training.'
        '<br/><br/><b>4.</b> Duration: 1 year<br/>First renewal paragraph.'
    )
    assert _kept(flow) == [[
        '3. Commencement Date: 01 August 2026', '1. Installation.', '2. Training.',
        '4. Duration: 1 year', 'First renewal paragraph.',
    ]]


def test_tall_first_duration_paragraph_stays_out_of_the_joint():
    tall = 'The continuation wording runs on as one plain paragraph. ' * 30
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/><br/><b>4.</b> Duration: 1 year<br/>'
        + tall + '<br/><br/><b>5.</b> Service Packages'
    )
    assert _kept(flow) == [['3. Commencement Date: 01 August 2026', '4. Duration: 1 year']]


def test_long_commencement_wording_keeps_its_line_and_its_end_with_duration():
    long_line = 'The service schedule continues as agreed in writing by both Parties. ' * 8
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/>' + long_line + '<br/><br/>'
        + long_line + '<br/><br/><b>4.</b> Duration: 1 year<br/>' + long_line
        + '<br/><br/>' + long_line + '<br/><br/><b>5.</b> Service Packages'
    )
    kept = _kept(flow)
    assert len(kept) == 2
    # The clause line keeps its first paragraph; the last paragraph of the
    # clause joins the duration line.
    assert kept[0][0] == '3. Commencement Date: 01 August 2026'
    assert kept[0][1].startswith('The service schedule') and len(kept[0]) == 2
    assert kept[1][0].startswith('The service schedule')
    assert kept[1][1] == '4. Duration: 1 year'
    plain = [item.getPlainText() for item in flow if isinstance(item, Paragraph)]
    assert len(plain) == 2 and plain[-1] == '5. Service Packages'


def test_commencement_without_following_duration_is_left_to_flow():
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/><br/><b>4.</b> Activation Date: on payment'
    )
    assert not _kept(flow)
    assert [item.getPlainText() for item in flow if not isinstance(item, Spacer)] == [
        '3. Commencement Date: 01 August 2026', '4. Activation Date: on payment',
    ]
