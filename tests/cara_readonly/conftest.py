"""Hermetic Cara integration tests: real models, no production DB or signals.

Run with the dedicated pytest.ini and PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. This is
synthetic unit/integration verification, not a locally served CRM deployment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import django
import pytest
from django.apps import AppConfig, apps
from django.conf import settings
from django.db import connection


class CaraTestCRMConfig(AppConfig):
    name = "crm_app"

    def ready(self):
        pass  # No business signal registration or outbound side effects.


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if settings.configured:
    raise RuntimeError(
        "Cara synthetic tests require fresh, unconfigured Django settings"
    )
settings.configure(
    SECRET_KEY="synthetic-local-tests-only",
    INSTALLED_APPS=[
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "conftest.CaraTestCRMConfig",
    ],
    AUTH_USER_MODEL="crm_app.User",
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    USE_TZ=True,
    TIME_ZONE="UTC",
    ROOT_URLCONF="conftest",
    REST_FRAMEWORK={"UNAUTHENTICATED_USER": None},
)
django.setup()


@pytest.fixture(scope="session", autouse=True)
def local_database():
    with connection.schema_editor() as editor:
        for model in apps.get_models():
            editor.create_model(model)
    yield
    connection.close()


@pytest.fixture(autouse=True)
def clean_synthetic_database(local_database):
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys = OFF")
        for table in connection.introspection.table_names():
            cursor.execute('DELETE FROM "' + table + '"')
        cursor.execute("PRAGMA foreign_keys = ON")
