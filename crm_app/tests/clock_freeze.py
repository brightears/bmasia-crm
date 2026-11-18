"""Opt-in clock freeze for the whole test run (date-boundary checks).

Off unless both the plugin is loaded and ``CRM_TEST_FROZEN_AT`` is set to an
aware ISO timestamp. Every test (its fixtures included) then starts at that
instant, for example 00:30 in Bangkok, when the UTC date is still yesterday::

    CRM_TEST_FROZEN_AT=2027-01-01T00:30:00+07:00 \\
        python -m pytest -q -p crm_app.tests.clock_freeze

The clock ticks from the frozen instant so code that waits on time still runs.
``timezone.now()`` is the frozen UTC instant. Naive ``datetime.now()`` and
``date.today()`` return the UTC date and time here (freezegun ignores the process
time zone that Django sets in production), so a run at 00:30 Bangkok also catches
code or tests that lean on the process time zone instead of ``timezone.localdate()``.
"""
import datetime as dt
import os

import pytest

ENV = "CRM_TEST_FROZEN_AT"


def _frozen_at():
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    at = dt.datetime.fromisoformat(raw)
    if at.tzinfo is None:
        raise pytest.UsageError(f"{ENV} needs a UTC offset, e.g. 2027-01-01T00:30:00+07:00")
    return at


def pytest_report_header(config):
    at = _frozen_at()
    if at is not None:
        return f"clock frozen at the start of every test: {at.isoformat()} ({ENV})"


@pytest.fixture(autouse=True)
def _frozen_clock():
    at = _frozen_at()
    if at is None:
        yield
        return
    from freezegun import freeze_time

    with freeze_time(at, tick=True):
        yield
