"""Opt-in MCP correction updates must compare current CRM state atomically."""
import json

import pytest

from crm_app.mcp import update_record
from crm_app.models import Company, Contact
from crm_app.serializers import ContactSerializer


def _contact():
    company = Company.objects.create(
        name='Optimistic lock fixture', billing_entity='BMAsia Limited',
    )
    return Contact.objects.create(
        company=company,
        name='Correction contact',
        email='correction@example.test',
        title='Director',
        department='',
    )


def _observed(contact):
    record = ContactSerializer(contact).data
    return record['updated_at'], record


@pytest.mark.django_db
def test_guarded_update_rejects_stale_version_without_saving():
    contact = _contact()
    version, record = _observed(contact)
    contact.title = 'Changed elsewhere'
    contact.save()

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        expected_version=version,
        expected_values=json.dumps({'title': record['title']}),
    ))

    contact.refresh_from_db()
    assert result == {
        'updated': False, 'id': str(contact.pk),
        'error': 'Stale expected_version; nothing was saved.',
    }
    assert contact.title == 'Changed elsewhere'


@pytest.mark.django_db
def test_guarded_update_rejects_before_value_mismatch_and_null_coercion():
    contact = _contact()
    version, _ = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'department': 'Operations'}),
        expected_version=version,
        # Blank string is distinct from null and must not be silently coerced.
        expected_values=json.dumps({'department': None}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Expected values no longer match; nothing was saved.'
    assert contact.department == ''


@pytest.mark.django_db
def test_guarded_update_rejects_unknown_or_company_binding_fields_without_saving():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'company': str(contact.company_id)}),
        expected_version=version,
        expected_values=json.dumps({'company': str(contact.company_id)}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert result['error'] == 'Guarded patch contains fields outside the approved correction scope.'
    assert contact.company_id == record['company']


@pytest.mark.django_db
def test_guarded_update_saves_then_returns_readback():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        expected_version=version,
        expected_values=json.dumps({'title': record['title']}),
    ))

    contact.refresh_from_db()
    assert result == {
        'updated': True, 'id': str(contact.pk),
        'applied': {'title': 'General Manager'},
    }
    assert contact.title == 'General Manager'


@pytest.mark.django_db
def test_guarded_version_accepts_equivalent_query_timestamp_format():
    contact = _contact()
    version, record = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
        # query_data_collections renders Django datetimes with an explicit UTC
        # offset, while DRF's serializer commonly returns a trailing Z.
        expected_version=version.replace('Z', '+00:00'),
        expected_values=json.dumps({'title': record['title']}),
    ))

    assert result['updated'] is True


@pytest.mark.django_db
@pytest.mark.parametrize('data, expected_values', [
    ('{"title":"Director","title":"Other"}', '{"title":"Director"}'),
    ('{"title":NaN}', '{"title":"Director"}'),
    ('{"title":"Other"}', '{"title":"Director","title":"Other"}'),
])
def test_guarded_json_rejects_duplicate_keys_and_nonfinite_values(data, expected_values):
    contact = _contact()
    version, _ = _observed(contact)

    result = json.loads(update_record(
        'contact', str(contact.pk), data,
        expected_version=version, expected_values=expected_values,
    ))

    contact.refresh_from_db()
    assert result['updated'] is False
    assert contact.title == 'Director'


@pytest.mark.django_db
def test_legacy_three_argument_update_remains_available():
    contact = _contact()

    result = json.loads(update_record(
        'contact', str(contact.pk), json.dumps({'title': 'General Manager'}),
    ))

    contact.refresh_from_db()
    assert result['updated'] is True
    assert result['applied'] == {'title': 'General Manager'}
    assert contact.title == 'General Manager'
