"""Login and token-obtain endpoints are rate limited without side effects.

The throttles keep their counters in a dedicated LocMem cache alias; the
default cache stays a DummyCache, so no other endpoint starts throttling.
"""
import secrets

import pytest
from django.conf import settings
from django.core.cache import caches
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from crm_app import login_throttle
from crm_app.tests.factories import UserFactory

TOKEN_OBTAIN_PATHS = ["/api-token-auth/", "/api/auth/token/"]
ALL_OBTAIN_PATHS = TOKEN_OBTAIN_PATHS + ["/api/v1/jwt/token/", "/api/v1/auth/login/"]


@pytest.fixture
def user_with_password():
    password = secrets.token_urlsafe(16)
    user = UserFactory()
    user.set_password(password)
    user.save()
    return user, password


@pytest.fixture
def low_limits(monkeypatch):
    monkeypatch.setattr(login_throttle.LoginUsernameRateThrottle, "rate", "3/hour")
    monkeypatch.setattr(login_throttle.LoginClientRateThrottle, "rate", "5/hour")


def test_global_cache_and_throttle_settings_are_unchanged():
    assert settings.CACHES["default"]["BACKEND"].endswith("DummyCache")
    assert settings.CACHES[login_throttle.LOGIN_THROTTLE_CACHE_ALIAS]["BACKEND"].endswith(
        "LocMemCache"
    )
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] == [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {
        "anon": "100/hour",
        "user": "1000/hour",
    }


def test_login_throttles_use_the_dedicated_cache():
    for throttle_cls in login_throttle.LOGIN_THROTTLE_CLASSES:
        assert throttle_cls().cache is caches[login_throttle.LOGIN_THROTTLE_CACHE_ALIAS]


@pytest.mark.parametrize("path", TOKEN_OBTAIN_PATHS)
def test_token_obtain_response_shape_is_unchanged(path, user_with_password):
    user, password = user_with_password

    response = APIClient().post(path, {"username": user.username, "password": password})

    assert response.status_code == 200
    assert response.json() == {"token": Token.objects.get(user=user).key}


@pytest.mark.parametrize("path", TOKEN_OBTAIN_PATHS)
def test_token_obtain_accepts_json(path, user_with_password):
    user, password = user_with_password

    response = APIClient().post(
        path, {"username": user.username, "password": password}, format="json"
    )

    assert response.status_code == 200
    assert set(response.json()) == {"token"}


@pytest.mark.parametrize("path", TOKEN_OBTAIN_PATHS)
def test_token_obtain_bad_password_is_still_400(path, user_with_password):
    user, _ = user_with_password

    response = APIClient().post(path, {"username": user.username, "password": "wrong"})

    assert response.status_code == 400
    assert "non_field_errors" in response.json()


@pytest.mark.parametrize("path", ALL_OBTAIN_PATHS)
def test_repeated_attempts_on_one_username_are_throttled(path, low_limits, user_with_password):
    user, _ = user_with_password
    client = APIClient()

    statuses = [
        client.post(path, {"username": user.username, "password": "wrong"}, format="json").status_code
        for _ in range(4)
    ]

    # Wrong password: 400 from the DRF token and login views, 401 from simplejwt.
    assert all(s in (400, 401) for s in statuses[:3])
    assert statuses[3] == 429


def test_throttled_response_has_retry_after(low_limits, user_with_password):
    user, _ = user_with_password
    client = APIClient()
    for _ in range(3):
        client.post("/api-token-auth/", {"username": user.username, "password": "wrong"})

    response = client.post("/api-token-auth/", {"username": user.username, "password": "wrong"})

    assert response.status_code == 429
    assert "Retry-After" in response


def test_username_limit_is_shared_across_obtain_routes(low_limits, user_with_password):
    user, password = user_with_password
    client = APIClient()
    body = {"username": user.username, "password": "wrong"}
    client.post("/api-token-auth/", body, format="json")
    client.post("/api/auth/token/", body, format="json")
    client.post("/api/v1/jwt/token/", body, format="json")

    response = client.post(
        "/api/v1/auth/login/", {"username": user.username, "password": password}, format="json"
    )

    assert response.status_code == 429


def test_client_limit_applies_across_usernames(low_limits):
    client = APIClient()
    statuses = [
        client.post(
            "/api-token-auth/", {"username": f"nobody{i}", "password": "wrong"}
        ).status_code
        for i in range(6)
    ]

    assert statuses[:5] == [400] * 5
    assert statuses[5] == 429


def test_other_users_are_not_affected_by_one_username_limit(low_limits, user_with_password):
    user, _ = user_with_password
    other_password = secrets.token_urlsafe(16)
    other = UserFactory()
    other.set_password(other_password)
    other.save()
    client = APIClient()
    for _ in range(3):
        client.post("/api-token-auth/", {"username": user.username, "password": "wrong"})

    response = client.post(
        "/api-token-auth/", {"username": other.username, "password": other_password}
    )

    assert response.status_code == 200


def test_unrelated_endpoints_are_not_throttled(low_limits, user_with_password):
    user, _ = user_with_password
    client = APIClient()
    client.force_authenticate(user)

    statuses = [client.get("/api/v1/auth/me/").status_code for _ in range(10)]
    refresh = [
        APIClient().post("/api/v1/auth/refresh/", {"refresh": "x"}, format="json").status_code
        for _ in range(10)
    ]

    assert set(statuses) == {200}
    assert 429 not in refresh
