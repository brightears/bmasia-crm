"""The first supervised run as the runbook describes it, and the follow-ups of
the first-run review: temporary failures, auth refusals, --skip-once, label
rules that grow after their preview, and the pacer. Fake transports only."""
import threading
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from mail_capture import purge, sync
from mail_capture.gmail_client import FakeGmailClient
from mail_capture.models import (
    CaptureFailure, CaptureMailbox, CaptureRule, CaptureRun, CaptureSkip, MailboxAccessLog, MailboxCopy,
    MailMessage,
)
from mail_capture.sync import sync_mailbox

from .builders import SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent


pytestmark = pytest.mark.django_db
TEST_MAILBOX = 'test-mailbox@example.com'
RUNBOOK = Path(__file__).resolve().parents[1] / 'RUNBOOK.md'


def run(mailbox, client, **kwargs):
    kwargs.setdefault('sleep', lambda s: None)
    return sync_mailbox(mailbox.pk, factory_for(client), **kwargs)


def inbound(gid, to=(SALES,), **kwargs):
    kwargs.setdefault('date', recent(5))
    kwargs.setdefault('message_id', f'<{gid}@lagoon.test>')
    return gmail_message(gid, 'Pat Example <pat@lagoon.test>', list(to), **kwargs)


@pytest.fixture
def lagoon(capture_on):
    company = make_company('Lagoon Test Hotel')
    return company, make_contact(company, 'pat@lagoon.test', 'Pat Example')


@pytest.fixture
def switched_on(capture_on):
    capture_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'key_file'
    capture_on.GOOGLE_CAPTURE_KEY_FILE = '/nonexistent/synthetic.json'
    capture_on.GOOGLE_CAPTURE_SCOPE = 'metadata'
    capture_on.GOOGLE_CAPTURE_NEVER_MAILBOXES = []
    return capture_on


def gmail_sync(*args):
    out, err = StringIO(), StringIO()
    try:
        call_command('gmail_sync', *args, stdout=out, stderr=err)
        code = 0
    except SystemExit as exc:
        code = exc.code
    return code, out.getvalue() + err.getvalue()


def use_client(monkeypatch, client):
    monkeypatch.setattr('mail_capture.google_client.client_for', lambda m: client, raising=False)


# --- G1: the runbook's sequence, end to end ------------------------------------------------

def test_runbook_first_supervised_run_sequence(switched_on, lagoon, monkeypatch):
    """Runbook section 1, step by step, with the commands exactly as written
    there (the test also checks the runbook still says them)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    text = RUNBOOK.read_text('utf-8')
    commands = [
        f'python manage.py gmail_sync --check --mailbox {TEST_MAILBOX}',
        f'python manage.py gmail_sync --backfill --since <yesterday> --dry-run --max-messages 20 '
        f'--mailbox {TEST_MAILBOX}',
        f'python manage.py gmail_sync --backfill --since <yesterday> --max-messages 20 --mailbox {TEST_MAILBOX}',
        f'python manage.py gmail_sync --incremental --mailbox {TEST_MAILBOX}',
    ]
    for command in commands:
        assert command in text, command
    assert f'enabled mailboxes: {TEST_MAILBOX}' in text

    def args(command):
        return command.replace('<yesterday>', yesterday).split()[3:]

    mailbox = make_mailbox(TEST_MAILBOX)
    client = FakeGmailClient(TEST_MAILBOX)
    client.add_message(inbound('t1', to=[TEST_MAILBOX]))          # the test mail, sent before step 1
    use_client(monkeypatch, client)

    # Step 1: --check. Only the test mailbox is enabled; 1 unit; nothing stored.
    code, out = gmail_sync(*args(commands[0]))
    lines = out.splitlines()
    assert code == 0 and lines[0] == f'enabled mailboxes: {TEST_MAILBOX}'
    assert lines[1] == f'{TEST_MAILBOX}: messages 1, history id {client.history_id}'
    assert MailboxAccessLog.objects.get().purpose == 'check'

    # Step 2: the backfill dry run shows what would be read, and stores no mail.
    code, out = gmail_sync(*args(commands[1]))
    assert code == 0 and f'{TEST_MAILBOX}: ok' in out and 'fetched=1' in out and 'matched=1' in out
    assert MailMessage.objects.count() == 0
    log = MailboxAccessLog.objects.get(dry_run=True)
    assert log.purpose == 'backfill' and log.messages_read == 1 and log.finished_at is not None
    run_row = CaptureRun.objects.get(dry_run=True)
    assert run_row.outcome == 'ok' and run_row.fetched == 1 and run_row.error_summary == ''
    mailbox.refresh_from_db()
    assert mailbox.last_error == '' and mailbox.history_id == ''

    # Step 3: the same without --dry-run stores the test mail and sets the starting point.
    code, out = gmail_sync(*args(commands[2]))
    assert code == 0 and 'stored=1' in out
    assert list(MailMessage.objects.values_list('rfc_message_id', flat=True)) == ['t1@lagoon.test']
    mailbox.refresh_from_db()
    assert mailbox.history_id and mailbox.last_error == '' and mailbox.consecutive_errors == 0

    # Step 4: send a second test mail, then one incremental run reads it.
    client.add_message(inbound('t2', to=[TEST_MAILBOX]))
    code, out = gmail_sync(*args(commands[3]))
    assert code == 0 and 'stored=1' in out and MailMessage.objects.count() == 2

    # A second run on the same mailbox while one is running exits 7.
    CaptureMailbox.objects.filter(pk=mailbox.pk).update(
        lease_token='another-run', lease_expires_at=timezone.now() + timedelta(minutes=5))
    code, out = gmail_sync(*args(commands[3]))
    assert code == 7 and 'busy' in out


def test_a_dry_run_never_sets_the_starting_point(lagoon):
    """Why the runbook uses a backfill dry run: an incremental dry run on a new
    mailbox saves nothing, so a second one would count nothing either."""
    mb = make_mailbox()
    client = FakeGmailClient(mb.email)
    run(mb, client, dry_run=True)
    client.add_message(inbound('t1'))
    assert not run(mb, client, dry_run=True).counts.get('fetched')
    mb.refresh_from_db()
    assert mb.history_id == ''


def test_reading_forms_need_a_mailbox_or_all_mailboxes(switched_on, lagoon, monkeypatch):
    mb = make_mailbox()
    make_mailbox('ops@ourco.example')
    client = primed(mb)
    use_client(monkeypatch, client)
    for form in (('--check',), ('--incremental',), ('--incremental', '--dry-run')):
        code, out = gmail_sync(*form)
        assert code == 2 and 'name one mailbox with --mailbox' in out
    assert client.calls == []
    assert gmail_sync('--incremental', '--mailbox', SALES, '--all-mailboxes')[0] == 2
    code, out = gmail_sync('--check', '--mailbox', SALES)
    assert out.splitlines()[0] == 'enabled mailboxes: ops@ourco.example, sales@ourco.example'
    assert len([c for c in client.calls if c[0] == 'get_profile']) == 1     # only the named one is read


def test_the_runbook_covers_the_corrections():
    text = RUNBOOK.read_text('utf-8')
    first = text.index('## ')
    assert text[first:].startswith('## How to stop')
    for phrase in ('capture service', 'never the web service', 'Always pass `--mailbox`',
                   'GOOGLE_CAPTURE_NEVER_MAILBOXES', 'skips the message for good', 'exits 7',
                   'address rule', '--all-mailboxes'):
        assert phrase in text, phrase
    order = [text.index(f'`{name}`', text.index('Settings, in this order'))
             for name in ('GOOGLE_CAPTURE_NEVER_MAILBOXES', 'GOOGLE_CAPTURE_CREDENTIALS_MODE',
                          'CAPTURE_INTERNAL_DOMAINS', 'GOOGLE_CAPTURE_ENABLED')]
    assert order == sorted(order)


# --- G2: temporary failures back off; refusals show but do not stop the mailbox -----------

def _expire_backoff(mb):
    CaptureMailbox.objects.filter(pk=mb.pk).update(retry_not_before=timezone.now() - timedelta(seconds=1))


def test_rate_limits_back_off_and_do_not_need_attention(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('r1'))
    client.fail('list_history', 429, times=100)
    first = run(mb, client)
    mb.refresh_from_db()
    assert first.outcome == 'rate_limited' and mb.retry_not_before is not None
    calls = len(client.calls)
    for _ in range(3):
        assert run(mb, client).outcome == 'deferred'        # backing off: no Gmail call
    assert len(client.calls) == calls
    waits = []
    for _ in range(5):
        _expire_backoff(mb)
        before = timezone.now()
        assert run(mb, client).outcome == 'rate_limited'
        mb.refresh_from_db()
        waits.append(round((mb.retry_not_before - before).total_seconds() / 60))
    assert waits == [2, 4, 8, 16, 32] and not mb.needs_attention and mb.attention_errors == 0


def test_a_gmail_outage_is_temporary_too(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.fail('list_history', 503, times=100)
    outcomes = []
    for _ in range(5):
        _expire_backoff(mb)
        outcomes.append(run(mb, client).outcome)
    mb.refresh_from_db()
    assert outcomes == ['unavailable'] * 5 and not mb.needs_attention and mb.transient_errors == 5


def test_hours_of_nothing_but_temporary_failures_need_attention(lagoon, settings):
    settings.CAPTURE_TRANSIENT_ATTENTION_HOURS = 24
    mb = make_mailbox()
    client = primed(mb)
    client.fail('list_history', 429, times=100)
    run(mb, client)
    CaptureMailbox.objects.filter(pk=mb.pk).update(transient_since=timezone.now() - timedelta(hours=25))
    _expire_backoff(mb)
    run(mb, client)
    mb.refresh_from_db()
    assert mb.needs_attention and mb.attention_reason.startswith('only temporary failures for 24 hours')
    assert 'rate limited' in mb.attention_reason


def test_retry_after_sets_the_next_run(lagoon):
    mb = make_mailbox()
    client = batch_client(mb, 2)
    client.fail_item('m1', 429, times=99, retry_after=240)
    before = timezone.now()
    assert run(mb, client).outcome == 'rate_limited'
    mb.refresh_from_db()
    assert (mb.retry_not_before - before).total_seconds() >= 239


def test_a_success_clears_the_temporary_state(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.fail('list_history', 503, times=4)
    run(mb, client)
    _expire_backoff(mb)
    assert run(mb, client).outcome == 'ok'
    mb.refresh_from_db()
    assert (mb.transient_errors, mb.transient_since, mb.retry_not_before, mb.consecutive_errors) == (0, None, None, 0)


def test_code_errors_still_need_attention_after_three(lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad'))

    def broken(self, plan, now, queue_ops):
        raise TypeError('synthetic')
    monkeypatch.setattr(sync._Runner, '_store', broken)
    for _ in range(3):
        with pytest.raises(TypeError):
            run(mb, client)
    mb.refresh_from_db()
    assert mb.needs_attention and mb.attention_errors == 3 and mb.retry_not_before is None


def test_a_refused_token_shows_at_once_and_the_next_good_token_clears_it(switched_on, lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    use_client(monkeypatch, client)
    client.fail('list_labels', 403, times=5, reason='insufficientPermissions')
    for _ in range(5):
        assert run(mb, client).outcome == 'auth_error'          # never deferred, never needs attention
    mb.refresh_from_db()
    assert mb.auth_problem.startswith('auth permission_denied') and not mb.needs_attention
    assert mb.retry_not_before is None
    client.fail('get_profile', 403, times=1, reason='insufficientPermissions')
    code, out = gmail_sync('--check', '--mailbox', SALES)
    assert code == 3 and 'auth_error permission_denied' in out
    # The operator fixes the setup: the next check makes a token and clears it, no --clear-attention.
    code, out = gmail_sync('--check', '--mailbox', SALES)
    assert code == 0
    mb.refresh_from_db()
    assert mb.auth_problem == ''
    client.fail('list_labels', 401, times=1)
    run(mb, client)
    mb.refresh_from_db()
    assert mb.auth_problem.startswith('auth gmail_unauthorized')
    assert run(mb, client).outcome == 'ok'
    mb.refresh_from_db()
    assert mb.auth_problem == ''


def test_exit_4_covers_unavailable_and_deferred(switched_on, lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    use_client(monkeypatch, client)
    monkeypatch.setattr(sync.time, 'sleep', lambda s: None)
    client.fail('list_history', 503, times=100)
    code, out = gmail_sync('--incremental', '--mailbox', SALES)
    assert code == 4 and 'unavailable' in out
    code, out = gmail_sync('--incremental', '--mailbox', SALES)
    assert code == 4 and 'deferred' in out
    code, out = gmail_sync('--check', '--mailbox', SALES)
    assert 'runs back off until' in out


# --- G3: --skip-once needs a recorded failure, or --force -----------------------------------

def test_skip_once_refuses_an_id_that_never_failed(switched_on, lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('innocent'))
    code, out = gmail_sync('--skip-once', 'innocent', '--mailbox', SALES, '--by', 'Test Operator',
                           '--reason', 'testing')
    assert code == 2 and 'has no recorded failure' in out and '--force' in out
    assert CaptureSkip.objects.count() == 0
    run(mb, client)
    assert MailMessage.objects.count() == 1


def test_skip_once_with_force_is_recorded(switched_on, lagoon):
    mb = make_mailbox()
    code, out = gmail_sync('--skip-once', 'odd1', '--mailbox', SALES, '--by', 'Test Operator',
                           '--reason', 'known bad', '--force')
    assert code == 0 and 'forced' in out
    skip = CaptureSkip.objects.get()
    assert skip.forced and skip.reason == 'known bad' and skip.mailbox == mb


def test_skip_once_accepts_a_recorded_failure_or_the_last_failed_run(switched_on, lagoon):
    mb = make_mailbox()
    now = timezone.now()
    CaptureFailure.objects.create(mailbox=mb, gmail_id='f1', error='gmail 400', first_failed_at=now,
                                  last_failed_at=now)
    CaptureRun.objects.create(mailbox=mb, kind='incremental', started_at=now, outcome='error',
                              error_gmail_id='r1', error_class='TypeError')
    for gid in ('f1', 'r1'):
        assert gmail_sync('--skip-once', gid, '--mailbox', SALES, '--by', 'T', '--reason', 'x')[0] == 0
    assert set(CaptureSkip.objects.values_list('gmail_id', 'forced')) == {('f1', False), ('r1', False)}


# --- label rules that grow after their preview ------------------------------------------------

LABEL = {'id': 'Label_3', 'name': 'Clients', 'type': 'user'}


def _labelled_mailbox():
    mb = make_mailbox()
    client = primed(mb, labels=[LABEL])
    client.add_message(inbound('l0', labels=('INBOX', 'Label_3')))
    client.add_message(inbound('l1'))
    client.add_message(inbound('l2'))
    run(mb, client)
    return mb, client


def _form(page):
    import re
    return dict(re.findall(r'<input type="hidden" name="(fingerprint|previewed)" value="([^"]*)"', page),
                confirm='yes')


def test_a_label_rule_purges_only_what_its_preview_showed(lagoon, admin_client):
    mb, client = _labelled_mailbox()
    rule = CaptureRule(kind='label', value='Clients', action='skip')
    rule.full_clean()
    rule.save()
    run(mb, client)                                            # records the label ids for the preview
    url = f'/admin/mail_capture/capturerule/{rule.pk}/confirm-purge/'
    page = admin_client.get(url).content.decode()
    assert 'Messages purged: <strong>1</strong>' in page
    client.add_labels('l1', ['Label_3'])                       # labelled after the preview
    client.add_labels('l2', ['Label_3'])
    run(mb, client)                                            # not confirmed yet: nothing goes
    assert MailMessage.objects.count() == 3
    response = admin_client.post(url, _form(page), follow=True)
    assert '2 more messages carry this label since the preview: preview again to purge them' in \
        response.content.decode()
    run(mb, client)
    assert sorted(MailMessage.objects.values_list('rfc_message_id', flat=True)) == ['l1@lagoon.test',
                                                                                    'l2@lagoon.test']
    rule.refresh_from_db()
    assert purge.label_rule_pending(rule) == 2
    # A new preview shows the two; confirming it purges them.
    page = admin_client.get(url).content.decode()
    assert 'Messages purged: <strong>2</strong>' in page
    admin_client.post(url, _form(page))
    run(mb, client)
    assert MailMessage.objects.count() == 0


def test_a_label_rule_still_blocks_new_capture_from_the_moment_it_is_saved(lagoon):
    mb = make_mailbox()
    client = primed(mb, labels=[LABEL])
    CaptureRule.objects.create(kind='label', value='Clients', action='skip')
    client.add_message(inbound('n1', labels=('INBOX', 'Label_3')))
    assert run(mb, client).counts['skipped_by_rule'] == 1 and MailMessage.objects.count() == 0


def test_a_stale_label_preview_cannot_be_confirmed(lagoon):
    mb, client = _labelled_mailbox()
    rule = CaptureRule.objects.create(kind='label', value='Clients', action='skip')
    run(mb, client)
    purge.store_label_preview(rule)
    rule.refresh_from_db()
    snap = dict(rule.preview_snapshot, at=(timezone.now() - timedelta(minutes=61)).isoformat())
    CaptureRule.objects.filter(pk=rule.pk).update(preview_snapshot=snap)
    with pytest.raises(purge.RuleChanged, match='more than 60 minutes old'):
        purge.confirm_rule(rule, expected_fingerprint=rule.fingerprint())
    CaptureRule.objects.filter(pk=rule.pk).update(preview_snapshot={})
    with pytest.raises(purge.RuleChanged):                     # no preview at all
        purge.confirm_rule(rule, expected_fingerprint=rule.fingerprint())


def test_the_built_in_private_label_is_still_immediate(lagoon):
    private = {'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}
    mb = make_mailbox()
    client = primed(mb, labels=[private])
    client.add_message(inbound('p1'))
    run(mb, client)
    client.add_labels('p1', ['Label_9'])
    run(mb, client)
    assert MailMessage.objects.count() == 0 and MailboxCopy.objects.count() == 0


# --- G4: the engine paces every Gmail call; the confirm row lock ------------------------------

class SpyPacer:
    def __init__(self):
        self.units = []

    def acquire(self, units, sleep):
        self.units.append(units)

    def drain(self):
        pass


def batch_client(mb, count):
    client = FakeGmailClient(mb.email, batch=True)
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=client.history_id)
    for i in range(count):
        client.add_message(inbound(f'm{i}'))
    return client


@pytest.mark.parametrize('batch', [False, True])
def test_the_engine_paces_every_gmail_call(lagoon, batch):
    mb = make_mailbox()
    client = FakeGmailClient(mb.email, batch=batch)
    client.add_message(inbound('old', date=recent(30)))
    spy = SpyPacer()
    client.pacer = spy
    result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=5))
    client.add_message(inbound('new1'))
    client.add_message(inbound('new2'))
    second = run(mb, client)
    assert len(spy.units) == len(client.calls) > 4
    assert sum(spy.units) == result.counts['quota_units'] + second.counts['quota_units']


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='row locks need Postgres')
def test_confirm_rule_waits_for_the_row_lock(capture_on):
    from django.db import connections, transaction
    rule = CaptureRule.objects.create(kind='domain', value='harbour.test', action='skip')
    fingerprint = rule.fingerprint()
    outcome = []

    def second_admin():
        try:
            purge.confirm_rule(CaptureRule.objects.get(pk=rule.pk), expected_fingerprint=fingerprint)
            outcome.append('confirmed')
        except purge.RuleChanged as exc:
            outcome.append(str(exc))
        finally:
            connections.close_all()

    with transaction.atomic():
        CaptureRule.objects.select_for_update().get(pk=rule.pk)     # the first admin holds the row
        thread = threading.Thread(target=second_admin)
        thread.start()
        thread.join(1.0)
        assert thread.is_alive() and outcome == []                 # it waits for the lock
        CaptureRule.objects.filter(pk=rule.pk).update(
            purge_state='confirmed', confirmed_fingerprint=fingerprint, confirmed_at=timezone.now())
    thread.join(10)
    assert outcome == ['this rule is already confirmed as it stands']
