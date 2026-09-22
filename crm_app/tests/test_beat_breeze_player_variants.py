from datetime import date
from decimal import Decimal
from io import BytesIO
import os
from pathlib import Path

import pytest
from django.test import override_settings
from pypdf import PdfReader
from rest_framework.test import APIClient

from crm_app.models import Company, Contract, User
from crm_app.serializers import ContractSerializer


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def approved_contract_renderer():
    with override_settings(
        COMMERCIAL_DOCUMENT_V2_CONTRACT_LIVE=True,
        COMMERCIAL_DOCUMENT_V2_PREVIEW_ENABLED=True,
    ):
        yield


@pytest.fixture
def client():
    user = User.objects.create_user(
        username='beat-breeze-template-reviewer',
        email='reviewer@example.com',
        password='test-only-password',
        role='Admin',
        is_active=True,
    )
    api = APIClient()
    api.force_authenticate(user=user)
    return api


@pytest.fixture
def contract():
    company = Company.objects.create(
        name='Example Coastal Hotel',
        legal_entity_name='Example Coastal Hospitality Limited',
        city='Nha Trang',
        country='Vietnam',
        billing_entity='BMAsia Limited',
    )
    agreement = Contract.objects.create(
        company=company,
        contract_number='DRAFT-BB-PLAYER-VARIANTS',
        contract_type='Annual',
        service_type='beat_breeze_yearly',
        contract_category='standard',
        status='Draft',
        start_date=date(2026, 10, 1),
        end_date=date(2027, 9, 30),
        value=Decimal('260.00'),
        total_value=Decimal('260.00'),
        tax_rate=Decimal('0.00'),
        currency='USD',
        billing_frequency='Annually',
        property_name='Example Coastal Hotel',
        show_zone_pricing_detail=False,
    )
    agreement.service_locations.create(
        location_name='Lobby',
        platform='custom',
        custom_service_name='Beat Breeze',
    )
    return agreement


def _pdf_text(response, review_name=None):
    assert response.status_code == 200, getattr(response, 'data', None)
    if review_name and os.environ.get('BEAT_BREEZE_VARIANT_REVIEW_DIR'):
        review_dir = Path(os.environ['BEAT_BREEZE_VARIANT_REVIEW_DIR'])
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / f'{review_name}.pdf').write_bytes(response.content)
    reader = PdfReader(BytesIO(response.content))
    return ' '.join(' '.join(page.extract_text() or '' for page in reader.pages).split())


def _pdf_page_text(response):
    return [
        ' '.join((page.extract_text() or '').split())
        for page in PdfReader(BytesIO(response.content)).pages
    ]


def test_default_yearly_variant_excludes_player_boxes(contract, client):
    text = _pdf_text(
        client.get(f'/api/v1/contracts/{contract.pk}/pdf/'),
        'beat-breeze-excludes-player-boxes',
    )

    assert 'Player provided and managed by BMAsia' not in text
    assert 'Player box equipment' not in text
    assert 'Curation and content lease for the Beat Breeze package' in text


def test_charged_player_variant_renders_the_positive_price_line(contract, client):
    contract.service_type = 'beat_breeze_yearly_with_players'
    contract.value = Decimal('760.00')
    contract.total_value = Decimal('760.00')
    contract.save()
    contract.line_items.create(
        product_service='Beat Breeze annual service',
        quantity=Decimal('1.00'),
        unit_price=Decimal('260.00'),
        discount_percentage=Decimal('0.00'),
        tax_rate=Decimal('0.00'),
        line_total=Decimal('260.00'),
    )
    contract.line_items.create(
        product_service='Player Box',
        quantity=Decimal('1.00'),
        unit_price=Decimal('500.00'),
        discount_percentage=Decimal('0.00'),
        tax_rate=Decimal('0.00'),
        line_total=Decimal('500.00'),
    )

    response = client.get(f'/api/v1/contracts/{contract.pk}/pdf/')
    text = _pdf_text(
        response,
        'beat-breeze-includes-charged-player-boxes',
    )

    assert 'charged as itemized below' in text
    assert 'Player Box' in text
    assert 'USD 500.00' in text
    assert 'provided' not in text.casefold()
    pages = _pdf_page_text(response)
    assert len(pages) == 2
    assert 'Service Packages - Music Design & Management' in pages[0]
    assert 'Player Box @ USD 500.00' in pages[1]


@pytest.mark.parametrize('unit_price,discount', [
    ('0.00', '0.00'),
    ('500.00', '100.00'),
])
def test_charged_player_variant_rejects_free_player_lines(contract, unit_price, discount):
    serializer = ContractSerializer(
        contract,
        data={
            'service_type': 'beat_breeze_yearly_with_players',
            'line_items': [{
                'product_service': 'Player Box',
                'description': '',
                'quantity': '1.00',
                'unit_price': unit_price,
                'discount_percentage': discount,
                'tax_rate': '0.00',
            }],
        },
        partial=True,
    )

    assert not serializer.is_valid()
    assert 'positive quantity and unit price' in str(serializer.errors)


def test_charged_player_variant_pdf_fails_closed_without_priced_player(contract, client):
    Contract.objects.filter(pk=contract.pk).update(
        service_type='beat_breeze_yearly_with_players',
    )

    response = client.get(f'/api/v1/contracts/{contract.pk}/pdf/')

    assert response.status_code == 409
    assert response.data['code'] == 'PLAYER_BOX_VARIANT_INVALID'
    assert 'requires a Player Box line item' in response.data['error']


def test_exclude_variant_rejects_a_player_box_line(contract):
    serializer = ContractSerializer(
        contract,
        data={
            'line_items': [{
                'product_service': 'Player Box',
                'description': '',
                'quantity': '1.00',
                'unit_price': '500.00',
                'discount_percentage': '0.00',
                'tax_rate': '0.00',
            }],
        },
        partial=True,
    )

    assert not serializer.is_valid()
    assert 'excludes player boxes' in str(serializer.errors)


def test_charged_player_variant_rejects_provided_wording(contract):
    serializer = ContractSerializer(
        contract,
        data={
            'service_type': 'beat_breeze_yearly_with_players',
            'line_items': [{
                'product_service': 'Player Box provided by BMAsia',
                'description': '',
                'quantity': '1.00',
                'unit_price': '500.00',
                'discount_percentage': '0.00',
                'tax_rate': '0.00',
            }],
        },
        partial=True,
    )

    assert not serializer.is_valid()
    assert 'must never be described as provided' in str(serializer.errors)
