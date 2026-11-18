"""Every action on the user API either reads, acts on the caller's own account, or needs staff and a
website sign-in by a person. A new action fails these tests until it is classified."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAdminUser
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from crm_app.permissions import PersonSignedInToWebsite
from crm_app.views import UserViewSet

KNOWN_ACTIONS = {
    'list', 'retrieve', 'create', 'update', 'partial_update', 'destroy',
    'me', 'change_password', 'update_smtp', 'test_smtp', 'upload_avatar', 'test_smtp_send', 'bulk_operations',
}


def registered_actions():
    from crm_app.urls import router
    for prefix, viewset, basename in router.registry:
        if viewset is UserViewSet:
            names = set()
            for route in router.get_routes(viewset):
                names.update(route.mapping.values())
            return names - {'list_route', 'detail_route'}
    raise AssertionError('UserViewSet is not registered')


def test_every_registered_action_is_known():
    actions = registered_actions()
    assert actions == KNOWN_ACTIONS, sorted(actions ^ KNOWN_ACTIONS)


@pytest.mark.parametrize('name', sorted(KNOWN_ACTIONS))
def test_every_action_is_open_only_if_it_reads_or_serves_the_callers_own_account(name):
    viewset = UserViewSet()
    viewset.action = name
    permissions = viewset.get_permissions()
    if name in UserViewSet.OPEN_READ_ACTIONS | UserViewSet.SELF_SERVICE_ACTIONS:
        assert name in {'list', 'retrieve', 'me', 'change_password', 'update_smtp', 'test_smtp', 'upload_avatar'}
        return
    assert any(isinstance(p, IsAdminUser) for p in permissions), name
    assert any(isinstance(p, PersonSignedInToWebsite) for p in permissions), name


def _user(username, staff=False):
    user = get_user_model().objects.create_user(username=username, email=f'{username}@example.test',
                                                password='pw-user-12345678', role='Admin' if staff else 'Sales')
    user.is_staff = staff
    user.save()
    return user


def _token(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.get_or_create(user=user)[0].key)
    return client


def _jwt(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return client


@pytest.mark.parametrize('staff', [False, True])
def test_bulk_user_changes_are_refused_with_a_token(staff):
    target = _user('bulk-target')
    caller = _user('bulk-caller', staff=staff)
    for body in ({'action': 'delete', 'ids': [str(target.pk)]},
                 {'action': 'update_status', 'ids': [str(target.pk)], 'data': {'status': 'x', 'is_staff': True}}):
        response = _token(caller).post('/api/v1/users/bulk_operations/', body, format='json')
        assert response.status_code == 403
    target.refresh_from_db()
    assert get_user_model().objects.filter(pk=target.pk).exists() and not target.is_staff


def test_bulk_user_changes_are_not_available_even_on_the_website():
    target = _user('bulk-target')
    response = _jwt(_user('site-admin', staff=True)).post(
        '/api/v1/users/bulk_operations/', {'action': 'delete', 'ids': [str(target.pk)]}, format='json')
    assert response.status_code == 405
    assert get_user_model().objects.filter(pk=target.pk).exists()


def test_sending_a_test_email_from_another_users_account_needs_the_website():
    target = _user('smtp-target')
    response = _token(_user('smtp-caller', staff=True)).post(f'/api/v1/users/{target.pk}/test_smtp_send/', {},
                                                             format='json')
    assert response.status_code == 403


def test_self_service_still_works_with_a_token():
    me = _user('self-service')
    client = _token(me)
    assert client.get('/api/v1/users/me/').status_code == 200
    assert client.patch('/api/v1/users/me/', {'first_name': 'Pat'}, format='json').status_code == 200
    assert client.post('/api/v1/users/change_password/', {'old_password': 'pw-user-12345678',
                                                          'new_password': 'pw-new-12345678'},
                       format='json').status_code == 200
    assert client.get('/api/v1/users/').status_code == 200


def test_audit_logs_cannot_be_changed_or_deleted_through_the_api():
    from crm_app.models import AuditLog
    row = AuditLog.objects.create(action='UPDATE', model_name='Company', record_id='x')
    client = _jwt(_user('site-admin', staff=True))
    assert client.delete(f'/api/v1/audit-logs/{row.pk}/').status_code == 405
    assert client.patch(f'/api/v1/audit-logs/{row.pk}/', {'action': 'DELETE'}, format='json').status_code == 405
    assert client.post('/api/v1/audit-logs/bulk_operations/', {'action': 'delete', 'ids': [str(row.pk)]},
                       format='json').status_code in (404, 405)
    assert AuditLog.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize('path', ['/api/v1/activities/', '/api/v1/change-proposals/'])
def test_activity_log_and_proposals_have_no_bulk_or_delete_route(path):
    client = _jwt(_user('site-admin', staff=True))
    assert client.post(f'{path}bulk_operations/', {'action': 'delete', 'ids': []}, format='json').status_code \
        in (404, 405)
    assert client.delete(f'{path}00000000-0000-0000-0000-000000000001/').status_code in (404, 405)
