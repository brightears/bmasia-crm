"""Pytest config for the CRM test suite.

Fix 2026-08-22: the previous `django_db_setup` no-op disabled test-database
creation entirely, so the suite could only run against a pre-existing database.
Combined with `--no-migrations` in pytest.ini (build the schema directly from the
current models), the suite now builds a correct throwaway test DB from zero on
any Postgres, independent of the legacy migration history.
"""
import pytest


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
