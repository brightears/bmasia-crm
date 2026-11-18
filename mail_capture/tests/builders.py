"""Synthetic mail for tests. Every person, company and domain here is invented
(.test, example.com and example.org only); document numbers use the year 99."""
from datetime import datetime, timedelta, timezone as dt_timezone
from email.utils import format_datetime

from crm_app.models import Company, Contact

from mail_capture.gmail_client import FakeGmailClient, eml_to_gmail
from mail_capture.models import CaptureMailbox


OUR_DOMAIN = 'ourco.example'
SALES = f'sales@{OUR_DOMAIN}'
OPS = f'ops@{OUR_DOMAIN}'


def build_eml(headers, body='Synthetic body text.\n', content_type='text/plain; charset=utf-8'):
    """RFC 822 text from (name, value) pairs, values written as given."""
    lines = [f'{name}: {value}' for name, value in headers]
    names = {name.lower() for name, _ in headers}
    if 'mime-version' not in names:
        lines.append('MIME-Version: 1.0')
    if 'content-type' not in names:
        lines.append(f'Content-Type: {content_type}')
    return ('\r\n'.join(lines) + '\r\n\r\n' + body).encode('utf-8')


def gmail_message(gid, from_, to=(), cc=(), subject='Synthetic subject', message_id=None,
                  date=None, in_reply_to=None, references=None, labels=('INBOX',), extra=(),
                  body='Synthetic body text.\n', thread_id=None, omit=()):
    """A Gmail API message dict built from synthetic RFC 822 text."""
    date = date or datetime(2099, 1, 5, 9, 0, tzinfo=dt_timezone.utc)
    headers = [('From', from_)]
    if to:
        headers.append(('To', ', '.join(to) if not isinstance(to, str) else to))
    if cc:
        headers.append(('Cc', ', '.join(cc) if not isinstance(cc, str) else cc))
    headers.append(('Subject', subject))
    headers.append(('Date', format_datetime(date)))
    if message_id is not False:
        headers.append(('Message-ID', message_id or f'<{gid}@mail.example.org>'))
    if in_reply_to:
        headers.append(('In-Reply-To', in_reply_to))
    if references:
        headers.append(('References', references))
    headers.extend(extra)
    headers = [h for h in headers if h[0] not in omit]
    return eml_to_gmail(
        build_eml(headers, body), gmail_id=gid, thread_id=thread_id or f'thr-{gid}',
        label_ids=list(labels), internal_date_ms=str(int(date.timestamp() * 1000)),
    )


def recent(hours=1):
    """A time shortly before now, for runs bounded by the resync window."""
    return datetime.now(dt_timezone.utc).replace(microsecond=0) - timedelta(hours=hours)


def make_company(name, **kwargs):
    return Company.objects.create(name=name, **kwargs)


def make_contact(company, email, name='Synthetic Contact'):
    return Contact.objects.create(company=company, name=name, email=email)


def make_mailbox(email=SALES, enabled=True, **kwargs):
    return CaptureMailbox.objects.create(email=email, enabled=enabled, **kwargs)


def primed(mailbox, labels=()):
    """A fake client for ``mailbox`` whose cursor is already set, so the next
    incremental run reads only what the test adds."""
    client = FakeGmailClient(mailbox.email, labels=labels)
    mailbox.history_id = client.history_id
    mailbox.save(update_fields=['history_id'])
    return client


def factory_for(*clients):
    """A client factory that hands out the given fakes by mailbox address and
    records every call."""
    by_email = {c.mailbox_email: c for c in clients}
    calls = []

    def factory(mailbox):
        calls.append(mailbox.email)
        return by_email[mailbox.email]

    factory.calls = calls
    return factory


def no_client(mailbox):
    raise AssertionError('a Gmail client was requested')
