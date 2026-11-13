"""GET /api/v1/auth/me/ must require a logged-in user.

The route is wired with as_view({'get': 'me'}), which does not apply the
per-action permission_classes given to @action, so AuthViewSet has to
enforce authentication for `me` itself.
"""
import secrets

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from crm_app.tests.factories import UserFactory

ME_URL = "/api/v1/auth/me/"


@pytest.fixture
def api_client():
    return APIClient()


def test_me_rejects_anonymous_request(api_client):
    response = api_client.get(ME_URL)

    assert response.status_code in (401, 403)


def test_me_rejects_invalid_bearer_token(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

    response = api_client.get(ME_URL)

    assert response.status_code == 401


def test_me_returns_current_user_for_jwt(api_client):
    user = UserFactory()
    access = RefreshToken.for_user(user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    response = api_client.get(ME_URL)

    assert response.status_code == 200
    assert response.data["username"] == user.username
    assert str(response.data["id"]) == str(user.pk)


def test_login_then_me_round_trip(api_client):
    password = secrets.token_urlsafe(16)
    user = UserFactory()
    user.set_password(password)
    user.save()

    login = api_client.post(
        "/api/v1/auth/login/",
        {"username": user.username, "password": password},
        format="json",
    )
    assert login.status_code == 200
    assert {"access", "refresh", "user"} <= set(login.data)

    fresh = APIClient()
    fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = fresh.get(ME_URL)

    assert response.status_code == 200
    assert response.data["username"] == user.username
