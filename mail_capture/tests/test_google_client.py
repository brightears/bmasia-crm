"""The real Gmail client and the credential factory, against a fake HTTP
transport. Every response is synthetic, in the shape the Gmail API returns.
Nothing here reaches Google: the transport is a local object."""
import json
import socket
import subprocess
import sys
from io import StringIO
from urllib.parse import parse_qs, urlparse

import httplib2
import pytest
from django.core.management import call_command

from mail_capture import credentials as creds
from mail_capture.gmail_client import (
    FakeGmailClient, GmailError, GmailNotFound, GmailRateLimited, GmailServerError,
)
from mail_capture.google_client import BATCH_SIZE, GoogleGmailClient
from mail_capture.models import MailboxAccessLog, MailMessage
from mail_capture.sync import sync_mailbox

from .builders import SALES, gmail_message, make_company, make_contact, make_mailbox, recent


pytestmark = pytest.mark.django_db


class FakeHttp:
    """Stands in for httplib2.Http: routes by path, records every request."""

    def __init__(self, routes):
        self.routes = routes        # list of (predicate(method, path, query, body), handler) pairs
        self.requests = []

    def request(self, uri, method='GET', body=None, headers=None, redirections=None, connection_type=None):
        parsed = urlparse(uri)
        query = parse_qs(parsed.query)
        if isinstance(body, bytes):
            body = body.decode('utf-8', 'replace')
        self.requests.append((method, parsed.path, query, body))
        for predicate, handler in self.routes:
            if predicate(method, parsed.path, query, body):
                status, payload, extra = handler(method, parsed.path, query, body)
                resp = httplib2.Response({'status': str(status), 'content-type': 'application/json', **extra})
                content = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
                return resp, content.encode() if isinstance(content, str) else content
        resp = httplib2.Response({'status': '599', 'content-type': 'application/json'})
        return resp, b'{"error": {"message": "no route in the fake transport"}}'


def ok(payload):
    return lambda *a: (200, payload, {})


def error(status, reason=''):
    body = {'error': {'code': status, 'message': 'synthetic', 'errors': [{'reason': reason}] if reason else []}}
    return lambda *a: (status, body, {})


def path_is(suffix, method='GET'):
    return lambda m, p, q, b: m == method and p.endswith(suffix)


BOUNDARY = 'batch_synthetic_boundary'


def batch_response(parts):
    """Multipart/mixed body as Gmail's batch endpoint returns it."""
    chunks = []
    for content_id, status, payload in parts:
        chunks.append(
            f'--{BOUNDARY}\r\nContent-Type: application/http\r\nContent-ID: <response-x + {content_id}>\r\n\r\n'
            f'HTTP/1.1 {status} {"OK" if status == 200 else "Error"}\r\nContent-Type: application/json\r\n\r\n'
            f'{json.dumps(payload)}\r\n')
    return ''.join(chunks) + f'--{BOUNDARY}--\r\n'


def batch_handler(messages, statuses=None):
    """Answers a batch POST from the given {gmail id: message} map."""
    statuses = statuses or {}

    def handle(method, path, query, body):
        import re
        ids = re.findall(r'/messages/([^/?\s]+)\?', body)
        parts = []
        for gid in ids:
            status = statuses.get(gid, 200 if gid in messages else 404)
            payload = messages.get(gid) if status == 200 else {'error': {'code': status, 'message': 'x'}}
            parts.append((gid, status, payload))
        return 200, batch_response(parts), {'content-type': f'multipart/mixed; boundary={BOUNDARY}'}

    return handle


def client(routes):
    http = FakeHttp(routes)
    return GoogleGmailClient(SALES, http=http), http


# --- the client ---------------------------------------------------------------------------

def test_profile_labels_and_listing():
    c, http = client([
        (path_is('/profile'), ok({'emailAddress': SALES, 'messagesTotal': 3, 'historyId': '1234'})),
        (path_is('/labels'), ok({'labels': [{'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}]})),
        (path_is('/messages'), ok({'messages': [{'id': 'g1', 'threadId': 't1'}], 'nextPageToken': 'p2'})),
    ])
    assert c.get_profile()['historyId'] == '1234'
    assert c.list_labels() == [{'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}]
    page = c.list_messages(page_token='p1', max_results=50)
    assert page['nextPageToken'] == 'p2'
    method, path, query, _ = http.requests[-1]
    assert path.endswith('/gmail/v1/users/me/messages') and query == {'maxResults': ['50'], 'pageToken': ['p1'], 'alt': ['json']}


def test_history_asks_for_the_four_change_types():
    c, http = client([(path_is('/history'), ok({'history': [], 'historyId': '99'}))])
    assert c.list_history('42', page_token='t', max_results=100)['historyId'] == '99'
    _, _, query, _ = http.requests[-1]
    assert query['startHistoryId'] == ['42'] and query['pageToken'] == ['t']
    assert sorted(query['historyTypes']) == ['labelAdded', 'labelRemoved', 'messageAdded', 'messageDeleted']


def test_metadata_get_requests_the_header_list():
    c, http = client([(path_is('/messages/g1'), ok({'id': 'g1'}))])
    c.get_message('g1', format='metadata')
    _, _, query, _ = http.requests[-1]
    assert query['format'] == ['metadata'] and 'Message-ID' in query['metadataHeaders']
    assert 'X-BMAsia-Email-ID' in query['metadataHeaders'] and 'Authentication-Results' in query['metadataHeaders']


@pytest.mark.parametrize('status, reason, expected', [
    (404, 'notFound', GmailNotFound), (429, 'rateLimitExceeded', GmailRateLimited),
    (403, 'userRateLimitExceeded', GmailRateLimited), (500, 'backendError', GmailServerError),
    (503, '', GmailServerError),
])
def test_errors_become_gmail_errors(status, reason, expected):
    c, _ = client([(path_is('/history'), error(status, reason))])
    with pytest.raises(expected) as caught:
        c.list_history('1')
    assert caught.value.status == status


def test_a_transport_failure_is_a_retryable_503():
    class Broken:
        def request(self, *a, **k):
            raise socket.timeout('synthetic')

    c = GoogleGmailClient(SALES, http=Broken())
    with pytest.raises(GmailServerError) as caught:
        c.get_profile()
    assert caught.value.status == 503


def test_batch_fetch_returns_messages_and_none_for_gone_ones():
    messages = {'g1': {'id': 'g1', 'labelIds': ['INBOX']}, 'g3': {'id': 'g3'}}
    c, http = client([(path_is('/batch', 'POST'), batch_handler(messages))])
    out = c.get_messages(['g1', 'g2', 'g3'])
    assert out == {'g1': messages['g1'], 'g2': None, 'g3': messages['g3']}
    assert len(http.requests) == 1 and 'format=metadata' in http.requests[0][3]


def test_batches_hold_at_most_fifty_calls():
    ids = [f'g{i}' for i in range(BATCH_SIZE + 10)]
    c, http = client([(path_is('/batch', 'POST'), batch_handler({i: {'id': i} for i in ids}))])
    assert len(c.get_messages(ids)) == len(ids)
    assert len(http.requests) == 2


def test_a_failed_item_in_a_batch_comes_back_as_its_own_error():
    c, _ = client([(path_is('/batch', 'POST'),
                    batch_handler({'g1': {'id': 'g1'}}, statuses={'g2': 429, 'g3': 400, 'g4': 410}))])
    out = c.get_messages(['g1', 'g2', 'g3', 'g4'])
    assert out['g1'] == {'id': 'g1'} and out['g4'] is None
    assert isinstance(out['g2'], GmailRateLimited) and type(out['g3']) is GmailError
    assert out['g3'].status == 400


def test_end_to_end_sync_through_the_real_client(capture_on):
    """The engine, the real client and the fake transport together."""
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox()
    mb.history_id = '100'
    mb.save(update_fields=['history_id'])
    message = gmail_message('g1', 'Pat <pat@lagoon.test>', [SALES], date=recent(2))
    c, http = client([
        (path_is('/labels'), ok({'labels': []})),
        (path_is('/history'), ok({'history': [{'id': '101', 'messagesAdded': [
            {'message': {'id': 'g1', 'threadId': 't1', 'labelIds': ['INBOX']}}]}], 'historyId': '101'})),
        (path_is('/batch', 'POST'), batch_handler({'g1': message})),
    ])
    result = sync_mailbox(mb.pk, lambda m: c, sleep=lambda s: None)
    assert result.outcome == 'ok' and result.counts['stored'] == 1
    mb.refresh_from_db()
    assert mb.history_id == '101' and MailMessage.objects.count() == 1


def test_building_the_client_makes_no_request():
    http = FakeHttp([])
    GoogleGmailClient(SALES, http=http)
    assert http.requests == []


# --- the credential factory -----------------------------------------------------------

@pytest.fixture
def switched_on(capture_on):
    capture_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'key_file'
    capture_on.GOOGLE_CAPTURE_SCOPE = 'metadata'
    capture_on.GOOGLE_CAPTURE_NEVER_MAILBOXES = []
    return capture_on


@pytest.fixture
def key_file(tmp_path):
    """A synthetic service-account key, generated for the test."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    path = tmp_path / 'synthetic-key.json'
    path.write_text(json.dumps({
        'type': 'service_account', 'project_id': 'synthetic-project', 'private_key_id': 'synthetic',
        'private_key': pem, 'client_email': 'capture@synthetic-project.iam.gserviceaccount.com',
        'client_id': '1', 'token_uri': 'https://oauth2.googleapis.com/token',
    }))
    return str(path)


def test_mode_off_raises(capture_on):
    mb = make_mailbox()
    with pytest.raises(creds.CredentialsOff):
        creds.delegated_credentials(mb)


def test_switched_off_capture_refuses_before_any_mode(settings):
    settings.GOOGLE_CAPTURE_ENABLED = False
    settings.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'key_file'
    mb = make_mailbox()
    with pytest.raises(creds.CredentialsRefused, match='GOOGLE_CAPTURE_ENABLED'):
        creds.delegated_credentials(mb)


def test_disabled_and_denied_mailboxes_are_refused(switched_on, key_file):
    switched_on.GOOGLE_CAPTURE_KEY_FILE = key_file
    off = make_mailbox('off@ourco.example', enabled=False)
    with pytest.raises(creds.CredentialsRefused, match='not enabled'):
        creds.delegated_credentials(off)
    denied = make_mailbox('hr@ourco.example')
    switched_on.GOOGLE_CAPTURE_NEVER_MAILBOXES = ['HR@ourco.example']
    with pytest.raises(creds.CredentialsRefused, match='NEVER_MAILBOXES'):
        creds.delegated_credentials(denied)


def test_body_mode_needs_the_readonly_scope(switched_on, key_file):
    switched_on.GOOGLE_CAPTURE_KEY_FILE = key_file
    mb = make_mailbox(body_mode='body')
    with pytest.raises(creds.CredentialsRefused, match='readonly'):
        creds.delegated_credentials(mb)
    switched_on.GOOGLE_CAPTURE_SCOPE = 'readonly'
    assert creds.delegated_credentials(mb).scopes == ['https://www.googleapis.com/auth/gmail.readonly']


def test_key_file_credential_is_delegated_to_exactly_that_mailbox(switched_on, key_file, caplog):
    switched_on.GOOGLE_CAPTURE_KEY_FILE = key_file
    mb = make_mailbox()
    credential = creds.delegated_credentials(mb)
    assert credential._subject == SALES
    assert credential.scopes == ['https://www.googleapis.com/auth/gmail.metadata']
    assert not credential.valid          # no token was fetched
    assert key_file not in caplog.text


def test_a_missing_key_file_never_echoes_its_path(switched_on, tmp_path):
    switched_on.GOOGLE_CAPTURE_KEY_FILE = str(tmp_path / 'secret-name-xyz.json')
    mb = make_mailbox()
    with pytest.raises(creds.CredentialsMisconfigured) as caught:
        creds.delegated_credentials(mb)
    assert 'secret-name-xyz' not in str(caught.value)


def test_keyless_signs_as_the_service_account_without_any_request(switched_on, monkeypatch):
    import google.auth
    from google.auth import credentials as ga_credentials
    switched_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'keyless'
    switched_on.GOOGLE_CAPTURE_SERVICE_ACCOUNT = 'capture@synthetic-project.iam.gserviceaccount.com'
    seen = {}

    class Source(ga_credentials.Credentials):
        def refresh(self, request):
            raise AssertionError('no network in tests')

    def fake_default(scopes=None, **kwargs):
        seen['scopes'] = scopes
        return Source(), 'synthetic-project'

    monkeypatch.setattr(google.auth, 'default', fake_default)
    mb = make_mailbox()
    credential = creds.delegated_credentials(mb)
    assert seen['scopes'] == ['https://www.googleapis.com/auth/cloud-platform']
    assert credential.service_account_email == 'capture@synthetic-project.iam.gserviceaccount.com'
    assert credential._subject == SALES and not credential.valid


def test_keyless_without_a_service_account_is_misconfigured(switched_on):
    switched_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'keyless'
    switched_on.GOOGLE_CAPTURE_SERVICE_ACCOUNT = ''
    with pytest.raises(creds.CredentialsMisconfigured):
        creds.delegated_credentials(make_mailbox())


def test_importing_capture_does_not_import_the_google_libraries():
    code = ('import os, sys, django; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bmasia_crm.settings"); '
            'django.setup(); import mail_capture.credentials, mail_capture.google_client, mail_capture.sync; '
            'print(any(m.startswith(("googleapiclient", "google.auth", "google.oauth2")) for m in sys.modules))')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=120)
    assert out.stdout.strip().splitlines()[-1] == 'False', out.stderr[-500:]


# --- the gmail_sync command ------------------------------------------------------------

def test_gmail_sync_refuses_while_capture_is_off(settings, monkeypatch):
    settings.GOOGLE_CAPTURE_ENABLED = False
    make_mailbox()
    monkeypatch.setattr('mail_capture.google_client.client_for',
                        lambda m: (_ for _ in ()).throw(AssertionError('client made')))
    for args in (['--check'], ['--incremental'], ['--backfill', '--since', '2099-01-01'],
                 ['--mailbox', SALES, '--incremental', '--dry-run']):
        out = StringIO()
        call_command('gmail_sync', *args, stdout=out)
        assert 'capture disabled' in out.getvalue()


def test_gmail_sync_check_reports_counts_and_logs_the_read(switched_on, monkeypatch):
    mb = make_mailbox()
    fake = FakeGmailClient(mb.email, messages=[gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent())])
    monkeypatch.setattr('mail_capture.google_client.client_for', lambda m: fake)
    out = StringIO()
    call_command('gmail_sync', '--check', stdout=out)
    assert f'{SALES}: messages 1, history id {fake.history_id}' in out.getvalue()
    assert MailboxAccessLog.objects.get().purpose == 'check'


def test_gmail_sync_incremental_dry_run_writes_no_mail(switched_on, monkeypatch):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    mb = make_mailbox()
    fake = FakeGmailClient(mb.email)
    mb.history_id = fake.history_id
    mb.save(update_fields=['history_id'])
    fake.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent()))
    monkeypatch.setattr('mail_capture.google_client.client_for', lambda m: fake)
    out = StringIO()
    call_command('gmail_sync', '--mailbox', SALES, '--incremental', '--dry-run', stdout=out)
    assert 'ok' in out.getvalue() and 'matched=1' in out.getvalue()
    assert MailMessage.objects.count() == 0
    call_command('gmail_sync', '--mailbox', SALES, '--incremental', '--max-messages', '5', stdout=StringIO())
    assert MailMessage.objects.count() == 1


def test_gmail_sync_needs_a_mode(switched_on):
    make_mailbox()
    err = StringIO()
    with pytest.raises(SystemExit) as caught:
        call_command('gmail_sync', stdout=StringIO(), stderr=err)
    assert caught.value.code == 2 and 'choose' in err.getvalue().lower()


# --- the engine with a batching client ---------------------------------------------

def _lagoon_contact():
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')


def test_the_engine_fetches_in_batches_of_fifty(capture_on):
    _lagoon_contact()
    mb = make_mailbox()
    fake = FakeGmailClient(mb.email, batch=True)
    mb.history_id = fake.history_id
    mb.save(update_fields=['history_id'])
    for i in range(120):
        fake.add_message(gmail_message(f'g{i}', 'pat@lagoon.test', [SALES], date=recent(3),
                                       message_id=f'<b{i}@lagoon.test>'))
    result = sync_mailbox(mb.pk, lambda m: fake, sleep=lambda s: None, page_size=500)
    batches = [len(kw['ids']) for name, kw in fake.calls if name == 'get_messages']
    assert batches == [50, 50, 20] and not [c for c in fake.calls if c[0] == 'get_message']
    assert result.counts['stored'] == 120 and result.counts['quota_units'] >= 120 * 20


def test_a_batched_backfill_stops_near_its_bound(capture_on):
    from datetime import date, timedelta
    _lagoon_contact()
    mb = make_mailbox()
    messages = [gmail_message(f'old{i}', 'pat@lagoon.test', [SALES], date=recent(24 * 60 + i),
                              message_id=f'<old{i}@lagoon.test>') for i in range(200)]
    messages += [gmail_message(f'new{i}', 'pat@lagoon.test', [SALES], date=recent(i + 1),
                               message_id=f'<new{i}@lagoon.test>') for i in range(10)][::-1]
    fake = FakeGmailClient(mb.email, messages=messages, batch=True)
    sync_mailbox(mb.pk, lambda m: fake, kind='backfill', since=date.today() - timedelta(days=10),
                 sleep=lambda s: None, page_size=500)
    fetched = sum(len(kw['ids']) for name, kw in fake.calls if name == 'get_messages')
    assert MailMessage.objects.count() == 10 and fetched <= 50


def test_max_messages_with_batches_loses_nothing(capture_on):
    _lagoon_contact()
    mb = make_mailbox()
    fake = FakeGmailClient(mb.email, batch=True)
    mb.history_id = fake.history_id
    mb.save(update_fields=['history_id'])
    for i in range(70):
        fake.add_message(gmail_message(f'g{i}', 'pat@lagoon.test', [SALES], date=recent(3),
                                       message_id=f'<m{i}@lagoon.test>'))
    first = sync_mailbox(mb.pk, lambda m: fake, sleep=lambda s: None, max_messages=60, page_size=500)
    assert first.outcome == 'partial' and first.counts['stored'] == 60
    sync_mailbox(mb.pk, lambda m: fake, sleep=lambda s: None, page_size=500)
    assert MailMessage.objects.count() == 70
