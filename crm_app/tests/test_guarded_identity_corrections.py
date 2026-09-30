"""Cira's source-bound company/contact corrections keep unrelated CRM state fixed."""

from contextlib import contextmanager
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from mcp_server.djangomcp import django_request_ctx

from crm_app import mcp
from crm_app.mcp import update_record
from crm_app.models import AuditLog, Company, Contact
from crm_app.serializers import CompanySerializer, ContactSerializer


@contextmanager
def _as_caller(username):
    user, _ = get_user_model().objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'role': 'Admin'},
    )
    token = django_request_ctx.set(SimpleNamespace(user=user))
    try:
        yield user
    finally:
        django_request_ctx.reset(token)


def _context(collection, record, changes, **overrides):
    value = {
        'kind': f'explicit_source_{collection}_correction',
        'requested_by': 'nikki',
        'source_reference': 'spaces/test/messages/verified-instruction',
        'record_id': str(record.pk),
        'authorized_changes': changes,
    }
    if collection == 'contact':
        value['company_id'] = str(record.company_id)
    value.update(overrides)
    return json.dumps(value)


def _call(collection, record, changes, observed, context):
    return json.loads(update_record(
        collection, str(record.pk), json.dumps(changes),
        expected_version=observed['updated_at'],
        expected_values=json.dumps({key: observed[key] for key in changes}),
        authorization_context=context,
    ))


@pytest.mark.django_db
def test_company_legal_identity_and_address_correction_is_source_bound_and_audited():
    company = Company.objects.create(
        name='Sample Beeing', legal_entity_name='Old legal name',
        country='Thailand', billing_entity='BMAsia Limited',
        seasonal_emails_enabled=True,
    )
    observed = CompanySerializer(company).data
    changes = {
        'name': 'Sample Being',
        'legal_entity_name': 'SAMPLE BEING PVT LTD',
        'address_line1': 'Fourth Floor',
        'city': 'Male',
        'postal_code': '20066',
        'country': 'Maldives',
        'tax_id': 'TIN-TEST-123',
        'phone': '+960 700 0000',
    }
    with _as_caller('cira'):
        result = _call('company', company, changes, observed, _context('company', company, changes))

    assert result['updated'] is True, result
    assert result['post_version'] != observed['updated_at']
    company.refresh_from_db()
    for key, value in changes.items():
        assert getattr(company, key) == value
        assert result['applied'][key] == value
    assert company.billing_entity == 'BMAsia Limited'
    assert company.seasonal_emails_enabled is True
    audit = AuditLog.objects.get(pk=result['audit_log_id'])
    assert audit.model_name == 'Company'
    assert audit.changes['legal_entity_name'] == {
        'before': 'Old legal name', 'after': 'SAMPLE BEING PVT LTD',
    }
    assert audit.additional_data['source_reference'] == 'spaces/test/messages/verified-instruction'
    assert audit.additional_data['post_version'] == result['post_version']


@pytest.mark.django_db
def test_contact_identity_correction_accepts_formatted_phone_and_preserves_preferences():
    company = Company.objects.create(name='Contact correction fixture', billing_entity='BMAsia Limited')
    contact = Contact.objects.create(
        company=company, name='Original Contact', email='original@example.test',
        phone='+9607000000', title='Director',
    )
    original_preferences = contact.receives_renewal_emails
    observed = ContactSerializer(contact).data
    changes = {
        'name': 'Correct Contact',
        'email': 'corrected@example.test',
        'phone': '+960 700 0001',
    }
    with _as_caller('cira'):
        result = _call('contact', contact, changes, observed, _context('contact', contact, changes))

    assert result['updated'] is True, result
    contact.refresh_from_db()
    assert (contact.name, contact.email, contact.phone) == tuple(changes.values())
    assert contact.company_id == company.pk
    assert contact.title == 'Director'
    assert contact.receives_renewal_emails == original_preferences
    audit = AuditLog.objects.get(pk=result['audit_log_id'])
    assert audit.model_name == 'Contact'
    assert audit.changes['phone']['after'] == '+960 700 0001'


@pytest.mark.django_db
@pytest.mark.parametrize('change_context,caller,expected', [
    ({}, 'vera', 'authenticated Cira writer'),
    ({'record_id': str(uuid4())}, 'cira', 'different record'),
    ({'source_reference': ''}, 'cira', 'valid source reference'),
    ({'requested_by': 'unverified'}, 'cira', 'requester is invalid'),
    ({'authorized_changes': {'name': 'Different'}}, 'cira', 'does not exactly match'),
])
def test_company_correction_rejects_wrong_writer_or_source(change_context, caller, expected):
    company = Company.objects.create(name='Before', billing_entity='BMAsia Limited')
    observed = CompanySerializer(company).data
    changes = {'name': 'After'}
    context = json.loads(_context('company', company, changes))
    context.update(change_context)
    with _as_caller(caller):
        result = _call('company', company, changes, observed, json.dumps(context))
    assert result['updated'] is False
    assert expected in result['error']
    company.refresh_from_db()
    assert company.name == 'Before'
    assert not AuditLog.objects.filter(record_id=str(company.pk)).exists()


@pytest.mark.django_db
def test_company_correction_lane_rejects_stale_version_and_non_identity_fields():
    company = Company.objects.create(name='Before', billing_entity='BMAsia Limited')
    observed = CompanySerializer(company).data
    changes = {'name': 'After'}
    with _as_caller('cira'):
        forbidden = json.loads(update_record(
            'company', str(company.pk), json.dumps({'billing_entity': 'Another'}),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'billing_entity': observed['billing_entity']}),
            authorization_context=_context('company', company, {'billing_entity': 'Another'}),
        ))
        company.city = 'Changed elsewhere'
        company.save()
        stale = _call('company', company, changes, observed, _context('company', company, changes))
    assert forbidden['error'] == (
        'Company identity correction may change name, legal, tax, address, phone and email '
        'fields only; nothing was saved.'
    )
    assert stale['error'] == 'Stale expected_version; nothing was saved.'
    company.refresh_from_db()
    assert company.name == 'Before'
    assert company.billing_entity == 'BMAsia Limited'
    assert not AuditLog.objects.filter(record_id=str(company.pk)).exists()


@pytest.mark.django_db
def test_contact_correction_rejects_wrong_company_and_mixed_fields():
    company = Company.objects.create(name='Company A', billing_entity='BMAsia Limited')
    contact = Contact.objects.create(company=company, name='Before', email='before@example.test')
    observed = ContactSerializer(contact).data
    changes = {'name': 'After'}
    with _as_caller('cira'):
        wrong = _call(
            'contact', contact, changes, observed,
            _context('contact', contact, changes, company_id=str(uuid4())),
        )
        mixed = json.loads(update_record(
            'contact', str(contact.pk), json.dumps({'name': 'After', 'title': 'Manager'}),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'name': 'Before', 'title': observed['title']}),
            authorization_context=_context('contact', contact, {'name': 'After', 'title': 'Manager'}),
        ))
        preference = json.loads(update_record(
            'contact', str(contact.pk), json.dumps({'receives_renewal_emails': False}),
            expected_version=observed['updated_at'],
            expected_values=json.dumps({'receives_renewal_emails': observed['receives_renewal_emails']}),
            authorization_context=_context('contact', contact, {'receives_renewal_emails': False}),
        ))
    assert 'different company' in wrong['error']
    assert 'cannot include other fields' in mixed['error']
    assert 'cannot include other fields' in preference['error']
    contact.refresh_from_db()
    assert contact.name == 'Before'
    assert not AuditLog.objects.filter(record_id=str(contact.pk)).exists()


@pytest.mark.django_db
def test_company_correction_rolls_back_if_serializer_changes_protected_column(monkeypatch):
    company = Company.objects.create(name='Before', billing_entity='BMAsia Limited')
    observed = CompanySerializer(company).data
    changes = {'name': 'After'}
    class SideEffectSerializer(CompanySerializer):
        def update(self, instance, validated_data):
            instance = super().update(instance, validated_data)
            instance.billing_entity = 'Unexpected'
            instance.save()
            return instance
    original = mcp._get_serializer_class
    monkeypatch.setattr(
        mcp, '_get_serializer_class',
        lambda path: SideEffectSerializer if path.endswith('CompanySerializer') else original(path),
    )
    with _as_caller('cira'):
        result = _call('company', company, changes, observed, _context('company', company, changes))
    assert result['updated'] is False
    assert 'readback changed protected state' in result['error']
    company.refresh_from_db()
    assert company.name == 'Before'
    assert company.billing_entity == 'BMAsia Limited'
    assert not AuditLog.objects.filter(record_id=str(company.pk)).exists()
