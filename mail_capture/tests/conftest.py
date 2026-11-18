import pytest

from .builders import OUR_DOMAIN


@pytest.fixture(autouse=True)
def no_pacing(monkeypatch):
    """Real clients built in tests get no token buckets (tests that test
    pacing pass their own); nothing here sleeps for the quota."""
    monkeypatch.setattr('mail_capture.gmail_client.pacers_for', lambda email: ())
    try:
        import mail_capture.google_client as google_client
    except ImportError:
        return
    monkeypatch.setattr(google_client, 'pacers_for', lambda email: ())


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
