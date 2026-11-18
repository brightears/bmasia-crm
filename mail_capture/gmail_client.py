"""The Gmail client protocol and a fake that reads fixtures.

The real client is ``google_client.GoogleGmailClient``. ``QuotaPacer`` keeps
calls under Gmail's per-minute quota. ``FakeGmailClient`` answers in Gmail API shape from a
fixture directory or from dicts built in a test, keeps a history sequence, and
can be told to fail with 404, 429 or 500.

Fixture directory layout: one ``<mailbox address>.json`` per mailbox::

    {
      "history_id": "1000",              # mailbox historyId before any record
      "labels": [{"id": "Label_7", "name": "CRM private", "type": "user"}],
      "messages": [
        {"eml": "inbound-1.eml", "id": "a1", "threadId": "t1",
         "labelIds": ["INBOX"], "internalDate": "4102444800000"},
        {"gmail": {...a message in Gmail API shape...}}
      ],
      "history": [                       # optional; records after history_id
        {"messagesAdded": ["a2"]}, {"labelsAdded": {"a1": ["Label_7"]}}
      ],
      "errors": [{"method": "list_history", "status": 404, "times": 1}]
    }

``.eml`` files are converted with ``eml_to_gmail``. Fixtures in this repository
are synthetic: invented people and domains under example.com, example.org or
.test only.
"""
import base64
import copy
import email
import email.policy
import email.utils
import json
import threading
import time
from pathlib import Path
from typing import Protocol, runtime_checkable


# Quota units per call (Gmail usage limits, research/11 B.2).
QUOTA_UNITS = {
    'get_profile': 1,
    'list_labels': 1,
    'list_messages': 5,
    'list_history': 2,
    'get_message': 20,
    'get_message_minimal': 20,
    'get_message_full': 60,
    'get_attachment': 20,
}

# Gmail API usage limits (developers.google.com/workspace/gmail/api/reference/quota,
# read 19 Nov 2026): 1,200,000 quota units per minute per project and 6,000 per
# minute per user (mailbox). The settings CAPTURE_GMAIL_USER_UNITS_PER_MINUTE and
# CAPTURE_GMAIL_PROJECT_UNITS_PER_MINUTE override them (lower only makes sense).
USER_UNITS_PER_MINUTE = 6000
PROJECT_UNITS_PER_MINUTE = 1200000


class QuotaPacer:
    """A token bucket that keeps any 60-second window under ``per_minute``
    quota units.

    The bucket holds at most ``burst`` units (a fifth of the minute's limit by
    default) and refills at the rest of the limit spread over the minute, so
    burst + refill over 60 s equals the limit. It starts empty: a run that
    begins right after another (even in a new process) cannot add a burst on
    top of the previous run's last minute. A call costing more than the bucket
    holds waits for a full bucket and leaves it in debt.

    ``acquire`` sleeps with the caller's ``sleep``; it never loops, so a test
    sleep that returns at once cannot hang it. ``drain`` empties the bucket
    after Gmail answered 429 anyway.
    """

    def __init__(self, per_minute, burst_fraction=0.2, clock=time.monotonic):
        per_minute = max(1, int(per_minute))
        self.per_minute = per_minute
        self.burst = max(1.0, per_minute * burst_fraction)
        self.rate = (per_minute - self.burst) / 60.0 or per_minute / 60.0
        self._clock = clock
        self._tokens = 0.0
        self._at = clock()
        self._lock = threading.Lock()
        self.waited = 0.0

    def _refill(self):
        now = self._clock()
        self._tokens = min(self.burst, self._tokens + max(0.0, now - self._at) * self.rate)
        self._at = now

    def wait_for(self, units):
        """Seconds until ``units`` may be spent (0 if now)."""
        with self._lock:
            self._refill()
            need = min(float(units), self.burst)
            return max(0.0, (need - self._tokens) / self.rate)

    def acquire(self, units, sleep=time.sleep):
        with self._lock:
            self._refill()
            need = min(float(units), self.burst)
            wait = max(0.0, (need - self._tokens) / self.rate)
            if wait:
                # Credit the refill the sleep will bring, then spend.
                self._tokens += wait * self.rate
                self._at = self._clock()
        if wait:
            self.waited += wait
            sleep(wait)
        with self._lock:
            self._tokens -= float(units)
            self._at = max(self._at, self._clock())
        return wait

    def drain(self):
        with self._lock:
            self._tokens = min(self._tokens, 0.0)
            self._at = self._clock()


_PACERS = {}
_PACERS_LOCK = threading.Lock()


def _limit(name, default):
    try:
        from django.conf import settings
        value = int(getattr(settings, name, default) or default)
    except Exception:
        value = default
    return max(1, min(value, default))


def pacers_for(mailbox_email):
    """The per-mailbox pacer and the project pacer, shared by every client in
    this process (consecutive runs of one mailbox share its bucket)."""
    user_limit = _limit('CAPTURE_GMAIL_USER_UNITS_PER_MINUTE', USER_UNITS_PER_MINUTE)
    project_limit = _limit('CAPTURE_GMAIL_PROJECT_UNITS_PER_MINUTE', PROJECT_UNITS_PER_MINUTE)
    with _PACERS_LOCK:
        key = ('user', mailbox_email.lower(), user_limit)
        if key not in _PACERS:
            _PACERS[key] = QuotaPacer(user_limit)
        project_key = ('project', '', project_limit)
        if project_key not in _PACERS:
            _PACERS[project_key] = QuotaPacer(project_limit)
        return _PACERS[key], _PACERS[project_key]


def reset_pacers():
    with _PACERS_LOCK:
        _PACERS.clear()


class GmailError(Exception):
    """An error answer from Gmail. ``status`` is the HTTP status."""

    def __init__(self, status, reason=''):
        self.status = int(status)
        self.reason = reason or ''
        super().__init__(f'gmail {self.status} {self.reason}'.strip())


class GmailNotFound(GmailError):
    """404 or 410: unknown or deleted message, or a history id too old to list from."""


class GmailRateLimited(GmailError):
    """429, or 403 with reason rateLimitExceeded / userRateLimitExceeded.
    ``retry_after`` is Gmail's Retry-After in seconds when it sent one."""

    def __init__(self, status, reason='', retry_after=None):
        super().__init__(status, reason)
        self.retry_after = retry_after


class GmailServerError(GmailError):
    """5xx, or a transport failure (retryable)."""


# Operator hints for authentication and permission failures. Each names the
# setup step that is the likely cause; none carries a token, an assertion or a
# key path (only these fixed texts and the OAuth error code are ever shown).
AUTH_HINTS = {
    'unauthorized_client': 'domain-wide delegation is missing for this service account or does not list '
                           'this scope: check the delegation entry (Unique ID and scope) in the Admin console',
    'access_denied': 'the scope is not authorised: GOOGLE_CAPTURE_SCOPE must match the delegation entry',
    'invalid_scope': 'the scope is not authorised: GOOGLE_CAPTURE_SCOPE must match the delegation entry',
    'invalid_grant': 'the grant was refused: check GOOGLE_CAPTURE_SERVICE_ACCOUNT or the key file, that the '
                     'mailbox address exists in the domain, and the server clock',
    'invalid_client': 'the service account or its key is not valid: check GOOGLE_CAPTURE_SERVICE_ACCOUNT '
                      'or replace the key file',
    'token_endpoint_unreachable': 'the Google token endpoint could not be reached: check outbound network '
                                  'access from this service',
    'signblob_refused': 'signBlob refused: grant Token Creator on the service account to the federated '
                        'principal, enable the IAM Credentials API, check GOOGLE_CAPTURE_SERVICE_ACCOUNT',
    'token_refused': 'the token request was refused: check the delegation entry, the scope and '
                     'GOOGLE_CAPTURE_SERVICE_ACCOUNT',
    'gmail_unauthorized': 'Gmail refused the token: check the delegation entry and its scope',
    'api_not_enabled': 'the Gmail API is not enabled in the Google Cloud project',
    'permission_denied': 'permission denied: check the delegation entry and scope, and that the mailbox '
                         'exists and has Gmail enabled',
    'credentials': 'the capture credential could not be made: check the GOOGLE_CAPTURE_* settings',
}


class GmailAuthError(GmailError):
    """Authentication or permission refused. Never retried: the run ends at
    once with outcome ``auth_error``. ``code`` is a short safe code;
    ``hint`` names the setup step that is the likely cause."""

    def __init__(self, code, status=401):
        code = code if code in AUTH_HINTS else 'permission_denied'
        super().__init__(status, code)
        self.code = code
        self.hint = AUTH_HINTS[code]


_RATE_REASONS = ('ratelimitexceeded', 'userratelimitexceeded', 'quotaexceeded', 'dailylimitexceeded')
_API_DISABLED_REASONS = ('accessnotconfigured', 'service_disabled', 'servicedisabled')


def error_for_status(status, reason='', retry_after=None):
    status = int(status)
    reason = reason or ''
    low = reason.lower()
    if status in (404, 410):
        return GmailNotFound(status, reason)
    if status == 429 or (status == 403 and low in _RATE_REASONS):
        return GmailRateLimited(status, reason or 'rateLimitExceeded', retry_after)
    if status == 401:
        return GmailAuthError('gmail_unauthorized', 401)
    if status == 403:
        # A 403 that is not a rate limit is a permission error: never retried.
        return GmailAuthError('api_not_enabled' if low in _API_DISABLED_REASONS else 'permission_denied', 403)
    if status >= 500:
        return GmailServerError(status, reason)
    return GmailError(status, reason)


@runtime_checkable
class GmailClient(Protocol):
    """What the sync engine needs from Gmail, one mailbox per client.

    Return values are the decoded JSON bodies of the matching Gmail API calls.
    Errors are raised as ``GmailError`` subclasses.
    """

    mailbox_email: str

    def get_profile(self) -> dict:
        """users.getProfile: emailAddress, messagesTotal, historyId."""

    def list_labels(self) -> list:
        """users.labels.list: [{'id', 'name', 'type'}]."""

    def list_messages(self, page_token=None, q=None, max_results=100) -> dict:
        """users.messages.list, newest first: messages [{'id', 'threadId'}],
        nextPageToken."""

    def list_history(self, start_history_id, page_token=None, max_results=100) -> dict:
        """users.history.list with messageAdded, messageDeleted, labelAdded and
        labelRemoved: history [...], nextPageToken, historyId."""

    def get_message(self, message_id, format='metadata', metadata_headers=None) -> dict:
        """users.messages.get with format metadata, minimal (labels only) or full."""

    def get_attachment(self, message_id, attachment_id) -> dict:
        """users.messages.attachments.get."""

    # Optional: a client with ``supports_batch = True`` also offers
    # ``get_messages(ids, format, metadata_headers) -> {id: message | None | GmailError}``,
    # many messages.get in one HTTP batch: None for a message gone since it was
    # listed (404/410), a GmailError instance for that one item's own failure.
    # A failure of the whole batch request is raised.
    #
    # Optional: ``pace(units, sleep)`` waits until ``units`` quota units may be
    # spent (the real client's token buckets); ``drain_pace()`` after a 429.


# --- .eml conversion --------------------------------------------------------

def _b64url(data):
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def eml_to_gmail(raw, gmail_id, thread_id='', label_ids=None, internal_date_ms=None):
    """Convert RFC 822 bytes into a Gmail API ``format=full`` message dict.

    Header values are kept exactly as written (folding and encoded words
    included), the hardest case for the parser.
    """
    if isinstance(raw, str):
        raw = raw.encode('utf-8')
    msg = email.message_from_bytes(raw, policy=email.policy.compat32)
    counter = [0]

    def convert(part):
        # compat32 keeps each header value exactly as written, folding included.
        headers = [{'name': k, 'value': v} for k, v in part._headers]
        node = {
            'partId': str(counter[0]),
            'mimeType': part.get_content_type(),
            'filename': part.get_filename() or '',
            'headers': headers,
            'body': {'size': 0},
        }
        counter[0] += 1
        if part.is_multipart():
            node['parts'] = [convert(child) for child in part.get_payload()]
            return node
        payload = part.get_payload(decode=True) or b''
        if node['filename']:
            node['body'] = {'size': len(payload), 'attachmentId': f'att-{gmail_id}-{node["partId"]}'}
        else:
            node['body'] = {'size': len(payload), 'data': _b64url(payload)}
        return node

    payload = convert(msg)
    if internal_date_ms is None:
        parsed = email.utils.parsedate_to_datetime(msg['Date']) if msg['Date'] else None
        internal_date_ms = str(int(parsed.timestamp() * 1000)) if parsed else '0'
    return {
        'id': gmail_id,
        'threadId': thread_id or gmail_id,
        'labelIds': list(label_ids or ['INBOX']),
        'internalDate': str(internal_date_ms),
        'sizeEstimate': len(raw),
        'payload': payload,
    }


def _metadata_view(message, metadata_headers):
    """What Gmail returns for format=metadata: top-level headers only, no bodies."""
    out = {k: copy.deepcopy(v) for k, v in message.items() if k != 'payload'}
    payload = message.get('payload') or {}
    wanted = {h.lower() for h in (metadata_headers or ())}
    headers = [
        dict(h) for h in payload.get('headers') or ()
        if not wanted or str(h.get('name', '')).lower() in wanted
    ]
    out['payload'] = {
        'mimeType': payload.get('mimeType', ''),
        'headers': headers,
    }
    # Attachment metadata is visible to the engine only through format=full.
    return out


# --- the fake ---------------------------------------------------------------

class FakeGmailClient:
    """In-memory Gmail for one mailbox. Records every call in ``calls``."""

    def __init__(self, mailbox_email, messages=(), labels=(), history_id=1000, errors=(), batch=False):
        self.mailbox_email = mailbox_email.lower()
        # With batch=True the fake answers get_messages, like the real client.
        self.supports_batch = bool(batch)
        self.calls = []
        self._messages = {}          # gmail id -> full message dict
        self._order = []             # gmail ids, oldest first
        self._labels = [dict(label) for label in labels]
        self._history = []           # [{'id': int, ...}]
        self._history_id = int(history_id)
        self._oldest_valid_history = int(history_id)
        self._errors = []            # [{'method', 'status', 'reason', 'times', 'after'}]
        self._item_errors = {}       # gmail id -> [{'status', 'reason', 'times', 'retry_after'}]
        self.pacer = None            # a QuotaPacer, when a test wants pacing
        for message in messages:
            self._put(message)
        for item in errors:
            self.fail(**item)

    # -- fixture loading ---------------------------------------------------
    @classmethod
    def from_fixture_dir(cls, directory, mailbox_email):
        directory = Path(directory)
        spec = json.loads((directory / f'{mailbox_email.lower()}.json').read_text('utf-8'))
        messages = []
        for item in spec.get('messages', []):
            if 'gmail' in item:
                messages.append(item['gmail'])
                continue
            raw = (directory / item['eml']).read_bytes()
            messages.append(eml_to_gmail(
                raw, item['id'], item.get('threadId', ''), item.get('labelIds'),
                item.get('internalDate'),
            ))
        client = cls(
            mailbox_email, labels=spec.get('labels', []),
            history_id=int(spec.get('history_id', 1000)), errors=spec.get('errors', []),
        )
        by_id = {m['id']: m for m in messages}
        added_later = set()
        for record in spec.get('history', []):
            added_later.update(record.get('messagesAdded', []))
        for message in messages:
            if message['id'] not in added_later:
                client._put(message)
        for record in spec.get('history', []):
            for gmail_id in record.get('messagesAdded', []):
                client.add_message(by_id[gmail_id])
            for gmail_id, label_ids in (record.get('labelsAdded') or {}).items():
                client.add_labels(gmail_id, label_ids)
            for gmail_id, label_ids in (record.get('labelsRemoved') or {}).items():
                client.remove_labels(gmail_id, label_ids)
            for gmail_id in record.get('messagesDeleted', []):
                client.delete_message(gmail_id)
        return client

    # -- test controls -----------------------------------------------------
    def fail(self, method, status, times=1, reason='', after=0):
        """Make the next ``times`` calls of ``method`` fail with ``status``
        (after letting ``after`` calls through)."""
        self._errors.append({
            'method': method, 'status': int(status), 'times': int(times),
            'reason': reason, 'after': int(after),
        })

    def fail_item(self, message_id, status, times=1, reason='', retry_after=None):
        """Make the next ``times`` fetches of one message fail with ``status``
        (in a batch: that item only)."""
        self._item_errors.setdefault(message_id, []).append({
            'status': int(status), 'reason': reason, 'times': int(times), 'retry_after': retry_after,
        })

    def _item_error(self, message_id):
        for item in self._item_errors.get(message_id, ()):
            if item['times'] > 0:
                item['times'] -= 1
                return error_for_status(item['status'], item['reason'], item['retry_after'])
        return None

    def pace(self, units, sleep):
        if self.pacer is not None:
            self.pacer.acquire(units, sleep)

    def drain_pace(self):
        if self.pacer is not None:
            self.pacer.drain()

    def _put(self, message):
        message = copy.deepcopy(message)
        if message['id'] not in self._messages:
            self._order.append(message['id'])
        self._messages[message['id']] = message

    def _record(self, **change):
        self._history_id += 1
        record = {'id': str(self._history_id)}
        record.update(change)
        self._history.append(record)
        return record

    @staticmethod
    def _ref(message):
        return {
            'id': message['id'], 'threadId': message.get('threadId', ''),
            'labelIds': list(message.get('labelIds', [])),
        }

    def add_message(self, message):
        self._put(message)
        stored = self._messages[message['id']]
        self._record(messages=[self._ref(stored)], messagesAdded=[{'message': self._ref(stored)}])

    def add_labels(self, gmail_id, label_ids):
        stored = self._messages[gmail_id]
        stored['labelIds'] = list(dict.fromkeys(list(stored.get('labelIds', [])) + list(label_ids)))
        self._record(labelsAdded=[{'message': self._ref(stored), 'labelIds': list(label_ids)}])

    def remove_labels(self, gmail_id, label_ids):
        stored = self._messages[gmail_id]
        stored['labelIds'] = [x for x in stored.get('labelIds', []) if x not in label_ids]
        self._record(labelsRemoved=[{'message': self._ref(stored), 'labelIds': list(label_ids)}])

    def delete_message(self, gmail_id):
        stored = self._messages.pop(gmail_id)
        self._order.remove(gmail_id)
        self._record(messagesDeleted=[{'message': self._ref(stored)}])

    def expire_history(self):
        """Make every history id up to now too old (the next list gives 404)."""
        self._oldest_valid_history = self._history_id

    @property
    def history_id(self):
        return str(self._history_id)

    # -- protocol ----------------------------------------------------------
    def _enter(self, method, **kwargs):
        self.calls.append((method, kwargs))
        for item in self._errors:
            if item['method'] != method or item['times'] <= 0:
                continue
            if item['after'] > 0:
                item['after'] -= 1
                continue
            item['times'] -= 1
            raise error_for_status(item['status'], item['reason'])

    def get_profile(self):
        self._enter('get_profile')
        return {
            'emailAddress': self.mailbox_email,
            'messagesTotal': len(self._messages),
            'historyId': str(self._history_id),
        }

    def list_labels(self):
        self._enter('list_labels')
        return [dict(label) for label in self._labels]

    def list_messages(self, page_token=None, q=None, max_results=100):
        self._enter('list_messages', page_token=page_token, q=q)
        ids = list(reversed(self._order))  # newest first, as Gmail lists them
        start = int(page_token or 0)
        page = ids[start:start + max_results]
        out = {
            'messages': [
                {'id': gid, 'threadId': self._messages[gid].get('threadId', '')} for gid in page
            ],
            'resultSizeEstimate': len(ids),
        }
        if start + max_results < len(ids):
            out['nextPageToken'] = str(start + max_results)
        return out

    def list_history(self, start_history_id, page_token=None, max_results=100):
        self._enter('list_history', start_history_id=start_history_id, page_token=page_token)
        start = int(start_history_id)
        if start < self._oldest_valid_history:
            raise GmailNotFound(404, 'historyId too old')
        records = [r for r in self._history if int(r['id']) > start]
        offset = int(page_token or 0)
        page = records[offset:offset + max_results]
        out = {'history': copy.deepcopy(page), 'historyId': str(self._history_id)}
        if offset + max_results < len(records):
            out['nextPageToken'] = str(offset + max_results)
        return out

    def get_message(self, message_id, format='metadata', metadata_headers=None):
        self._enter('get_message', message_id=message_id, format=format)
        error = self._item_error(message_id)
        if error is not None:
            raise error
        if message_id not in self._messages:
            raise GmailNotFound(404, 'message not found')
        message = self._messages[message_id]
        if format == 'full':
            return copy.deepcopy(message)
        if format == 'minimal':
            return {k: copy.deepcopy(message.get(k)) for k in ('id', 'threadId', 'labelIds', 'internalDate')}
        return _metadata_view(message, metadata_headers)

    def get_messages(self, message_ids, format='metadata', metadata_headers=None):
        if not self.supports_batch:
            raise AttributeError('this fake was built without batch support')
        ids = list(message_ids)
        self._enter('get_messages', ids=ids, format=format)
        out = {}
        for message_id in ids:
            message = self._messages.get(message_id)
            error = self._item_error(message_id)
            if error is not None:
                out[message_id] = None if isinstance(error, GmailNotFound) else error
            elif message is None:
                out[message_id] = None
            elif format == 'full':
                out[message_id] = copy.deepcopy(message)
            else:
                out[message_id] = _metadata_view(message, metadata_headers)
        return out

    def get_attachment(self, message_id, attachment_id):
        self._enter('get_attachment', message_id=message_id, attachment_id=attachment_id)
        if message_id not in self._messages:
            raise GmailNotFound(404, 'message not found')
        return {'size': 0, 'data': ''}


def fake_factory(clients):
    """A client factory that can only hand out ``FakeGmailClient`` objects.

    The sync engine accepts nothing else while capture is switched off, and
    it checks the marker before calling the factory, so no credential can be
    minted on that path. ``clients`` maps mailbox addresses to fakes.
    """
    by_email = {}
    for client in (clients.values() if isinstance(clients, dict) else clients):
        if type(client) is not FakeGmailClient and not isinstance(client, FakeGmailClient):
            raise TypeError('fake_factory takes FakeGmailClient objects only')
        by_email[client.mailbox_email] = client

    def factory(mailbox):
        return by_email[mailbox.email]

    factory.fake_only_factory = True
    return factory
