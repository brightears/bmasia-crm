"""The real client before the first supervised run: auth errors, per-item
batch errors, pacing hooks, library retries and the logging pin. Every
response comes from a local fake transport; nothing reaches Google."""
import json
import logging
import socket

import httplib2
import pytest

from mail_capture import credentials as creds
from mail_capture import google_client as gc
from mail_capture.gmail_client import (
    GmailAuthError, GmailRateLimited, GmailServerError, QuotaPacer,
)
from mail_capture.google_client import BATCH_SIZE, GoogleGmailClient
from mail_capture.models import CaptureMailbox, CaptureRun
from mail_capture.sync import BATCH_SIZE as ENGINE_BATCH_SIZE, sync_mailbox

from .builders import SALES, gmail_message, make_company, make_contact, make_mailbox, recent
from .test_google_client import BOUNDARY, FakeHttp, batch_response, error, ok, path_is


pytestmark = pytest.mark.django_db


@pytest.fixture
def key_file(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    path = tmp_path / 'synthetic-secret-keyfile.json'
    path.write_text(json.dumps({
        'type': 'service_account', 'project_id': 'synthetic-project', 'private_key_id': 'synthetic',
        'private_key': pem, 'client_email': 'capture@synthetic-project.iam.gserviceaccount.com',
        'client_id': '1', 'token_uri': 'https://oauth2.googleapis.com/token'}))
    return str(path), pem


@pytest.fixture
def on(capture_on, key_file):
    capture_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'key_file'
    capture_on.GOOGLE_CAPTURE_SCOPE = 'metadata'
    capture_on.GOOGLE_CAPTURE_NEVER_MAILBOXES = []
    capture_on.GOOGLE_CAPTURE_KEY_FILE = key_file[0]
    return capture_on


def authed(mailbox, routes):
    """The real credential for this mailbox and the real client, on a fake wire."""
    http = FakeHttp(routes)
    return GoogleGmailClient(mailbox.email, credentials=creds.delegated_credentials(mailbox), http=http), http


def token_ok():
    return (path_is('/token', 'POST'), ok({'access_token': 'ya29.SYNTHETIC-TOKEN', 'expires_in': 3600,
                                           'token_type': 'Bearer'}))


def raising(exc):
    def handler(*a):
        raise exc
    return handler


def token_requests(http):
    return sum(1 for m, p, q, b in http.requests if p.endswith('/token'))


@pytest.mark.parametrize('code', ['unauthorized_client', 'invalid_grant', 'access_denied', 'invalid_scope'])
def test_a_refused_token_is_an_auth_error_tried_once(on, key_file, code, caplog):
    caplog.set_level(logging.DEBUG)
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='100')
    client, http = authed(mb, [(path_is('/token', 'POST'), lambda *a: (
        400, {'error': code, 'error_description': 'synthetic description'}, {}))])
    result = sync_mailbox(mb.pk, lambda m: client, sleep=lambda s: None)
    assert result.outcome == 'auth_error' and result.reason.startswith(f'auth {code}: ')
    assert token_requests(http) == 1                    # no retries
    row = CaptureRun.objects.get()
    assert row.outcome == 'auth_error' and code in row.error_summary
    haystack = caplog.text + json.dumps(list(CaptureRun.objects.values()), default=str)
    assert 'synthetic-secret-keyfile' not in haystack and key_file[1].splitlines()[1] not in haystack
    assert 'assertion' not in row.error_summary


@pytest.mark.parametrize('exc', [httplib2.ServerNotFoundError('synthetic'), socket.timeout('synthetic'),
                                 ConnectionRefusedError('synthetic')])
def test_an_unreachable_token_endpoint_is_temporary_not_a_503(on, exc):
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='100')
    client, http = authed(mb, [(path_is('/token', 'POST'), raising(exc))])
    result = sync_mailbox(mb.pk, lambda m: client, sleep=lambda s: None)
    # Not a refusal: a temporary failure, ended at once, retried on a later run.
    assert result.outcome == 'unavailable' and 'token_endpoint_unreachable' in result.reason
    assert 'gmail 503' not in result.reason and token_requests(http) == 1
    mb.refresh_from_db()
    assert mb.auth_problem == '' and mb.transient_errors == 1 and mb.retry_not_before is not None


def test_a_refused_signblob_is_an_auth_error_naming_token_creator():
    from google.auth import exceptions
    error = gc._translate(exceptions.TransportError("Error calling the IAM signBlob API: b'{\"error\": 403}'"))
    assert isinstance(error, GmailAuthError) and error.code == 'signblob_refused'
    assert 'Token Creator' in error.hint and 'signBlob API: b' not in str(error)
    error = gc._token_error(exceptions.TransportError('exhausted signBlob endpoint retries'))
    assert error.code == 'signblob_refused'


def test_a_refresh_error_keeps_only_the_oauth_code():
    from google.auth import exceptions
    error = gc._translate(exceptions.RefreshError(
        'unauthorized_client: Client is unauthorized to retrieve access tokens', {'error': 'unauthorized_client'}))
    assert error.code == 'unauthorized_client' and 'retrieve' not in str(error)
    assert gc._translate(exceptions.RefreshError('something new')).code == 'token_refused'


@pytest.mark.parametrize('reason,code', [('insufficientPermissions', 'permission_denied'),
                                         ('accessNotConfigured', 'api_not_enabled')])
def test_a_permission_403_is_never_retried(on, reason, code):
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='100')
    client, http = authed(mb, [token_ok(), (path_is('/labels'), error(403, reason))])
    delays = []
    result = sync_mailbox(mb.pk, lambda m: client, sleep=delays.append)
    assert result.outcome == 'auth_error' and result.reason.startswith(f'auth {code}')
    assert sum(1 for m, p, q, b in http.requests if p.endswith('/labels')) == 1 and delays == []


def test_a_rate_limit_403_is_still_retried(on):
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='100')
    client, http = authed(mb, [token_ok(), (path_is('/labels'), error(403, 'userRateLimitExceeded'))])
    result = sync_mailbox(mb.pk, lambda m: client, sleep=lambda s: None)
    assert result.outcome == 'rate_limited'
    assert sum(1 for m, p, q, b in http.requests if p.endswith('/labels')) == 4


def test_the_library_does_not_retry_on_its_own():
    http = FakeHttp([(path_is('/labels'), error(500, 'backendError'))])
    client = GoogleGmailClient(SALES, http=http)
    with pytest.raises(GmailServerError):
        client.list_labels()
    assert len(http.requests) == 1


def test_batches_hold_fifty_calls_in_the_client_and_the_engine():
    assert BATCH_SIZE == 50 and ENGINE_BATCH_SIZE == 50
    ids = [f'g{i}' for i in range(120)]
    sizes = []

    def handle(method, path, query, body):
        import re
        found = re.findall(r'/messages/([^/?\s]+)\?', body)
        sizes.append(len(found))
        return 200, batch_response([(g, 200, {'id': g}) for g in found]), {
            'content-type': f'multipart/mixed; boundary={BOUNDARY}'}
    client = GoogleGmailClient(SALES, http=FakeHttp([(path_is('/batch', 'POST'), handle)]))
    assert len(client.get_messages(ids)) == 120 and sizes == [50, 50, 20]


def _retry_after_batch(statuses, retry_after):
    """A batch answer where some items carry their own status and Retry-After."""
    def handle(method, path, query, body):
        import re
        found = re.findall(r'/messages/([^/?\s]+)\?', body)
        chunks = []
        for gid in found:
            status = statuses.pop(gid, 200)
            payload = {'id': gid} if status == 200 else {'error': {'code': status, 'message': 'x',
                                                                   'errors': [{'reason': 'rateLimitExceeded'}]}}
            extra = f'Retry-After: {retry_after}\r\n' if status == 429 else ''
            chunks.append(
                f'--{BOUNDARY}\r\nContent-Type: application/http\r\nContent-ID: <response-x + {gid}>\r\n\r\n'
                f'HTTP/1.1 {status} X\r\nContent-Type: application/json\r\n{extra}\r\n{json.dumps(payload)}\r\n')
        return 200, ''.join(chunks) + f'--{BOUNDARY}--\r\n', {'content-type': f'multipart/mixed; boundary={BOUNDARY}'}
    return handle


def test_a_per_item_429_keeps_retry_after():
    client = GoogleGmailClient(SALES, http=FakeHttp([(path_is('/batch', 'POST'),
                                                     _retry_after_batch({'g2': 429}, 9))]))
    out = client.get_messages(['g1', 'g2'])
    assert out['g1'] == {'id': 'g1'} and isinstance(out['g2'], GmailRateLimited)
    assert out['g2'].retry_after == 9.0


def test_the_engine_retries_only_the_rate_limited_item_through_the_real_client(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id='100')
    messages = {f'm{i}': gmail_message(f'm{i}', 'Pat <pat@lagoon.test>', [SALES], date=recent(2),
                                       message_id=f'<m{i}@lagoon.test>') for i in range(5)}
    history = {'history': [{'id': '101', 'messagesAdded': [{'message': {'id': g}} for g in messages]}],
               'historyId': '101'}
    statuses = {'m3': 429}

    def handle(method, path, query, body):
        import re
        found = re.findall(r'/messages/([^/?\s]+)\?', body)
        parts = [(g, statuses.pop(g, 200), None) for g in found]
        parts = [(g, s, messages[g] if s == 200 else {'error': {'code': s, 'message': 'x'}}) for g, s, _ in parts]
        return 200, batch_response(parts), {'content-type': f'multipart/mixed; boundary={BOUNDARY}'}
    http = FakeHttp([(path_is('/labels'), ok({'labels': []})), (path_is('/history'), ok(history)),
                     (path_is('/batch', 'POST'), handle)])
    client = GoogleGmailClient(mb.email, http=http)
    result = sync_mailbox(mb.pk, lambda m: client, sleep=lambda s: None)
    posts = [b for m, p, q, b in http.requests if m == 'POST']
    assert result.outcome == 'ok' and result.counts['stored'] == 5 and len(posts) == 2
    assert posts[1].count('/messages/') == 1
    mb.refresh_from_db()
    assert mb.history_id == '101'


def test_the_client_paces_with_its_buckets():
    calls = []

    class Recording(QuotaPacer):
        def acquire(self, units, sleep):
            calls.append(units)
            return 0
    client = GoogleGmailClient(SALES, http=FakeHttp([]), pacers=[Recording(6000), Recording(1200000)])
    client.pace(1000, lambda s: None)
    assert calls == [1000, 1000]


def test_real_clients_share_one_bucket_per_mailbox(monkeypatch):
    from mail_capture import gmail_client
    monkeypatch.undo()                                  # the real pacers_for, not the test stub
    gmail_client.reset_pacers()
    try:
        a1, project1 = gmail_client.pacers_for(SALES)
        a2, project2 = gmail_client.pacers_for(SALES.upper())
        b, project3 = gmail_client.pacers_for('ops@ourco.example')
        assert a1 is a2 and a1 is not b and project1 is project2 is project3
        assert a1.per_minute == 6000 and project1.per_minute == 1200000
    finally:
        gmail_client.reset_pacers()


# --- the logging pin ------------------------------------------------------------------------

def test_google_debug_logging_stays_off_at_a_debug_root(caplog):
    from logging.config import dictConfig
    from django.conf import settings
    from google.auth import _helpers
    dictConfig(settings.LOGGING)
    root = logging.getLogger()
    old = root.level
    root.setLevel(logging.DEBUG)
    caplog.set_level(logging.DEBUG)
    try:
        for name in ('google', 'google.auth.transport.requests', 'google.auth.transport._http_client',
                     'google_auth_httplib2', 'googleapiclient.discovery', 'googleapiclient.http'):
            logger = logging.getLogger(name)
            if name.startswith(('google.', 'googleapiclient')) or name == 'google':
                assert not logger.isEnabledFor(logging.DEBUG), name
            logger.debug('synthetic debug record from %s', name)
        assert not _helpers.is_logging_enabled(logging.getLogger('google.auth.transport.requests'))
        assert not [r for r in caplog.records
                    if r.name.startswith(('google.', 'googleapiclient')) and r.levelno == logging.DEBUG]
        assert logging.getLogger('google').getEffectiveLevel() == logging.INFO
        assert logging.getLogger('googleapiclient').getEffectiveLevel() == logging.INFO
    finally:
        root.setLevel(old)
