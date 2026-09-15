"""A tailored one-zone agreement must not gain a page from duplicate gaps."""
from datetime import date
from decimal import Decimal
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from crm_app.models import Company, Contract, User
from crm_app.tests.test_contract_layout_regressions import (
    _image_boxes, _page_text, _render, _signature_lines, _snapshot,
)

pytestmark = pytest.mark.django_db


def test_tailored_thailand_contacts_and_blank_signatures_fit_second_page():
    User.objects.create_user(username='closing-reviewer', role='Admin', is_active=True)
    company = Company.objects.create(
        name='Example Asia Pacific (Bangkok)',
        legal_entity_name='EXAMPLE PROPERTY MANAGEMENT COMPANY LIMITED',
        address_line1='88 Example Office Building, 10th Fl.',
        address_line2='Example Road, Khlong Toei, Tax ID: 0000000000000',
        city='Bangkok', postal_code='10110', country='Thailand',
        tax_id='0000000000000', billing_entity='BMAsia (Thailand) Co., Ltd.',
    )
    contract = Contract.objects.create(
        company=company, contract_number='DRAFT-CLOSING-LAYOUT',
        contract_type='Annual', contract_category='standard', status='Draft',
        is_active=False, start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
        value=Decimal('11000'), price_per_zone=Decimal('11000'), tax_rate=Decimal('7'),
        currency='THB', billing_frequency='Annual',
        customer_contact_name='Alexandra Example',
        customer_contact_email='alexandra.example@example.com',
        customer_contact_title='Workplace Ambassador, Example Office Thailand, Corporate Real Estate',
        bmasia_contact_name='Example Coordinator',
        bmasia_contact_email='coordinator@example.com',
        bmasia_contact_title='Music Experience Assistant',
        custom_terms=(
            'This agreement covers Soundtrack Your Brand background music service for one zone '
            'at Lobby/Public Areas from 1 October 2026 to 30 September 2027. Invoices and '
            'payments under this agreement are to be routed through Example Office Supplies '
            'Co., Ltd., attention Ms. Alexandra Example, 80/41 Example Residential Estate 2, '
            'Example District Road, Saphan Soong, Bangkok 10250, Tax ID 0000000000000.'
        ),
    )
    contract.service_locations.create(
        location_name='Lobby/Public Areas', platform='soundtrack', price=Decimal('11000'),
    )
    Contract.objects.filter(pk=contract.pk).update(
        tax_amount=Decimal('770'), total_value=Decimal('11770'),
    )
    contract.refresh_from_db()
    before = _snapshot(contract)
    with CaptureQueriesContext(connection) as queries:
        reader = _render(contract)
    assert len(reader.pages) == 2
    last = _page_text(reader.pages[1])
    for phrase in ('9. Contacts:', 'Client: ' + contract.customer_contact_name,
                   contract.customer_contact_email, contract.bmasia_contact_email,
                   'Chris Andrews', 'Authorized Representative', '11,770.00',
                   contract.custom_terms):
        assert last.count(phrase) == 1
    rules = _signature_lines(reader.pages[1])
    assert len(rules) == 2
    assert rules[0]['y'] == pytest.approx(rules[1]['y'], abs=1)
    assert not [box for box in _image_boxes(reader.pages[1]) if box[1] < rules[0]['y'] + 100]
    assert not [q for q in queries if re.match(r'^\s*(INSERT|UPDATE|DELETE)\b', q['sql'], re.I)]
    assert _snapshot(contract) == before
