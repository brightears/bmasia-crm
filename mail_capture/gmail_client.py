"""The Gmail client protocol and a fake that reads fixtures.

There is no real Google client in this module (that comes with the credential
factory in a later PR). ``FakeGmailClient`` answers in Gmail API shape from a
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


class GmailError(Exception):
    """An error answer from Gmail. ``status`` is the HTTP status."""

    def __init__(self, status, reason=''):
        self.status = int(status)
        self.reason = reason or ''
        super().__init__(f'gmail {self.status} {self.reason}'.strip())


class GmailNotFound(GmailError):
    """404: unknown message, or a history id too old to list from."""


class GmailRateLimited(GmailError):
    """429, or 403 with reason rateLimitExceeded / userRateLimitExceeded."""


class GmailServerError(GmailError):
    """5xx."""


def error_for_status(status, reason=''):
    status = int(status)
    if status == 404:
        return GmailNotFound(status, reason)
    if status == 429 or (status == 403 and 'ratelimit' in reason.lower()):
        return GmailRateLimited(status, reason or 'rateLimitExceeded')
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
    # ``get_messages(ids, format, metadata_headers) -> {id: message or None}``,
    # many messages.get in one HTTP batch (None for a message gone since listed).


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
            if message is None:
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
