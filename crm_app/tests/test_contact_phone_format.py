"""Contact phone formatting must agree with the human-facing forms."""
import pytest

from crm_app.models import Company, Contact
from crm_app.serializers import ContactSerializer


@pytest.mark.django_db
@pytest.mark.parametrize('phone', ['+960 730 8504', '+960 7308525', '+66 (81) 234-5678', '+9607308504', ''])
def test_contact_accepts_formatted_phone_without_changing_source(phone):
    company = Company.objects.create(name='Phone format fixture')
    serializer = ContactSerializer(data={
        'company': str(company.pk), 'name': 'Example Contact',
        'email': 'contact@example.test', 'phone': phone,
    })
    assert serializer.is_valid(), serializer.errors
    contact = serializer.save()
    contact.refresh_from_db()
    assert contact.phone == phone


@pytest.mark.django_db
@pytest.mark.parametrize('phone', ['abc7308504', '++9607308504', '+9607308', '+1234567890123456', '+9607308504 ext 2', '+960\n7308504'])
def test_contact_rejects_invalid_phone(phone):
    company = Company.objects.create(name='Invalid phone fixture')
    serializer = ContactSerializer(data={
        'company': str(company.pk), 'name': 'Example Contact',
        'email': 'contact@example.test', 'phone': phone,
    })
    assert not serializer.is_valid()
    assert 'phone' in serializer.errors
    assert not Contact.objects.filter(company=company).exists()


@pytest.mark.django_db
def test_partial_phone_update_preserves_other_contact_fields():
    company = Company.objects.create(name='Partial phone fixture')
    contact = Contact.objects.create(company=company, name='Original Contact', email='original@example.test')
    serializer = ContactSerializer(contact, data={'phone': '+960 7308525'}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    contact.refresh_from_db()
    assert contact.phone == '+960 7308525'
    assert contact.name == 'Original Contact'
    assert contact.email == 'original@example.test'
    assert contact.company_id == company.pk
