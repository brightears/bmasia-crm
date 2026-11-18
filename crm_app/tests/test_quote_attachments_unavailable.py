"""Quote attachments are refused until uploaded files have persistent storage.

Uploaded files are written to the web container's own disk (no MEDIA_ROOT or storage
backend is configured and the service has no persistent disk), so they would be lost on
the next deploy or restart. The endpoint says so instead of reporting success.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from crm_app.models import Company, Quote, QuoteAttachment, User


@pytest.fixture
def api():
    user = User.objects.create_user(
        username='quote-tester', email='quote-tester@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def quote():
    company = Company.objects.create(name='Riverside Test Spa', billing_entity='BMAsia Limited')
    return Quote.objects.create(
        quote_number='HK-QT-ATTACH-TEST', company=company, status='Draft',
        valid_from=date(2026, 11, 1), valid_until=date(2026, 12, 1),
        subtotal=Decimal('500.00'), total_value=Decimal('500.00'), currency='USD',
    )


def test_upload_is_refused_and_nothing_is_stored(api, quote, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    upload = SimpleUploadedFile('brief.pdf', b'%PDF-1.4 test', content_type='application/pdf')

    response = api.post(f'/api/v1/quotes/{quote.pk}/add_attachment/', {'file': upload}, format='multipart')

    assert response.status_code == 503
    assert response.data['code'] == 'attachments_unavailable'
    assert 'not available' in response.data['error']
    assert QuoteAttachment.objects.count() == 0
    assert list(tmp_path.iterdir()) == []


def test_the_path_the_old_form_used_does_not_exist(api, quote):
    assert api.post(f'/api/v1/quotes/{quote.pk}/attachments/', {}, format='multipart').status_code == 404
