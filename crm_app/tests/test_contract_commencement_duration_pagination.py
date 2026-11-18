"""Clause 3 (Commencement Date) never sits alone at a page foot before clause 4.

18 Nov 2026: a one-zone Beat Breeze Draft with renewal wording placed under
clause 4 ("[under: duration]") printed "3. Commencement Date" alone at the
bottom of page 1 and "4. Duration" at the top of page 2. Sales asked for the
two clauses on one page. The fix changes page flow only. Fictional data; the
preamble length is swept so clause 3 crosses the foot of page 1.
"""
from datetime import date
from decimal import Decimal

import pytest
from reportlab.platypus import KeepTogether, Paragraph, Spacer

from crm_app.commercial_pdf import document_styles
from crm_app.contract_pdf_v2 import _flowables
from crm_app.models import Company, Contract, User
from crm_app.tests.test_contract_layout_regressions import _compact, _render

pytestmark = pytest.mark.django_db

RENEWAL_WORDING = (
    'Prior to the expiry of the service term, BMA shall provide the Client with a written '
    'renewal proposal no later than sixty (60) days prior to the expiry of the current '
    'contract term. Such proposal shall specify the service fees, terms and conditions, '
    'and other relevant provisions.\n\n'
    'The renewal of the Agreement shall be effective only upon the mutual written '
    'agreement of both Parties.'
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


def _contract(extra_lines):
    company = Company.objects.create(
        name=f'Example Pop {extra_lines}', legal_entity_name='Example Leisure Co., Ltd.',
        address_line1='1 Example Tower, 20th Floor, Example Road, Example Subdistrict, '
                      'Example District, Bangkok 10330',
        city='Bangkok', country='Thailand', billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number=f'DRAFT-CLAUSE-{extra_lines}',
        contract_type='Annual', contract_category='standard', status='Draft',
        is_active=False, start_date=date(2026, 8, 1), end_date=date(2027, 7, 31),
        value=Decimal('8000'), price_per_zone=Decimal('8000'), tax_rate=Decimal('7'),
        currency='THB', billing_frequency='Annual',
        customer_contact_name='Example Contact', customer_contact_email='contact@example.com',
        bmasia_contact_name='Example Coordinator', bmasia_contact_email='coordinator@example.com',
        bmasia_contact_title='Music Experience Assistant',
        preamble_custom=PREAMBLE + FILLER * extra_lines,
        custom_terms='[under: duration]\n' + RENEWAL_WORDING,
        custom_service_items=[{'name': 'Monthly refresh of music content', 'description': ''}],
    )
    contract.service_locations.create(
        location_name='Common Area 1st Floor', platform='custom',
        custom_service_name='Beat Breeze', price=None,
    )
    Contract.objects.filter(pk=contract.pk).update(
        tax_amount=Decimal('560'), total_value=Decimal('8560'),
    )
    contract.refresh_from_db()
    return contract


def _page_of(pages, phrase):
    found = [number for number, text in enumerate(pages) if phrase in text]
    assert len(found) == 1, (phrase, found)
    return found[0]


def test_commencement_and_duration_clauses_share_a_page_across_page_one_foot():
    User.objects.create_user(username='clause-flow-reviewer', role='Admin', is_active=True)
    pair_pages = set()
    for extra_lines in range(0, 20):
        reader = _render(_contract(extra_lines))
        pages = [_compact(page.extract_text() or '') for page in reader.pages]
        commencement = _page_of(pages, '3. Commencement Date: 01 August 2026')
        duration = _page_of(pages, '4. Duration: 1 year from 01 August 2026 to 31 July 2027')
        # The first paragraph placed under clause 4 travels with its line.
        under_duration = _page_of(pages, 'Prior to the expiry of the service term')
        assert commencement == duration == under_duration, (
            extra_lines, commencement, duration, under_duration)
        pair_pages.add(commencement)
        # Wording and order are untouched: clause 4's own wording follows it.
        text = ' '.join(pages)
        order = [text.index(phrase) for phrase in (
            '3. Commencement Date:', '4. Duration:', 'Prior to the expiry of the service term',
            'The renewal of the Agreement', '5. Service Packages',
        )]
        assert order == sorted(order)
    # The sweep must cross the page-one foot, or it proves nothing.
    assert pair_pages == {0, 1}


def _paragraphs(markup):
    styles = document_styles()
    return _flowables([Paragraph(markup, styles['body'])], 480, styles)


def test_short_commencement_keeps_its_wording_with_the_duration_joint():
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/>Service starts once installed.'
        '<br/><br/><b>4.</b> Duration: 1 year<br/>First renewal paragraph.<br/><br/>'
        'Second renewal paragraph.<br/><br/><b>5.</b> Service Packages'
    )
    kept = [item for item in flow if isinstance(item, KeepTogether)]
    assert len(kept) == 1
    assert [item.getPlainText() for item in kept[0]._content] == [
        '3. Commencement Date: 01 August 2026', 'Service starts once installed.',
        '4. Duration: 1 year', 'First renewal paragraph.',
    ]
    # Later duration wording flows on its own, in the same order.
    assert [item.getPlainText() for item in flow if isinstance(item, Paragraph)] == [
        'Second renewal paragraph.', '5. Service Packages',
    ]


def test_long_commencement_and_duration_keep_only_their_joint():
    long_line = 'The service schedule continues as agreed in writing by both Parties. ' * 8
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/>' + long_line + '<br/><br/>'
        + long_line + '<br/><br/><b>4.</b> Duration: 1 year<br/>' + long_line
        + '<br/><br/>' + long_line + '<br/><br/><b>5.</b> Service Packages'
    )
    kept = [item for item in flow if isinstance(item, KeepTogether)]
    assert len(kept) == 1
    joint = [item.getPlainText() for item in kept[0]._content]
    # Last commencement paragraph, the duration line and the first line under it.
    assert joint[0].startswith('The service schedule')
    assert joint[1] == '4. Duration: 1 year'
    assert joint[2].startswith('The service schedule')
    assert len(joint) == 3
    plain = [item.getPlainText() for item in flow if isinstance(item, Paragraph)]
    assert plain[0] == '3. Commencement Date: 01 August 2026'
    assert plain[-1] == '5. Service Packages'


def test_commencement_without_following_duration_is_left_to_flow():
    flow = _paragraphs(
        '<b>3.</b> Commencement Date: 01 August 2026<br/><br/><b>4.</b> Activation Date: on payment'
    )
    assert not [item for item in flow if isinstance(item, KeepTogether)]
    assert [item.getPlainText() for item in flow if not isinstance(item, Spacer)] == [
        '3. Commencement Date: 01 August 2026', '4. Activation Date: on payment',
    ]
