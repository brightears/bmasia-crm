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
