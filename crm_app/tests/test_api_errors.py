"""API errors never carry internal exception text; validation and permission errors are unchanged."""
import logging
import smtplib
from unittest import mock

import pytest
from django.db.models import ProtectedError
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from crm_app.api_errors import api_exception_handler, internal_error_text, request_id_for
from crm_app.models import Company, User

SECRET = 'host=db.internal.example password=not-a-real-one'


@pytest.fixture
def user():
    return User.objects.create_user(
        username='errors-tester', email='errors-tester@example.com',
        password='test-only-password', role='Admin', is_active=True,
    )


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class _Body(serializers.Serializer):
    name = serializers.CharField(max_length=5)


class _Probe(APIView):
    """Raises whatever the test puts in `raise_this`."""
    raise_this = None

    def post(self, request):
        if self.raise_this is not None:
            raise self.raise_this
        _Body(data=request.data).is_valid(raise_exception=True)
        return None


def _call(user, exc=None, data=None, headers=None):
    request = APIRequestFactory().post('/probe/', data or {}, format='json', **(headers or {}))
    force_authenticate(request, user=user)
    return _Probe.as_view(raise_this=exc)(request)


# --- the exception handler -----------------------------------------------------------------

def test_unexpected_error_is_logged_and_answered_generically(user, caplog):
    with caplog.at_level(logging.ERROR, logger='crm_app.api_errors'):
        response = _call(user, RuntimeError(SECRET))

    assert response.status_code == 500
    body = response.data
    assert set(body) == {'error', 'request_id'}
    assert SECRET not in str(body) and 'RuntimeError' not in str(body) and 'Traceback' not in str(body)
    assert body['error'] == f"Something went wrong on the server. Reference: {body['request_id']}"
    assert response['X-Request-ID'] == body['request_id']
    record = caplog.records[-1]
    assert body['request_id'] in record.getMessage()
    assert record.exc_info and record.exc_info[1].args == (SECRET,)


def test_a_sensible_incoming_request_id_is_reused(user):
    response = _call(user, RuntimeError('x'), headers={'HTTP_X_REQUEST_ID': 'edge-1234abcd'})
    assert response.data['request_id'] == 'edge-1234abcd'


def test_an_odd_incoming_request_id_is_replaced(user):
    response = _call(user, RuntimeError('x'), headers={'HTTP_X_REQUEST_ID': 'bad id <script>'})
    assert response.data['request_id'] != 'bad id <script>'
    assert len(response.data['request_id']) == 16


def test_validation_errors_are_unchanged(user):
    response = _call(user, data={'name': 'far too long'})
    assert response.status_code == 400
    assert response.data == {'name': ['Ensure this field has no more than 5 characters.']}


@pytest.mark.parametrize('exc, code', [
    (PermissionDenied('Admin only'), 403),
    (NotFound('No such invoice'), 404),
])
def test_permission_and_not_found_errors_are_unchanged(user, exc, code):
    response = _call(user, exc)
    assert response.status_code == code
    assert response.data == {'detail': exc.detail}


def test_a_protected_delete_is_a_conflict_naming_what_is_in_the_way():
    company = Company.objects.create(name='Protected Test Co', billing_entity='BMAsia Limited')
    exc = ProtectedError('internal text', {company})
    response = api_exception_handler(exc, {'request': None})
    assert response.status_code == 409
    assert response.data['code'] == 'protected'
    assert 'companies' in response.data['error']
    assert 'internal text' not in response.data['error']


def test_internal_error_text_keeps_one_id_per_request(user):
    request = APIRequestFactory().get('/x/')
    first = internal_error_text(request, ValueError(SECRET), 'Failed to send')
    assert first == f'Failed to send. Reference: {request_id_for(request)}'
    assert SECRET not in first
    assert request_id_for(request) == request_id_for(request)


# --- endpoints that used to return str(e) --------------------------------------------------

def test_company_list_failure_is_generic(api):
    with mock.patch('crm_app.views.CompanyViewSet.filter_queryset', side_effect=RuntimeError(SECRET)):
        response = api.get('/api/v1/companies/')
    assert response.status_code == 500
    assert SECRET not in response.content.decode()
    assert 'request_id' in response.data


def test_company_list_invalid_page_is_a_404_again(api):
    response = api.get('/api/v1/companies/?page=999')
    assert response.status_code == 404


def test_finance_report_failure_is_generic(api):
    with mock.patch('crm_app.services.profit_loss_service.ProfitLossService.get_monthly_profit_loss',
                    side_effect=RuntimeError(SECRET)):
        response = api.get('/api/v1/profit-loss/monthly/?year=2026&month=10')
    assert response.status_code == 500
    assert SECRET not in response.content.decode()
    assert response.data['error'].startswith('Something went wrong on the server. Reference: ')


def test_finance_report_validation_message_is_kept(api):
    response = api.get('/api/v1/profit-loss/monthly/?year=2026&month=13')
    assert response.status_code == 400
    assert response.data == {'error': 'month must be between 1 and 12'}


def test_smtp_check_says_which_step_failed_without_the_server_reply(api, user):
    user.smtp_email = 'sender@example.com'
    user.smtp_password = 'not-a-password'
    user.save()
    reply = (535, b'5.7.8 internal server detail')
    with mock.patch('smtplib.SMTP') as smtp:
        smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(*reply)
        response = api.post('/api/v1/users/test_smtp/')
    assert response.status_code == 400
    assert response.data['success'] is False
    assert response.data['error'].startswith('The mail server did not accept this email address and app password.')
    assert 'internal server detail' not in response.data['error']


def test_sequence_enrol_keeps_its_own_validation_message(api):
    with mock.patch('crm_app.services.email_service.EmailService.enroll_contact_in_sequence',
                    side_effect=ValueError('Contact has unsubscribed from emails')):
        response = api.post('/api/v1/sequence-enrollments/enroll/',
                            {'sequence_id': 'seq', 'contact_id': 'c'}, format='json')
    assert response.status_code == 400
    assert response.data == {'error': 'Contact has unsubscribed from emails'}


# --- /healthz/ -----------------------------------------------------------------------------

def test_healthz_is_public_and_touches_no_database(client, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = client.get('/healthz/')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert 'no-cache' in response['Cache-Control'] or 'max-age=0' in response['Cache-Control']


def test_healthz_only_answers_reads(client):
    assert client.post('/healthz/').status_code == 405
    assert client.head('/healthz/').status_code == 200
