import pytest

from .builders import OUR_DOMAIN


@pytest.fixture
def capture_on(settings):
    """Master switch on, with the synthetic internal domain."""
    settings.GOOGLE_CAPTURE_ENABLED = True
    settings.CAPTURE_INTERNAL_DOMAINS = [OUR_DOMAIN]
    settings.CAPTURE_INTERNAL_ADDRESSES = []
    return settings


@pytest.fixture
def no_sleep():
    delays = []

    def sleep(seconds):
        delays.append(seconds)

    sleep.delays = delays
    return sleep
