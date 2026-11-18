"""Shared fixtures for the agent_inbox tests. Synthetic data only.

Both write switches are on for every test here (they default to off in
settings); the tests that check the off state turn them off again.
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

ACTIVITIES = '/api/v1/activities/'
PROPOSALS = '/api/v1/change-proposals/'


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
def inbox_switches_on():
    with override_settings(AGENT_ACTIVITY_WRITES_ENABLED=True, CHANGE_PROPOSALS_ENABLED=True):
        yield


@pytest.fixture(autouse=True)
def clear_mcp_request_context():
    from mcp_server.djangomcp import django_request_ctx
    token = django_request_ctx.set(None)
    yield
    django_request_ctx.reset(token)


def make_user(username, role='Sales'):
    user, _ = get_user_model().objects.get_or_create(
        username=username, defaults={'email': f'{username}@example.test', 'role': role},
    )
    return user


@pytest.fixture
def person():
    return make_user('reviewer-person', role='Admin')


@pytest.fixture
def other_person():
    return make_user('second-person', role='Sales')


@pytest.fixture
def agent():
    # 'theo' is a principal in crm_app/agent_policy.py, so it is an agent account.
    return make_user('theo', role='Admin')


@pytest.fixture
def other_agent():
    return make_user('lyra', role='Admin')


def session_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def jwt_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return client


def token_client(user):
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
    return client


@pytest.fixture
def company():
    from crm_app.models import Company
    return Company.objects.create(
        name='Example Riverside Hotel', billing_entity='BMAsia Limited', country='Thailand',
        phone='+66 2 000 0000', email='front@riverside.example.com', website='https://riverside.example.com',
        address_line1='1 Example Road', city='Bangkok', notes='Existing company note',
    )


@pytest.fixture
def other_company():
    from crm_app.models import Company
    return Company.objects.create(name='Example Hilltop Resort', billing_entity='BMAsia Limited')


@pytest.fixture
def contact(company):
    from crm_app.models import Contact
    return Contact.objects.create(
        company=company, name='Pat Example', email='pat@riverside.example.com',
        phone='+66 81 000 0000', title='Manager', notes='Prefers email',
    )


@pytest.fixture
def contract(company):
    from datetime import date
    from decimal import Decimal
    from crm_app.models import Contract
    return Contract.objects.create(
        company=company, contract_number='TH-CT-INBOX-1', status='Active',
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        value=Decimal('1000.00'), total_value=Decimal('1000.00'), currency='THB',
    )


def iso_ago(**delta):
    return (timezone.now() - timedelta(**delta)).isoformat()


def activity_body(company, **overrides):
    body = {
        'idempotency_key': 'test:activity-0001',
        'company_id': str(company.pk),
        'kind': 'email',
        'direction': 'inbound',
        'occurred_at': iso_ago(hours=2),
        'summary': 'Customer asked about the new phone number',
        'body': 'Hello,\nour new reception number is +66 2 111 2222 from Monday.\nRegards, Pat',
        'participants': [{'name': 'Pat Example', 'address': 'pat@riverside.example.com', 'role': 'from'}],
        'source_system': 'gmail',
        'source_ref': 'msg-0001',
    }
    body.update(overrides)
    return body
