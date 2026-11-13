"""Pytest config for the CRM test suite.

Fix 2026-08-22: the previous `django_db_setup` no-op disabled test-database
creation entirely, so the suite could only run against a pre-existing database.
Combined with `--no-migrations` in pytest.ini (build the schema directly from the
current models), the suite now builds a correct throwaway test DB from zero on
any Postgres, independent of the legacy migration history.
"""
import pytest


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Keep test-created contract templates clear of the reserved Hilton template IDs.

    `crm_app.views` recognises the maintained Hilton agreement by fixed primary
    keys. PostgreSQL sequences are not rolled back between tests, so without
    this a template created by an unrelated test could receive one of those
    IDs, depending on test order, and be rendered under the Hilton rules.
    SQLite reuses rolled-back IDs and does not reach them.
    """
    from django.db import connection
    from crm_app.models import ContractTemplate
    from crm_app.views import HILTON_FULL_TEMPLATE_IDS

    if connection.vendor == "postgresql":
        table = ContractTemplate._meta.db_table
        reserved_max = max(int(pk) for pk in HILTON_FULL_TEMPLATE_IDS)
        with django_db_blocker.unblock(), connection.cursor() as cursor:
            cursor.execute(
                f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                f"GREATEST(%s, (SELECT COALESCE(MAX(id), 0) FROM {connection.ops.quote_name(table)})))",
                [table, reserved_max],
            )
    yield


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
def clear_mcp_request_context():
    """MCP HTTP tests leave their request in a context variable; start each test without it."""
    from mcp_server.djangomcp import django_request_ctx
    token = django_request_ctx.set(None)
    yield
    django_request_ctx.reset(token)


@pytest.fixture(autouse=True)
def clear_login_throttle_cache():
    """Login rate-limit counters live in an in-process cache; start each test clean."""
    from django.core.cache import caches
    from crm_app.login_throttle import LOGIN_THROTTLE_CACHE_ALIAS
    caches[LOGIN_THROTTLE_CACHE_ALIAS].clear()
    yield
    caches[LOGIN_THROTTLE_CACHE_ALIAS].clear()
