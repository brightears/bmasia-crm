"""PATCH /api/v1/users/me/: the username is read-only; a new password needs the current one."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

ME = '/api/v1/users/me/'


@pytest.fixture
def user():
    user = get_user_model().objects.create_user(
        username='profile-person', email='profile-person@example.test', password='current-pass-123', role='Sales',
    )
    return user


def client_for(user, token=False):
    client = APIClient()
    if token:
        key, _ = Token.objects.get_or_create(user=user)
        client.credentials(HTTP_AUTHORIZATION='Token ' + key.key)
    else:
        client.force_authenticate(user)
    return client


@pytest.mark.parametrize('token', [False, True])
def test_username_cannot_be_changed(user, token):
    response = client_for(user, token).patch(ME, {'username': 'someone-else'}, format='json')
    assert response.status_code == 400
    assert 'username' in response.json()
    user.refresh_from_db()
    assert user.username == 'profile-person'


def test_sending_the_same_username_is_harmless(user):
    response = client_for(user).patch(ME, {'username': 'profile-person', 'first_name': 'Pat'}, format='json')
    assert response.status_code == 200
    user.refresh_from_db()
    assert (user.username, user.first_name) == ('profile-person', 'Pat')


@pytest.mark.parametrize('token', [False, True])
def test_new_password_needs_the_current_one(user, token):
    client = client_for(user, token)
    missing = client.patch(ME, {'password': 'new-pass-4567890'}, format='json')
    wrong = client.patch(ME, {'password': 'new-pass-4567890', 'current_password': 'not-it'}, format='json')
    for response in (missing, wrong):
        assert response.status_code == 400
        assert 'current_password' in response.json()
    user.refresh_from_db()
    assert user.check_password('current-pass-123')


def test_password_changes_with_the_current_one(user):
    response = client_for(user).patch(
        ME, {'password': 'new-pass-4567890', 'current_password': 'current-pass-123'}, format='json')
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password('new-pass-4567890')


def test_other_profile_fields_still_update(user):
    response = client_for(user).patch(ME, {
        'first_name': 'Pat', 'last_name': 'Example', 'email': 'pat.example@example.test',
        'phone': '+66812345678', 'department': 'Sales',
    }, format='json')
    assert response.status_code == 200, response.content
    user.refresh_from_db()
    assert (user.first_name, user.last_name, user.email, user.department) == (
        'Pat', 'Example', 'pat.example@example.test', 'Sales')


def test_role_and_active_flag_are_still_ignored(user):
    response = client_for(user).patch(ME, {'role': 'Admin', 'is_active': False}, format='json')
    assert response.status_code == 200
    user.refresh_from_db()
    assert (user.role, user.is_active) == ('Sales', True)
