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
