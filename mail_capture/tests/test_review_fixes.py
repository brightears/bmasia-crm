"""The PR-A review findings, each as the behaviour that must now hold.
Several only show on Postgres (it refuses NUL and over-long values)."""
import base64
import json
import time
import tracemalloc
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection

from crm_app.models import EmailLog, User

from mail_capture import parse, sync
from mail_capture.gmail_client import FakeGmailClient, eml_to_gmail, fake_factory
from mail_capture.identity import canonical_source_ref
from mail_capture.models import (
    CaptureFailure, CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog,
    MailboxCopy, MailConversation, MailMatch, MailMessage, UnmatchedSender,
)
from mail_capture.sync import CaptureRefused, sync_all_enabled, sync_mailbox

from .builders import (
    OPS, SALES, build_eml, factory_for, gmail_message, make_company, make_contact, make_mailbox,
    primed, recent,
)


pytestmark = pytest.mark.django_db
PG = connection.vendor == 'postgresql'


def run(mailbox, client, **kwargs):
    kwargs.setdefault('sleep', lambda s: None)
    return sync_mailbox(mailbox.pk, factory_for(client), **kwargs)


@pytest.fixture
def lagoon(capture_on):
    company = make_company('Lagoon Test Hotel')
    contact = make_contact(company, 'pat@lagoon.test', 'Pat Example')
    return company, contact


def inbound(gid, when=None, frm='Pat Example <pat@lagoon.test>', to=(SALES,), **kwargs):
    return gmail_message(gid, frm, to, date=when or recent(5), **kwargs)


def raw_message(gid, headers, when, labels=('INBOX',)):
    """A Gmail dict with header values exactly as given (no .eml round trip)."""
    return {
        'id': gid, 'threadId': f't-{gid}', 'labelIds': list(labels),
        'internalDate': str(int(when.timestamp() * 1000)),
        'payload': {'mimeType': 'text/plain', 'headers': [{'name': k, 'value': v} for k, v in headers]},
    }


# --- 1/2. poison messages never block a mailbox -----------------------------------

POISON = {
    'nul_subject': [('Subject', '=?utf-8?q?Hello=00World?=')],
    'raw_nul_everywhere': [('Subject', 'a\x00b'), ('Cc', 'Na\x00me <c\x00c@lagoon.test>')],
    'long_domain_cc': [('Subject', 'Hello'), ('Cc', 'x@' + 'd' * 300 + '.test')],
    'surrogate_subject': [('Subject', json.loads('"x\\ud800y"'))],
    'huge_subject': [('Subject', 'y' * 50000)],
    'bad_date': [('Subject', 's'), ('Date', 'Mon, 01 Jan 0001 00:00:00 +9999')],
}


@pytest.mark.parametrize('kind', sorted(POISON))
def test_poison_message_is_cleaned_and_the_mailbox_moves_on(lagoon, kind):
    mb = make_mailbox()
    client = primed(mb)
    when = recent(3)
    headers = [('From', 'Pat Example <pat@lagoon.test>'), ('To', SALES),
               ('Date', when.strftime('%a, %d %b %Y %H:%M:%S +0000')),
               ('Message-ID', f'<poison-{kind}@lagoon.test>')]
    headers = [h for h in headers if h[0] not in {k for k, _ in POISON[kind]}] + POISON[kind]
    client.add_message(raw_message('p1', headers, when))
    client.add_message(inbound('ok1'))
    result = run(mb, client)
    mb.refresh_from_db()
    assert result.outcome == 'ok' and mb.history_id == client.history_id
    assert MailMessage.objects.count() == 2
    message = MailMessage.objects.get(rfc_message_id=f'poison-{kind}@lagoon.test')
    for value in [message.subject, message.from_name] + list(
            message.participants.values_list('address', flat=True)):
        assert '\x00' not in value and not any(0xD800 <= ord(c) <= 0xDFFF for c in value)
    assert all(len(d) <= 253 for d in message.participants.values_list('domain', flat=True))
    if kind in ('long_domain_cc', 'huge_subject'):
        assert 'truncated' in message.flags or 'bounded' in message.flags


def test_a_message_the_database_still_refuses_is_recorded_and_skipped(lagoon, monkeypatch):
    """Simulates a value the parser failed to clean. Postgres refuses it; the
    message is recorded as failed and the rest of the page is stored."""
    real = sync.parse_gmail_message

    def dirty(raw):
        parsed = real(raw)
        if parsed.gmail_id == 'bad':
            parsed.subject = 'z' * 400     # over the column limit; only Postgres refuses it
        return parsed

    monkeypatch.setattr(sync, 'parse_gmail_message', dirty)
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad', message_id='<bad@lagoon.test>'))
    client.add_message(inbound('good', message_id='<good@lagoon.test>'))
    result = run(mb, client)
    mb.refresh_from_db()
    assert mb.history_id == client.history_id
    if PG:
        assert result.counts['failed'] == 1 and result.counts['stored'] == 1
        assert CaptureFailure.objects.get().gmail_id == 'bad'
        assert CaptureRun.objects.get(pk=result.run_id).failed_gmail_ids == ['bad']
    else:
        assert result.counts['stored'] == 2


# --- 3. one mailbox never stops the others ---------------------------------------

def test_one_failing_mailbox_does_not_stop_the_next(lagoon):
    a, b = make_mailbox('a-first@ourco.example'), make_mailbox('b-second@ourco.example')
    primed(a)
    cb = primed(b)
    cb.add_message(inbound('z1', to=('b-second@ourco.example',)))

    def factory(mailbox):
        if mailbox.email.startswith('a-'):
            raise RuntimeError('credential failure in the first mailbox')
        return cb

    results = sync_all_enabled(factory, sleep=lambda s: None, all_mailboxes=True)
    assert [r.outcome for r in results] == ['error', 'ok']
    assert MailMessage.objects.count() == 1
    a.refresh_from_db()
    assert a.consecutive_errors == 1 and a.last_error == 'client: RuntimeError'
    assert CaptureRun.objects.get(mailbox=a).outcome == 'error'


def test_an_engine_error_in_one_mailbox_does_not_stop_the_next(lagoon, monkeypatch):
    a, b = make_mailbox('a-first@ourco.example'), make_mailbox('b-second@ourco.example')
    ca, cb = primed(a), primed(b)
    ca.add_message(inbound('x1', to=('a-first@ourco.example',)))
    cb.add_message(inbound('z1', to=('b-second@ourco.example',)))
    real = sync._Runner._incremental

    def boom(self):
        if self.mailbox.email.startswith('a-'):
            raise MemoryError('simulated')
        return real(self)

    monkeypatch.setattr(sync._Runner, '_incremental', boom)
    results = sync_all_enabled(factory_for(ca, cb), sleep=lambda s: None, all_mailboxes=True)
    assert [r.outcome for r in results] == ['error', 'ok']
    a.refresh_from_db()
    assert a.consecutive_errors == 1


# --- 4. bounded cost per message ---------------------------------------------------

def _measure(fn):
    """Time without tracing (tracemalloc slows Python several times), then
    peak memory in a second, traced call."""
    t0 = time.perf_counter()
    out = fn()
    elapsed = time.perf_counter() - t0
    tracemalloc.start()
    try:
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return out, elapsed, peak


def _msg(headers, payload_extra=None):
    payload = {'mimeType': 'text/plain', 'headers': [{'name': k, 'value': v} for k, v in headers]}
    payload.update(payload_extra or {})
    return {'id': 'g', 'threadId': 't', 'labelIds': ['INBOX'], 'internalDate': '4070908800000',
            'payload': payload}


BASE = [('From', 'Pat <pat@lagoon.test>'), ('To', SALES), ('Message-ID', '<m@lagoon.test>')]


def _nest(depth):
    node = {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'leaf').decode()}}
    for _ in range(depth):
        node = {'mimeType': 'multipart/mixed', 'parts': [node]}
    return node


def _html(text):
    return {'mimeType': 'text/html', 'body': {'data': base64.urlsafe_b64encode(text.encode()).decode()}}


HOSTILE = {
    'subject of 150,000 encoded words': lambda: parse.parse_gmail_message(
        _msg(BASE + [('Subject', ' '.join(['=?utf-8?q?ab?='] * 150000))])),
    'subject of 10 MB': lambda: parse.parse_gmail_message(_msg(BASE + [('Subject', 'x' * 10_000_000)])),
    'address list of 200 KB of quotes': lambda: parse.parse_address_list('"' * 200_000),
    'address list of 1 MB of <': lambda: parse.parse_address_list('<' * 1_000_000),
    'To with 20,000 addresses': lambda: parse.parse_gmail_message(
        _msg([BASE[0], ('To', ', '.join(f'p{i}@x{i}.test' for i in range(20000))), BASE[2]])),
    'References with 60,000 ids': lambda: parse.parse_gmail_message(
        _msg(BASE + [('References', ' '.join(f'<r{i}@x.test>' for i in range(60000)))])),
    'MIME depth 5,000 (parse)': lambda: parse.parse_gmail_message(
        {'id': 'g', 'payload': dict(_nest(5000), headers=[{'name': k, 'value': v} for k, v in BASE])}),
    'MIME depth 5,000 (body)': lambda: parse.extract_body_text(_nest(5000)),
    '20,000 text parts': lambda: parse.extract_body_text({'mimeType': 'multipart/mixed', 'parts': [
        {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'x' * 1000).decode()}}
        for _ in range(20000)]}),
    'HTML 180 KB of unclosed <style': lambda: parse.extract_body_text(_html('<style' * 30000)),
    'HTML 400 KB of <': lambda: parse.extract_body_text(_html('<' * 400000)),
    'HTML 2 MB of normal markup': lambda: parse.extract_body_text(_html('<p>hello <b>world</b></p>' * 80000)),
    'HTML one unclosed tag of 200 KB': lambda: parse.extract_body_text(_html('<' + 'a' * 200000)),
    'Message-ID header 10,000 times': lambda: parse.parse_gmail_message(
        _msg(BASE + [('Message-ID', f'<d{i}@x>') for i in range(10000)])),
}


@pytest.mark.parametrize('name', sorted(HOSTILE))
def test_hostile_input_has_a_time_and_memory_ceiling(name):
    out, elapsed, peak = _measure(HOSTILE[name])
    assert elapsed < 2.0, f'{name}: {elapsed:.2f}s'
    assert peak < 64 * 1024 * 1024, f'{name}: {peak / 1e6:.0f} MB'


def test_bounds_are_flagged_and_lists_capped():
    p = HOSTILE['To with 20,000 addresses']()
    assert len(p.to) == parse.MAX_ADDRESSES and 'bounded' in p.flags
    p = HOSTILE['References with 60,000 ids']()
    assert len(p.references) <= parse.MAX_REFERENCES_TAIL + 1 and 'bounded' in p.flags
    assert p.references[0] == 'r0@x.test' and p.references[-1] == 'r59999@x.test'
    p = HOSTILE['subject of 150,000 encoded words']()
    assert 'bounded' in p.flags and len(p.subject) <= parse.MAX_SUBJECT


def test_attachment_metadata_is_stored_when_the_body_is_read(lagoon):
    mb = make_mailbox(body_mode='body')
    client = primed(mb)
    raw = (
        'From: Pat Example <pat@lagoon.test>\r\nTo: ' + SALES + '\r\nSubject: Signed contract\r\n'
        'Message-ID: <att1@lagoon.test>\r\nMIME-Version: 1.0\r\n'
        'Content-Type: multipart/mixed; boundary=XX\r\n\r\n--XX\r\nContent-Type: text/plain\r\n\r\n'
        'See attached.\r\n--XX\r\nContent-Type: application/pdf\r\n'
        'Content-Disposition: attachment; filename="signed.pdf"\r\n'
        'Content-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n--XX--\r\n'
    ).encode()
    client.add_message(eml_to_gmail(raw, 'att1', internal_date_ms=str(int(recent(2).timestamp() * 1000))))
    run(mb, client)
    message = MailMessage.objects.get()
    assert message.body_text == 'See attached.' and message.has_attachments
    assert [a['filename'] for a in message.attachments] == ['signed.pdf']


def test_bcc_is_never_stored():
    raw = build_eml([('From', SALES), ('To', 'pat@lagoon.test'), ('Bcc', 'secret@hidden.test'),
                     ('Subject', 's'), ('Message-ID', '<bcc@x.test>')])
    p = parse.parse_gmail_message(eml_to_gmail(raw, 'g', label_ids=['SENT']))
    assert 'secret@hidden.test' not in [a.address for _, a in p.participants()]


# --- 5. Gmail's clock -----------------------------------------------------------------

def test_future_dated_unmatched_mail_expires_from_gmails_clock(capture_on):
    mb = make_mailbox()
    client = primed(mb)
    message = gmail_message('u1', 'Stranger <who@unknown-co.test>', [SALES], subject='Private matter',
                            date=datetime(2099, 1, 1, tzinfo=dt_timezone.utc))
    received = recent(1)
    message['internalDate'] = str(int(received.timestamp() * 1000))
    client.add_message(message)
    run(mb, client)
    row = UnmatchedSender.objects.get()
    assert row.last_seen == received and row.expires_at == received + timedelta(days=30)


def test_future_dated_inbound_does_not_pin_the_clock(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    first = inbound('f1', when=datetime(2099, 1, 1, tzinfo=dt_timezone.utc), message_id='<root-f@lagoon.test>')
    received = recent(3)
    first['internalDate'] = str(int(received.timestamp() * 1000))
    client.add_message(first)
    client.add_message(gmail_message('f2', f'Sales <{SALES}>', ['pat@lagoon.test'], labels=('SENT',),
                                     subject='Re: Synthetic subject', date=recent(1),
                                     in_reply_to='<root-f@lagoon.test>', references='<root-f@lagoon.test>'))
    run(mb, client)
    conv = MailConversation.objects.get()
    assert conv.last_inbound_at == received and conv.last_outbound_at > conv.last_inbound_at
    message = MailMessage.objects.get(rfc_message_id='root-f@lagoon.test')
    assert message.sent_at == received and message.claimed_date.year == 2099
    assert 'date_mismatch' in message.flags


# --- 6. direction and identity ------------------------------------------------------------

def test_forged_internal_from_is_not_outbound_and_links_no_email_log(lagoon):
    victim = make_company('Victim Test Company')
    log = EmailLog.objects.create(company=victim, email_type='manual', from_email=SALES,
                                  to_email='who@stranger.test', subject='x', status='sent',
                                  body_html='', body_text='')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(gmail_message('s1', f'Sales <{SALES}>', ['who@stranger.test', 'pat@lagoon.test'],
                                     subject='hello', date=recent(1),
                                     extra=[('X-BMAsia-Email-ID', str(log.pk))], labels=('INBOX',)))
    run(mb, client)
    message = MailMessage.objects.get()
    assert message.direction == 'claimed_internal' and message.email_log_id is None
    conv = message.conversation
    assert conv.last_outbound_at is None and conv.last_inbound_at is None


def test_crm_header_needs_the_logs_recipient(lagoon):
    victim = make_company('Victim Test Company')
    log = EmailLog.objects.create(company=victim, email_type='manual', from_email=SALES,
                                  to_email='buyer@victim.test', subject='x', status='sent',
                                  body_html='', body_text='')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(gmail_message('o1', f'Sales <{SALES}>', ['pat@lagoon.test'], subject='hello',
                                     date=recent(1), extra=[('X-BMAsia-Email-ID', str(log.pk))],
                                     labels=('SENT',)))
    run(mb, client)
    message = MailMessage.objects.get()
    assert message.direction == 'outbound' and message.email_log_id is None
    assert not MailMatch.objects.filter(target_id=str(victim.pk)).exists()


def test_a_later_sent_copy_makes_the_message_outbound(lagoon):
    a, b = make_mailbox(SALES), make_mailbox(OPS)
    ca, cb = primed(a), primed(b)
    shared = dict(message_id='<late@ourco.example>', date=recent(2))
    ca.add_message(gmail_message('a1', f'Ops <{OPS}>', ['pat@lagoon.test', SALES], labels=('INBOX',), **shared))
    cb.add_message(gmail_message('b1', f'Ops <{OPS}>', ['pat@lagoon.test', SALES], labels=('SENT',), **shared))
    run(a, ca)
    assert MailMessage.objects.get().direction == 'claimed_internal'
    run(b, cb)
    message = MailMessage.objects.get()
    assert message.direction == 'outbound'
    assert message.conversation.last_outbound_at is not None


def test_sender_is_the_angle_address_not_the_display_name(lagoon):
    p = parse.parse_address_list('evil@x.test <real@y.test>')
    assert [(a.address, a.display_name) for a in p] == [('real@y.test', 'evil@x.test')]
    assert parse.parse_address_list('a@x.test.')[0].address == 'a@x.test'
    nested = '=?utf-8?b?PT91dGYtOD9xP25lc3RlZD89?= <n@x.test>'   # decodes to an encoded word
    assert parse.parse_address_list(nested)[0].display_name == '=?utf-8?q?nested?='
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(raw_message('e1', [('From', 'pat@lagoon.test <stranger@elsewhere.test>'),
                                          ('To', SALES), ('Message-ID', '<e1@x.test>')], recent(1)))
    run(mb, client)
    assert UnmatchedSender.objects.get().address == 'stranger@elsewhere.test'
    assert MailMessage.objects.count() == 0      # not matched to the contact pat@


def test_idn_domains_are_compared_as_ascii():
    [a] = parse.parse_address_list('user@bücher.example')
    assert a.domain == 'xn--bcher-kva.example'


# --- 11. cursor, budget, synthetic ids, freemail -----------------------------------------------

def test_incremental_max_messages_never_skips_mail(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    for i in range(5):
        client.add_message(inbound(f'm{i}', message_id=f'<m{i}@lagoon.test>'))
    first = run(mb, client, max_messages=2)
    assert first.outcome == 'partial' and first.counts['stored'] == 2
    second = run(mb, client)
    assert second.outcome == 'ok'
    assert MailMessage.objects.count() == 5


def test_a_small_budget_still_makes_progress(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    for i in range(10):
        client.add_message(inbound(f'b{i}', message_id=f'<b{i}@lagoon.test>'))
    outcomes = []
    for _ in range(6):
        result = run(mb, client, max_quota_units=100)
        outcomes.append(result.outcome)
        if result.outcome == 'ok':
            break
    assert outcomes[0] == 'partial' and outcomes[-1] == 'ok'
    assert MailMessage.objects.count() == 10


def test_synthetic_ids_do_not_collide_for_different_messages(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    for gid, hours in (('n1', 2), ('n2', 1)):
        client.add_message(gmail_message(gid, 'Pat Example <pat@lagoon.test>', [SALES], subject='Invoice',
                                         message_id=False, date=recent(hours), omit=('Date',)))
    run(mb, client)
    assert MailMessage.objects.count() == 2


def test_synthetic_id_is_the_same_in_two_mailboxes(lagoon):
    a, b = make_mailbox(SALES), make_mailbox(OPS)
    ca, cb = primed(a), primed(b)
    when = recent(2).replace(second=5)
    for c, gid in ((ca, 'a1'), (cb, 'b1')):
        c.add_message(gmail_message(gid, 'Pat Example <pat@lagoon.test>', [SALES, OPS], subject='Invoice',
                                    message_id=False, date=when))
    run(a, ca)
    run(b, cb)
    assert MailMessage.objects.count() == 1 and MailboxCopy.objects.count() == 2


def test_malformed_message_ids_do_not_collide():
    one, two = parse.normalise_message_id('<a b@x.test>'), parse.normalise_message_id('<a c@x.test>')
    assert one != two and one.startswith('raw:')


def test_regional_and_configured_freemail(capture_on, settings):
    from mail_capture import rules
    assert rules.is_freemail('foxmail.com') and rules.is_freemail('yahoo.com.tw')
    settings.CAPTURE_EXTRA_FREEMAIL_DOMAINS = ['webmail.example']
    assert rules.is_freemail('webmail.example')


def test_internal_domain_that_is_freemail_disables_capture(settings):
    settings.GOOGLE_CAPTURE_ENABLED = True
    settings.CAPTURE_INTERNAL_DOMAINS = ['gmail.com']
    mb = make_mailbox()
    result = sync_mailbox(mb.pk, lambda m: (_ for _ in ()).throw(AssertionError('client')))
    assert result.outcome == 'disabled' and 'freemail' in result.reason


# --- 12. thread hijack and the shared identity ------------------------------------------------

def test_forward_to_an_outsider_on_a_confirmed_thread_is_only_proposed(lagoon):
    company, _ = lagoon
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('t1', message_id='<root-t@lagoon.test>', subject='Renewal 2099'))
    run(mb, client)
    MailConversation.objects.update(link_state='confirmed', company=company)
    client.add_message(gmail_message('t3', 'Lawyer <lawyer@other-firm.test>', [SALES],
                                     subject='Re: Fwd: Renewal 2099', date=recent(0),
                                     references='<root-t@lagoon.test> <t2@mail.example.org>'))
    run(mb, client)
    outsider = MailMessage.objects.get(from_address='lawyer@other-firm.test')
    links = list(MailMatch.objects.filter(message=outsider).values_list('method', 'status', 'confidence'))
    assert links == [('thread', 'proposed', 'low')]


def test_another_customer_in_a_confirmed_thread_marks_it_mixed(lagoon):
    company, _ = lagoon
    other = make_company('Harbour Test Resort')
    make_contact(other, 'sam@harbour.test')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('c1', message_id='<root-c@lagoon.test>'))
    run(mb, client)
    MailConversation.objects.update(link_state='confirmed', company=company)
    client.add_message(gmail_message('c2', 'Sam <sam@harbour.test>', [SALES], subject='Re: Synthetic subject',
                                     date=recent(1), references='<root-c@lagoon.test>'))
    run(mb, client)
    conv = MailConversation.objects.get()
    assert conv.is_mixed and conv.company == company and conv.link_state == 'confirmed'
    msg = MailMessage.objects.get(from_address='sam@harbour.test')
    assert MailMatch.objects.filter(message=msg, target_id=str(other.pk), status='auto').exists()


@pytest.mark.parametrize('raw, ref', [
    ('<AbC@Mail.Example.org>', 'AbC@Mail.Example.org'),
    ('\r\n  <x1@mail.example.org> (comment)', 'x1@mail.example.org'),
    ('plain@x.test', 'plain@x.test'),
    ('', ''),
])
def test_canonical_source_ref(raw, ref):
    assert canonical_source_ref(raw) == ref
    assert canonical_source_ref(canonical_source_ref(raw)) == canonical_source_ref(raw)


def test_canonical_source_ref_of_malformed_and_long_ids_is_stable():
    bad = canonical_source_ref('<a b@x.test>')
    assert bad.startswith('raw:') and canonical_source_ref(bad) == bad
    long = canonical_source_ref('<' + 'a' * 600 + '@x.test>')
    assert long.startswith('long:') and canonical_source_ref(long) == long


def test_stored_message_id_equals_the_canonical_ref(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('g1', message_id='  <Case.Kept@Lagoon.test>'))
    run(mb, client)
    assert MailMessage.objects.get().rfc_message_id == canonical_source_ref('<Case.Kept@Lagoon.test>')


# --- 8. who can see and change capture --------------------------------------------------------

def test_staff_without_superuser_sees_nothing(client, lagoon):
    mb = make_mailbox()
    c = primed(mb)
    c.add_message(inbound('a1', subject='Personal and confidential'))
    run(mb, c)
    staff = User.objects.create_user('staff-probe', 'staff@ourco.example', 'pw-probe-1', is_staff=True)
    for codename in ('view_mailmessage', 'view_unmatchedsender', 'change_capturemailbox'):
        staff.user_permissions.add(Permission.objects.get(codename=codename))
    client.force_login(staff)
    assert client.get('/admin/mail_capture/mailmessage/').status_code == 403
    assert client.get(f'/admin/mail_capture/capturemailbox/{mb.pk}/change/').status_code == 403
    assert 'mail_capture' not in client.get('/admin/').content.decode()


def test_mailbox_changes_are_logged_and_the_address_is_fixed(admin_client, capture_on):
    response = admin_client.post('/admin/mail_capture/capturemailbox/add/', {
        'email': 'new@ourco.example', 'kind': 'person', 'body_mode': 'headers', 'visibility': 'owner',
    })
    assert response.status_code == 302
    mb = CaptureMailbox.objects.get()
    response = admin_client.post(f'/admin/mail_capture/capturemailbox/{mb.pk}/change/', {
        'email': 'moved@ourco.example', 'kind': 'person', 'enabled': 'on', 'body_mode': 'body',
        'visibility': 'owner',
    })
    assert response.status_code == 302
    mb.refresh_from_db()
    assert mb.email == 'new@ourco.example' and mb.enabled and mb.body_mode == 'body'
    rows = list(MailboxAccessLog.objects.filter(purpose='config').order_by('at', 'pk')
                .values_list('detail', flat=True))
    changes = [r for r in rows if r['old'] is not None or r['field'] in ('enabled', 'body_mode')]
    assert {'field': 'enabled', 'old': False, 'new': True} in changes
    assert {'field': 'body_mode', 'old': 'headers', 'new': 'body'} in changes
    assert all(r.startswith('user:') for r in MailboxAccessLog.objects.values_list('actor', flat=True))


# --- 10. the access-log row exists before the first read ---------------------------------------

def test_access_log_row_is_written_before_the_first_gmail_call(lagoon):
    mb = make_mailbox()
    seen = {}

    class Watching(FakeGmailClient):
        def list_labels(self):
            seen['rows'] = list(MailboxAccessLog.objects.values_list('finished_at', flat=True))
            return super().list_labels()

    client = Watching(mb.email)
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=client.history_id)
    run(mb, client)
    assert seen['rows'] == [None]
    row = MailboxAccessLog.objects.get()
    assert row.finished_at is not None and row.api_calls == len(client.calls)


# --- 13. tests the mutation pass asked for --------------------------------------------------------

def test_lease_token_is_checked_before_writing(lagoon):
    mb = make_mailbox()

    class Stealing(FakeGmailClient):
        def get_message(self, *args, **kwargs):
            CaptureMailbox.objects.filter(pk=mb.pk).update(lease_token='someone-else')
            return super().get_message(*args, **kwargs)

    client = Stealing(mb.email)
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=client.history_id)
    start = client.history_id
    client.add_message(inbound('g1'))
    result = run(mb, client)
    mb.refresh_from_db()
    assert result.outcome == 'busy' and mb.history_id == start and MailMessage.objects.count() == 0
    assert mb.lease_token == 'someone-else'     # never released by the loser


def test_skip_beats_headers_only(lagoon):
    CaptureRule.objects.create(kind='domain', value='lagoon.test', action='headers_only')
    CaptureRule.objects.create(kind='address', value='pat@lagoon.test', action='skip')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('g1'))
    assert run(mb, client).counts['skipped_by_rule'] == 1


def test_queue_keeps_three_subjects_and_respects_never_log(capture_on):
    mb = make_mailbox()
    client = primed(mb)
    for i in range(5):
        client.add_message(gmail_message(f'u{i}', 'x@unknown.test', [SALES], subject=f'Subject {i}',
                                         date=recent(5 - i), message_id=f'<u{i}@x.test>'))
    run(mb, client)
    row = UnmatchedSender.objects.get()
    assert row.message_count == 5 and len(row.samples) == 3
    UnmatchedSender.objects.update(status='never_log')
    client.add_message(gmail_message('u9', 'x@unknown.test', [SALES], subject='More', date=recent(0),
                                     message_id='<u9@x.test>'))
    run(mb, client)
    assert UnmatchedSender.objects.get().message_count == 5


def test_ambiguous_mail_gets_no_body(capture_on):
    one, two = make_company('Twin Record One'), make_company('Twin Record Two')
    make_contact(one, 'owner@twins.test')
    make_contact(two, 'owner@twins.test')
    mb = make_mailbox(body_mode='body')
    client = primed(mb)
    client.add_message(inbound('g1', frm='owner@twins.test', body='Secret body.\n'))
    run(mb, client)
    assert MailMessage.objects.get().body_text is None
    assert not [c for c in client.calls if c[1].get('format') == 'full']


def test_fake_only_refuses_before_calling_a_real_factory(settings):
    settings.GOOGLE_CAPTURE_ENABLED = False
    settings.CAPTURE_INTERNAL_DOMAINS = ['ourco.example']
    mb = make_mailbox()
    made = []

    def real_factory(mailbox):
        made.append(mailbox.email)
        return FakeGmailClient(mailbox.email)

    with pytest.raises(CaptureRefused):
        sync_mailbox(mb.pk, real_factory, fake_only=True)
    assert made == []
    with pytest.raises(TypeError):
        fake_factory([object()])


def test_selfcheck_ignores_real_rules(settings):
    settings.GOOGLE_CAPTURE_ENABLED = False
    CaptureRule.objects.create(kind='domain', value='selfcheck-lagoon.test', action='skip')
    out = StringIO()
    call_command('mail_capture_selfcheck', stdout=out)
    assert 'pipeline: OK' in out.getvalue()


def test_company_domain_freemail_refused_on_every_path(capture_on):
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        CompanyDomain.objects.create(company=make_company('Fox Test'), domain='foxmail.com')
