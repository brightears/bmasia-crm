"""
Pytest configuration and shared fixtures for Contract-Zone tests.
"""
import pytest
from django.conf import settings


# Configure Django settings for tests
def pytest_configure(config):
    """Configure Django settings for pytest"""
    settings.DEBUG = False


@pytest.fixture(scope='session')
def django_db_setup():
    """Setup test database"""
    pass


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
    pass
