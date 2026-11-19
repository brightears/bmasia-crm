"""Second review round on the encrypted SMTP password.

N1 a typed value that looks encrypted is refused at input; N2 with RENDER set and the built-in
key, unchanged plain values are written back as stored and new passwords are refused with a
400, never a 500; N3 a send that fell back to the shared address says so.

Keys are generated per test; every password is invented; nothing connects to a mail server.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.db.models import F, TextField
from django.db.models.functions import Cast
from django.http import HttpResponse
from django.test import override_settings
from rest_framework.test import APIClient

from crm_app.fields import KEY_NOT_CONFIGURED_MESSAGE, TOKEN_INPUT_MESSAGE
from crm_app.models import SMTP_FALLBACK_NOTICE, User

PLAIN = 'legacy-app-pass-fixture'
NEW = 'new-app-pass-fixture'


def _key():
    return Fernet.generate_key().decode()


def _raw(user):
    return User.objects.filter(pk=user.pk).annotate(
        raw=Cast(F('smtp_password'), output_field=TextField())
    ).values_list('raw', flat=True)[0]


def _write_raw(user, value):
    from crm_app.management.commands.encrypt_smtp_passwords import _write_raw
    _write_raw(User, user.pk, value)


def _user(name='sender', **extra):
    return User.objects.create_user(
        username=f'{name}-fixture', email=f'{name}-fixture@example.com', password='test-only-password',
        role='Sales', smtp_email=f'{name}-fixture@example.com', **extra,
    )


def _staff():
    return User.objects.create_user(username='staff-fixture', email='staff-fixture@example.com',
                                    password='test-only-password', role='Admin', is_staff=True,
                                    is_superuser=True)


def _admin_post(client, user, **extra):
    from crm_app.admin import UserAdminChangeForm
    form = UserAdminChangeForm(instance=user)
    data = {k: v for k, v in form.initial.items()
            if v is not None and k not in ('password', 'groups', 'user_permissions', 'date_joined', 'last_login')}
    data['date_joined_0'] = user.date_joined.strftime('%Y-%m-%d')
    data['date_joined_1'] = user.date_joined.strftime('%H:%M:%S')
    for key, value in list(data.items()):
        if isinstance(value, bool):
            if value:
                data[key] = 'on'
            else:
                data.pop(key)
    data.update(extra)
    return client.post(f'/admin/crm_app/user/{user.pk}/change/', data)


# --- N1 -------------------------------------------------------------------------------------

def _looks_encrypted():
    return Fernet(_key()).encrypt(b'x').decode()


def test_token_shaped_input_is_refused_everywhere(client):
    with override_settings(FIELD_ENCRYPTION_KEY=_key()):
        user = _user(smtp_password=PLAIN)
        typed = _looks_encrypted()

        own = APIClient()
        own.force_authenticate(user)
        r = own.post('/api/v1/users/update_smtp/', {'smtp_email': user.smtp_email, 'smtp_password': typed},
                     format='json')
        assert r.status_code == 400 and r.data == {'error': TOKEN_INPUT_MESSAGE}

        staff = _staff()
        api = APIClient()
        api.force_authenticate(staff)
        r = api.patch(f'/api/v1/users/{user.pk}/', {'smtp_password': typed}, format='json')
        assert r.status_code == 400 and r.data == {'smtp_password': [TOKEN_INPUT_MESSAGE]}

        client.force_login(staff)
        r = _admin_post(client, user, new_smtp_password=typed)
        assert r.status_code == 200 and TOKEN_INPUT_MESSAGE in r.content.decode()
        assert typed not in r.content.decode()

        assert User.objects.get(pk=user.pk).smtp_password == PLAIN

        # A normal password, and near misses, are accepted and encrypted.
        for value in (NEW, typed.rstrip('='), 'abcd efgh ijkl mnop'):
            r = own.post('/api/v1/users/update_smtp/', {'smtp_email': user.smtp_email, 'smtp_password': value},
                         format='json')
            assert r.status_code == 200, value
            assert User.objects.get(pk=user.pk).smtp_password == value


# --- N2 -------------------------------------------------------------------------------------

@pytest.fixture
def builtin_in_production(monkeypatch):
    from bmasia_crm import settings as project_settings
    monkeypatch.setenv('RENDER', 'true')
    with override_settings(FIELD_ENCRYPTION_KEY=project_settings._BUILTIN_FIELD_ENCRYPTION_KEY):
        yield


@pytest.fixture
def legacy_user():
    user = _user()
    _write_raw(user, PLAIN)
    return user


def test_profile_patch_of_another_field_keeps_the_legacy_value(builtin_in_production, legacy_user):
    own = APIClient()
    own.force_authenticate(User.objects.get(pk=legacy_user.pk))
    r = own.patch('/api/v1/users/me/', {'first_name': 'Changed'}, format='json')
    assert r.status_code == 200
    assert _raw(legacy_user) == PLAIN
    assert User.objects.get(pk=legacy_user.pk).first_name == 'Changed'


def test_admin_save_of_another_field_keeps_the_legacy_value(builtin_in_production, legacy_user, client):
    client.force_login(_staff())
    r = _admin_post(client, User.objects.get(pk=legacy_user.pk), first_name='Changed')
    assert r.status_code == 302, r.content.decode()[:500]
    assert _raw(legacy_user) == PLAIN


def test_update_smtp_with_a_new_value_is_refused_with_400(builtin_in_production, legacy_user):
    own = APIClient()
    own.force_authenticate(User.objects.get(pk=legacy_user.pk))
    r = own.post('/api/v1/users/update_smtp/', {'smtp_email': legacy_user.smtp_email, 'smtp_password': NEW},
                 format='json')
    assert r.status_code == 400 and r.data == {'error': KEY_NOT_CONFIGURED_MESSAGE}
    # Changing only the address still works and keeps the stored password.
    r = own.post('/api/v1/users/update_smtp/', {'smtp_email': 'other-fixture@example.com'}, format='json')
    assert r.status_code == 200
    assert _raw(legacy_user) == PLAIN

    staff = APIClient()
    staff.force_authenticate(_staff())
    r = staff.patch(f'/api/v1/users/{legacy_user.pk}/', {'smtp_password': NEW}, format='json')
    assert r.status_code == 400 and r.data == {'smtp_password': [KEY_NOT_CONFIGURED_MESSAGE]}


def test_admin_new_password_is_a_form_error_not_a_500(builtin_in_production, legacy_user, client):
    client.force_login(_staff())
    r = _admin_post(client, User.objects.get(pk=legacy_user.pk), new_smtp_password=NEW)
    assert r.status_code == 200 and KEY_NOT_CONFIGURED_MESSAGE in r.content.decode()
    assert _raw(legacy_user) == PLAIN


def test_sign_in_and_mail_with_the_legacy_value(builtin_in_production, legacy_user, client):
    r = client.post('/api/v1/auth/login/', {'username': legacy_user.username, 'password': 'test-only-password'},
                    content_type='application/json')
    assert r.status_code == 200
    assert _raw(legacy_user) == PLAIN
    fresh = User.objects.get(pk=legacy_user.pk)
    assert fresh.get_smtp_config()['password'] == PLAIN
    own = APIClient()
    own.force_authenticate(fresh)
    with mock.patch('smtplib.SMTP') as smtp:
        assert own.post('/api/v1/users/test_smtp/').status_code == 200
    assert smtp.return_value.login.call_args.args == (fresh.smtp_email, PLAIN)


def test_update_fields_save_without_the_password_does_not_touch_it(builtin_in_production, legacy_user):
    fresh = User.objects.get(pk=legacy_user.pk)
    fresh.smtp_password = NEW  # changed in memory but not saved
    fresh.first_name = 'Only this'
    fresh.save(update_fields=['first_name'])
    assert _raw(legacy_user) == PLAIN


def test_an_unchanged_encrypted_value_is_written_back_as_stored():
    key = _key()
    with override_settings(FIELD_ENCRYPTION_KEY=key):
        user = _user(smtp_password=PLAIN)
        stored = _raw(user)
        fresh = User.objects.get(pk=user.pk)
        fresh.first_name = 'Again'
        fresh.save()
        assert _raw(user) == stored


# --- N3 -------------------------------------------------------------------------------------

@pytest.fixture
def documents(monkeypatch, settings):
    from crm_app import views
    from crm_app.models import Company, Contact, Contract, Invoice, Quote
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    pdf = lambda self, request, pk=None: HttpResponse(b'%PDF-1.4 synthetic', content_type='application/pdf')
    for viewset, name in ((views.QuoteViewSet, 'pdf'), (views.ContractViewSet, 'pdf'),
                          (views.InvoiceViewSet, 'pdf'), (views.InvoiceViewSet, 'receipt_pdf')):
        monkeypatch.setattr(viewset, name, pdf)
    company = Company.objects.create(name='Notice Test Hotel')
    Contact.objects.create(company=company, name='Pat Example', email='pat@lagoon.test')
    quote = Quote.objects.create(company=company, quote_number='TH-QT97001',
                                 valid_from=date(2099, 1, 1), valid_until=date(2099, 2, 1))
    contract = Contract.objects.create(company=company, contract_number='TH-CT97001', start_date=date(2099, 1, 1),
                                       end_date=date(2099, 12, 31), value=Decimal('100.00'), status='Draft')
    invoice = Invoice.objects.create(company=company, contract=contract, invoice_number='INV-TH-2099-0971',
                                     issue_date=date(2099, 1, 1), due_date=date(2099, 2, 1), amount=Decimal('100'),
                                     total_amount=Decimal('100'), receipt_number='REC-TH-2099-0971',
                                     status='Paid', paid_date=date(2099, 1, 10))
    return {'quote': f'/api/v1/quotes/{quote.pk}/send/',
            'invoice': f'/api/v1/invoices/{invoice.pk}/send/',
            'receipt': f'/api/v1/invoices/{invoice.pk}/send-receipt/'}


@pytest.mark.parametrize('kind', ['quote', 'invoice', 'receipt'])
def test_send_reply_says_it_used_the_shared_address(kind, documents, mailoutbox):
    with override_settings(FIELD_ENCRYPTION_KEY=_key()):
        sender = User.objects.create_user(
            username='notice-fixture', email='notice@ourco.example', password='test-only-password', role='Admin',
            is_staff=True, is_superuser=True, smtp_email='notice@ourco.example')
        _write_raw(sender, Fernet(_key()).encrypt(PLAIN.encode()).decode())  # under another key
        api = APIClient()
        api.force_authenticate(User.objects.get(pk=sender.pk))
        r = api.post(documents[kind], {'recipients': ['pat@lagoon.test'], 'subject': 'S', 'body': 'B'},
                     format='json')
        assert r.status_code == 200, (kind, r.status_code, getattr(r, 'data', None))
        assert r.data['notice'] == SMTP_FALLBACK_NOTICE

        _write_raw(sender, None)  # no password at all: no notice, as on main
        api.force_authenticate(User.objects.get(pk=sender.pk))
        r = api.post(documents[kind], {'recipients': ['pat@lagoon.test'], 'subject': 'S', 'body': 'B'},
                     format='json')
        assert r.status_code == 200
        assert 'notice' not in r.data
