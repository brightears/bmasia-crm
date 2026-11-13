"""Leftover setup and debug routes must stay unrouted.

These were reachable without a login. Database setup and one-off schema
repairs belong in management commands run from a shell, and configuration
checks belong behind authentication.
"""
import pytest
from django.urls import Resolver404, resolve


@pytest.mark.parametrize(
    "path",
    [
        "/debug-soundtrack/",
        "/api/initialize-database/",
        "/api/apply-migration-0025/",
    ],
)
def test_leftover_setup_routes_are_not_routed(path):
    with pytest.raises(Resolver404):
        resolve(path)


@pytest.mark.parametrize(
    "name",
    ["debug_soundtrack_api", "initialize_database", "apply_migration_0025_view"],
)
def test_leftover_setup_views_are_gone(name):
    from crm_app import views

    assert not hasattr(views, name)


def test_admin_reset_view_is_gone_from_crm_views():
    from crm_app import views

    assert not hasattr(views, "reset_admin")


def test_admin_reset_view_is_gone_from_root_urlconf():
    from bmasia_crm import urls

    assert not hasattr(urls, "reset_admin_view")
    assert not hasattr(urls, "create_admin_view")


@pytest.mark.parametrize(
    "module",
    ["crm_app.admin_setup", "crm_app.middleware", "crm_app.views 2"],
)
def test_admin_bootstrap_modules_are_gone(module):
    import importlib.util

    assert importlib.util.find_spec(module) is None


def test_development_auth_middleware_is_not_installed():
    from django.conf import settings

    assert not any("DevelopmentAuthMiddleware" in m for m in settings.MIDDLEWARE)
