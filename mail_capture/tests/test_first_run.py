"""Before the first supervised run: confirming exactly the previewed rule,
per-message Gmail failures, needs-attention, pacing and budgets, the DKIM
hint, the recipient cap, code versions and the suffix list. Engine tests use
the fake client; nothing here reaches Google."""
import logging
import re
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from mail_capture import conf, parse, purge, rules, sync
from mail_capture.gmail_client import (
    AUTH_HINTS, FakeGmailClient, GmailAuthError, GmailNotFound, GmailRateLimited,
    GmailServerError, QuotaPacer, error_for_status,
)
from mail_capture.models import (
    CaptureFailure, CaptureMailbox, CaptureRule, CaptureRun, CaptureSkip, CompanyDomain,
    MailboxAccessLog, MailMessage, UnmatchedSender,
)
from mail_capture.sync import sync_mailbox

from .builders import SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent


pytestmark = pytest.mark.django_db


def run(mailbox, client, **kwargs):
    kwargs.setdefault('sleep', lambda s: None)
    return sync_mailbox(mailbox.pk, factory_for(client), **kwargs)


def inbound(gid, **kwargs):
    kwargs.setdefault('date', recent(5))
    kwargs.setdefault('message_id', f'<{gid}@lagoon.test>')
    return gmail_message(gid, kwargs.pop('frm', 'Pat Example <pat@lagoon.test>'), kwargs.pop('to', [SALES]),
                         **kwargs)


@pytest.fixture
def lagoon(capture_on):
    company = make_company('Lagoon Test Hotel')
    return company, make_contact(company, 'pat@lagoon.test', 'Pat Example')


def batch_client(mb, count, prefix='m'):
    client = FakeGmailClient(mb.email, batch=True)
    mb.history_id = client.history_id
    mb.save(update_fields=['history_id'])
    for i in range(count):
        client.add_message(inbound(f'{prefix}{i}'))
    return client


def batches(client):
    return [kw['ids'] for name, kw in client.calls if name == 'get_messages']


# --- F1: confirm exactly the rule that was previewed -----------------------------------

def _stored_two_companies(capture_on):
    harbour = make_company('Harbour Test Hotel')
    lagoon = make_company('Lagoon Test Hotel')
    make_contact(harbour, 'kim@harbour.test')
    make_contact(lagoon, 'pat@lagoon.test')
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('h1', frm='Kim <kim@harbour.test>', message_id='<h1@harbour.test>'))
    client.add_message(inbound('l1'))
    run(mb, client)
    assert MailMessage.objects.count() == 2
    return mb, client


def _hidden(page):
    return dict(re.findall(r'<input type="hidden" name="(fingerprint|previewed)" value="([^"]*)"', page))


def test_confirm_is_refused_when_the_rule_changed_since_the_preview(capture_on, admin_client):
    _stored_two_companies(capture_on)
    response = admin_client.post('/admin/mail_capture/capturerule/add/', {
        'kind': 'domain', 'value': 'harbour.test', 'scope': 'org', 'action': 'skip', 'note': ''})
    url = response['Location']
    page = admin_client.get(url).content.decode()
    form = _hidden(page)
    rule = CaptureRule.objects.get()
    assert form['fingerprint'] == rule.fingerprint() and form['previewed'] == '1'
    # Meanwhile someone edits the rule to another domain.
    rule.value = 'lagoon.test'
    rule.save()
    response = admin_client.post(url, dict(form, confirm='yes'), follow=True)
    assert 'The rule changed since the preview: preview again' in response.content.decode()
    rule.refresh_from_db()
    assert rule.purge_state == 'awaiting_confirmation' and not rule.is_confirmed
    assert MailMessage.objects.count() == 2            # nothing purged
    # A fresh preview of the rule as it now stands can be confirmed.
    page = admin_client.get(url).content.decode()
    assert 'Messages purged: <strong>1</strong>' in page
    admin_client.post(url, dict(_hidden(page), confirm='yes'))
    assert list(MailMessage.objects.values_list('rfc_message_id', flat=True)) == ['h1@harbour.test']


def test_confirm_without_the_previewed_fingerprint_confirms_nothing(capture_on, admin_client):
    _stored_two_companies(capture_on)
    response = admin_client.post('/admin/mail_capture/capturerule/add/', {
        'kind': 'domain', 'value': 'harbour.test', 'scope': 'org', 'action': 'skip', 'note': ''})
    admin_client.post(response['Location'], {'confirm': 'yes'})
    assert CaptureRule.objects.get().purge_state == 'awaiting_confirmation'
    assert MailMessage.objects.count() == 2


def test_confirm_rule_checks_the_fingerprint_on_every_route(capture_on):
    rule = CaptureRule.objects.create(kind='domain', value='harbour.test', action='skip')
    previewed = rule.fingerprint()
    with pytest.raises(TypeError):
        purge.confirm_rule(rule)                                  # no default: every route must pass it
    for wrong in ('', 'x' * 64):
        with pytest.raises(purge.RuleChanged):
            purge.confirm_rule(rule, expected_fingerprint=wrong)
    CaptureRule.objects.filter(pk=rule.pk).update(value='lagoon.test')   # changed without save()
    with pytest.raises(purge.RuleChanged, match='preview again'):
        purge.confirm_rule(rule, expected_fingerprint=previewed)
    rule.refresh_from_db()
    assert rule.purge_state == 'awaiting_confirmation'
    purge.confirm_rule(rule, expected_fingerprint=rule.fingerprint())
    assert CaptureRule.objects.get().is_confirmed
    with pytest.raises(purge.RuleChanged):                       # already confirmed: nothing to confirm
        purge.confirm_rule(rule, expected_fingerprint=rule.fingerprint())


# --- F4: one message Gmail refuses fails that message, not the run -------------------------

def test_a_gone_item_is_skipped_and_counted(lagoon):
    mb = make_mailbox()
    client = batch_client(mb, 4)
    client.fail_item('m1', 410)
    client.fail_item('m2', 404)
    result = run(mb, client)
    assert result.outcome == 'ok' and result.counts['gone'] == 2 and result.counts['stored'] == 2
    assert CaptureRun.objects.get().gone == 2
    mb.refresh_from_db()
    assert mb.history_id == client.history_id and CaptureFailure.objects.count() == 0


def test_a_400_item_fails_that_message_and_the_cursor_moves_on(lagoon):
    mb = make_mailbox()
    client = batch_client(mb, 5)
    client.fail_item('m2', 400, times=99, reason='invalidArgument')
    result = run(mb, client)
    assert result.outcome == 'ok_with_failures' and result.counts['stored'] == 4
    assert batches(client) == [['m0', 'm1', 'm2', 'm3', 'm4']]       # a 400 is never retried
    failure = CaptureFailure.objects.get()
    assert failure.gmail_id == 'm2' and failure.error == 'gmail 400 invalidArgument'
    assert CaptureRun.objects.get().failed_gmail_ids == ['m2']
    mb.refresh_from_db()
    assert mb.history_id == client.history_id
    # Retried on later runs, then parked.
    run(mb, client)
    run(mb, client)
    failure.refresh_from_db()
    assert failure.parked and failure.attempts == 3


def test_a_repeated_5xx_on_one_item_retries_only_that_item_then_fails_it(lagoon, no_sleep):
    mb = make_mailbox()
    client = batch_client(mb, 5)
    client.fail_item('m3', 500, times=99, reason='backendError')
    result = run(mb, client, sleep=no_sleep)
    assert batches(client) == [['m0', 'm1', 'm2', 'm3', 'm4'], ['m3'], ['m3'], ['m3']]
    assert result.outcome == 'ok_with_failures' and result.counts['stored'] == 4
    assert CaptureFailure.objects.get().gmail_id == 'm3'
    assert len(no_sleep.delays) == 3 and max(no_sleep.delays) <= 4.0


def test_a_rate_limited_item_is_retried_alone_honouring_retry_after(lagoon, no_sleep):
    mb = make_mailbox()
    client = batch_client(mb, 5)
    client.fail_item('m1', 429, times=1, retry_after=7.0)
    client.fail_item('m4', 403, times=1, reason='userRateLimitExceeded')
    result = run(mb, client, sleep=no_sleep)
    assert batches(client) == [['m0', 'm1', 'm2', 'm3', 'm4'], ['m1', 'm4']]
    assert no_sleep.delays == [7.0]
    assert result.outcome == 'ok' and result.counts['stored'] == 5


def test_a_rate_limit_that_persists_keeps_the_progress_and_ends_rate_limited(lagoon, no_sleep):
    mb = make_mailbox()
    client = batch_client(mb, 5)
    start = int(mb.history_id)
    client.fail_item('m3', 429, times=99)
    result = run(mb, client, sleep=no_sleep)
    assert result.outcome == 'rate_limited'
    assert len(batches(client)) == 4 and all(b == ['m3'] for b in batches(client)[1:])
    assert all(d >= 15 * 0.75 for d in no_sleep.delays)      # longer than the quota minute in total
    assert sum(no_sleep.delays) > 60
    assert MailMessage.objects.count() == 3                  # m0..m2 kept
    mb.refresh_from_db()
    assert int(mb.history_id) == start + 3                   # stopped before m3, never past it
    client._item_errors.clear()
    assert run(mb, client).outcome == 'ok' and MailMessage.objects.count() == 5


def test_every_item_5xx_is_an_outage_and_moves_nothing(lagoon):
    mb = make_mailbox()
    client = batch_client(mb, 3)
    start = mb.history_id
    for i in range(3):
        client.fail_item(f'm{i}', 503, times=99)
    result = run(mb, client)
    assert result.outcome == 'error' and CaptureFailure.objects.count() == 0
    mb.refresh_from_db()
    assert mb.history_id == start


def test_single_get_failures_are_per_message_too(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    for i in range(4):
        client.add_message(inbound(f's{i}'))
    client.fail_item('s1', 400, times=99)
    client.fail_item('s2', 500, times=99)
    result = run(mb, client)
    assert result.outcome == 'ok_with_failures' and result.counts['stored'] == 2
    assert sorted(CaptureFailure.objects.values_list('gmail_id', flat=True)) == ['s1', 's2']


def test_a_failed_retry_of_a_failure_keeps_its_row(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('r1'))
    client.fail_item('r1', 400, times=2)
    run(mb, client)
    assert CaptureFailure.objects.get().attempts == 1
    run(mb, client)                                 # the retry fails again: still there
    assert CaptureFailure.objects.get().attempts == 2
    run(mb, client)                                 # now Gmail answers: stored, row gone
    assert CaptureFailure.objects.count() == 0 and MailMessage.objects.count() == 1


# --- F5: authentication and permission errors ---------------------------------------------

@pytest.mark.parametrize('status,reason,expected', [
    (401, '', 'gmail_unauthorized'),
    (403, 'insufficientPermissions', 'permission_denied'),
    (403, 'forbidden', 'permission_denied'),
    (403, '', 'permission_denied'),
    (403, 'accessNotConfigured', 'api_not_enabled'),
    (403, 'SERVICE_DISABLED', 'api_not_enabled'),
])
def test_permission_errors_are_auth_errors(status, reason, expected):
    error = error_for_status(status, reason)
    assert isinstance(error, GmailAuthError) and error.code == expected
    assert not isinstance(error, (GmailRateLimited, GmailServerError))


@pytest.mark.parametrize('reason', ['rateLimitExceeded', 'userRateLimitExceeded', 'quotaExceeded'])
def test_rate_limit_403s_stay_rate_limits(reason):
    assert isinstance(error_for_status(403, reason), GmailRateLimited)
    assert isinstance(error_for_status(429, ''), GmailRateLimited)
    assert isinstance(error_for_status(410, ''), GmailNotFound)


def test_every_auth_hint_fits_the_run_row_and_names_no_secret():
    for code, hint in AUTH_HINTS.items():
        assert len(f'auth {code}: {hint}') <= 200
        assert 'token=' not in hint and '/' not in hint.replace('and/or', '')


@pytest.mark.parametrize('status,reason', [(403, 'insufficientPermissions'), (401, '')])
def test_an_auth_error_ends_the_run_at_once_without_retries(lagoon, no_sleep, caplog, status, reason):
    mb = make_mailbox()
    client = primed(mb)
    client.fail('list_labels', status, times=99, reason=reason)
    result = run(mb, client, sleep=no_sleep)
    assert result.outcome == 'auth_error' and result.reason.startswith('auth ')
    assert [c for c in client.calls if c[0] == 'list_labels'] == [('list_labels', {})]
    assert no_sleep.delays == []
    row = CaptureRun.objects.get()
    assert row.outcome == 'auth_error' and row.error_class == 'GmailAuthError'
    mb.refresh_from_db()
    assert mb.last_error.startswith('auth ') and mb.consecutive_errors == 1


def test_a_credential_that_cannot_be_made_is_an_auth_error_with_the_setting_named(lagoon):
    from mail_capture.credentials import CredentialsMisconfigured
    mb = make_mailbox()

    def factory(mailbox):
        raise CredentialsMisconfigured('GOOGLE_CAPTURE_SERVICE_ACCOUNT is not set')
    result = sync_mailbox(mb.pk, factory)
    assert result.outcome == 'auth_error' and 'GOOGLE_CAPTURE_SERVICE_ACCOUNT' in result.reason
    assert CaptureRun.objects.get().outcome == 'auth_error'


def test_an_invalid_credentials_mode_is_refused(capture_on):
    from mail_capture import credentials
    capture_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'keyles'
    assert credentials.mode() == 'invalid'
    with pytest.raises(credentials.CredentialsMisconfigured, match='must be off, keyless or key_file'):
        credentials.check_mailbox(make_mailbox())


# --- F2: repeated errors need a person ---------------------------------------------------

def _break_store(monkeypatch):
    def broken(self, plan, now, queue_ops):
        raise TypeError('synthetic')
    monkeypatch.setattr(sync._Runner, '_store', broken)


def test_repeated_errors_mark_the_mailbox_and_stop_refetching(lagoon, monkeypatch, caplog):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad'))
    client.add_message(inbound('good'))
    _break_store(monkeypatch)
    caplog.set_level(logging.ERROR, logger='mail_capture.sync')
    for _ in range(conf.attention_after_errors()):
        with pytest.raises(TypeError):
            run(mb, client)
    mb.refresh_from_db()
    assert mb.needs_attention and mb.attention_reason == 'TypeError on gmail id bad'
    assert any('needs attention' in r.getMessage() and r.levelno == logging.ERROR for r in caplog.records)
    calls = len(client.calls)
    result = run(mb, client)
    assert result.outcome == 'needs_attention' and len(client.calls) == calls   # no Gmail call
    run_row = CaptureRun.objects.order_by('-started_at').first()
    assert (run_row.error_gmail_id, run_row.error_class) == ('bad', 'TypeError')


def test_the_threshold_is_a_setting(lagoon, monkeypatch, settings):
    settings.CAPTURE_ATTENTION_AFTER_ERRORS = 1
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad'))
    _break_store(monkeypatch)
    with pytest.raises(TypeError):
        run(mb, client)
    mb.refresh_from_db()
    assert mb.needs_attention


def test_skip_once_records_who_when_why_and_moves_on(lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad'))
    client.add_message(inbound('good'))
    real = sync._Runner._store

    def breaks_on_bad(self, plan, now, queue_ops):
        if plan.parsed.gmail_id == 'bad':
            raise TypeError('synthetic')
        return real(self, plan, now, queue_ops)
    monkeypatch.setattr(sync._Runner, '_store', breaks_on_bad)
    for _ in range(3):
        with pytest.raises(TypeError):
            run(mb, client)
    out = StringIO()
    call_command('gmail_sync', '--skip-once', 'bad', '--mailbox', SALES, '--by', 'Test Operator',
                 '--reason', 'synthetic code bug', stdout=out)
    assert 'skipped once' in out.getvalue()
    skip = CaptureSkip.objects.get()
    assert (skip.gmail_id, skip.actor, skip.reason, skip.used_at) == (
        'bad', 'person:Test Operator', 'synthetic code bug', None)
    mb.refresh_from_db()
    assert not mb.needs_attention and mb.consecutive_errors == 0
    assert MailboxAccessLog.objects.filter(purpose='config', detail__cleared_attention=True).exists()
    result = run(mb, client)
    assert result.outcome == 'ok' and result.counts['skipped_by_person'] == 1
    assert list(MailMessage.objects.values_list('rfc_message_id', flat=True)) == ['good@lagoon.test']
    skip.refresh_from_db()
    assert skip.used_at is not None
    mb.refresh_from_db()
    assert mb.history_id == client.history_id


def test_a_dry_run_does_not_use_up_a_skip(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('odd'))
    CaptureSkip.objects.create(mailbox=mb, gmail_id='odd', actor='person:t', reason='r')
    result = run(mb, client, dry_run=True)
    assert result.counts['skipped_by_person'] == 1
    assert CaptureSkip.objects.get().used_at is None


def test_a_new_code_version_clears_the_flag(lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    CaptureMailbox.objects.filter(pk=mb.pk).update(
        needs_attention=True, attention_reason='TypeError on gmail id x', attention_code_version='old-version')
    assert run(mb, client).outcome == 'ok'
    mb.refresh_from_db()
    assert not mb.needs_attention


def test_admin_shows_and_clears_needs_attention(lagoon, admin_client):
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(
        needs_attention=True, attention_reason='TypeError on gmail id x', attention_code_version=sync.code_version())
    page = admin_client.get('/admin/mail_capture/capturemailbox/').content.decode()
    assert 'TypeError on gmail id x' in page and 'needs_attention' in page
    admin_client.post('/admin/mail_capture/capturemailbox/', {
        'action': 'clear_needs_attention', '_selected_action': [str(mb.pk)]})
    mb.refresh_from_db()
    assert not mb.needs_attention


# --- F9 / F8: pacing and budgets ------------------------------------------------------------

class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_the_pacer_keeps_every_minute_under_the_limit():
    clock = Clock()
    pacer = QuotaPacer(6000, clock=clock)
    spent = []
    for i in range(400):
        units = 1000 if i % 3 else 2
        pacer.acquire(units, clock.sleep)
        spent.append((clock.now, units))
    for start, _ in spent:
        window = sum(u for t, u in spent if start <= t < start + 60)
        assert window <= 6000
    assert spent[-1][0] - spent[0][0] > 60       # it really paced (not all at once)


def test_the_pacer_starts_empty_and_drains_after_a_429():
    clock = Clock()
    pacer = QuotaPacer(6000, clock=clock)
    assert pacer.wait_for(20) > 0                 # a new run cannot burst on top of the last one
    clock.sleep(60)
    assert pacer.wait_for(1000) == 0
    pacer.drain()
    assert pacer.wait_for(1000) > 0


class QuotaFake(FakeGmailClient):
    """A fake that answers 429 like Gmail once a mailbox spends more than
    6,000 units in a minute (by the test clock)."""

    def __init__(self, *args, clock, **kwargs):
        super().__init__(*args, **kwargs)
        self.clock = clock
        self.spent = []

    def _charge(self, units):
        now = self.clock()
        self.spent = [(t, u) for t, u in self.spent if t > now - 60] + [(now, units)]
        if sum(u for _, u in self.spent) > 6000:
            raise GmailRateLimited(429, 'rateLimitExceeded')

    def list_messages(self, *a, **k):
        self._charge(5)
        return super().list_messages(*a, **k)

    def get_messages(self, ids, *a, **k):
        self._charge(20 * len(ids))
        return super().get_messages(ids, *a, **k)


def test_a_paced_backfill_stays_under_the_quota(lagoon):
    from datetime import date
    clock = Clock()
    mb = make_mailbox()
    messages = [inbound(f'q{i}', date=recent(i + 1)) for i in range(700)][::-1]
    client = QuotaFake(mb.email, messages=messages, batch=True, clock=clock)
    client.pacer = QuotaPacer(6000, clock=clock)
    result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=60), sleep=clock.sleep,
                 page_size=500)
    assert result.outcome == 'ok' and result.counts['stored'] == 700
    assert clock.now - 1000.0 > 60 * (700 * 20 / 6000) * 0.8     # it took the time the quota needs


def test_without_pacing_the_same_backfill_would_hit_the_limit(lagoon):
    from datetime import date
    clock = Clock()
    mb = make_mailbox()
    messages = [inbound(f'q{i}', date=recent(i + 1)) for i in range(700)][::-1]
    client = QuotaFake(mb.email, messages=messages, batch=True, clock=clock)
    result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=60),
                 sleep=lambda s: None, page_size=500)
    assert result.outcome == 'rate_limited'


def test_max_messages_trims_the_last_batch(lagoon):
    from datetime import date
    mb = make_mailbox()
    messages = [inbound(f'b{i}', date=recent(i + 1)) for i in range(60)][::-1]
    client = FakeGmailClient(mb.email, messages=messages, batch=True)
    result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=30), max_messages=2)
    assert [len(b) for b in batches(client)] == [2] and result.counts['stored'] == 2
    assert MailboxAccessLog.objects.get().messages_read == 2


def test_the_quota_budget_is_never_overshot(lagoon):
    from datetime import date
    mb = make_mailbox()
    messages = [inbound(f'b{i}', date=recent(i + 1)) for i in range(60)][::-1]
    client = FakeGmailClient(mb.email, messages=messages, batch=True)
    result = run(mb, client, kind='backfill', since=date.today() - timedelta(days=30), max_quota_units=500)
    assert result.outcome == 'partial' and result.counts['quota_units'] <= 500
    assert sum(len(b) for b in batches(client)) * 20 <= 500


def test_single_gets_never_overshoot_the_budget(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    for i in range(5):
        client.add_message(inbound(f'u{i}'))
    result = run(mb, client, max_quota_units=50)
    assert result.counts['quota_units'] <= 50 and result.outcome == 'partial'


# --- F10: the DKIM hint --------------------------------------------------------------------

@pytest.mark.parametrize('values,expect', [
    (['mx.google.com;\r\n dkim=pass header.i=@ourco.example header.s=s1 header.b=AbC; spf=pass'], ['ourco.example']),
    (['mx.google.com; dkim=pass header.d=ourco.example header.s=s1'], ['ourco.example']),
    (['mx.google.com; dkim=pass header.i=ourco.example@evil.example header.s=x'], ['evil.example']),
    (['mx.google.com; dkim=pass header.i=@ourco.example.evil.example'], ['ourco.example.evil.example']),
    (['mx.google.com; dkim=pass (header.d=ourco.example) header.i=@evil.example'], ['evil.example']),
    (['mx.google.com; dkim=pass header.d=ourco.example.evil.example'], ['ourco.example.evil.example']),
    (['mx.google.com; dkim=fail header.i=@ourco.example', 'mx.google.com; dkim=pass header.i=@ourco.example'], []),
    (['evil.example; dkim=pass header.d=ourco.example', 'mx.google.com; dkim=pass header.d=ourco.example'], []),
])
def test_only_the_signing_domain_of_gmails_own_header_counts(values, expect):
    assert parse.gmail_dkim_pass_domains(values) == expect


def _claimed_internal(client, gid, auth):
    client.add_message(gmail_message(gid, 'Sales <sales@ourco.example>', ['buyer@lagoon.test'], cc=[SALES],
                                     date=recent(1), labels=('INBOX',), message_id=f'<{gid}@x.test>',
                                     extra=[('Authentication-Results', a) for a in auth]))


@pytest.mark.parametrize('auth,flagged', [
    (['mx.google.com; dkim=pass header.i=@ourco.example header.s=s'], True),
    (['mx.google.com; dkim=pass header.i=ourco.example@evil.example header.s=x'], False),
    (['mx.google.com; dkim=pass header.d=mail.ourco.example'], False),           # exactly our domain only
    (['mx.google.com; dkim=fail header.d=ourco.example', 'mx.google.com; dkim=pass header.d=ourco.example'], False),
    (['other.example; dkim=pass header.d=ourco.example'], False),
])
def test_the_hint_needs_our_exact_signing_domain(capture_on, auth, flagged):
    make_contact(make_company('Lagoon Test Hotel'), 'buyer@lagoon.test')
    mb = make_mailbox()
    client = primed(mb)
    _claimed_internal(client, 'dk', auth)
    run(mb, client)
    message = MailMessage.objects.get()
    assert message.direction == 'claimed_internal'
    assert ('dkim_pass_internal' in message.flags) is flagged


# --- F7: past the recipient cap nothing reaches the queue -------------------------------------

def test_an_address_found_only_past_the_cap_is_never_queued(capture_on):
    company = make_company('Lagoon Test Hotel')
    make_contact(company, 'pat@lagoon.test')
    CompanyDomain.objects.create(company=company, domain='lagoon.test')
    mb = make_mailbox()
    client = primed(mb)
    internal = [f'staff{i}@ourco.example' for i in range(100)]
    client.add_message(gmail_message('ov1', 'Pat <pat@lagoon.test>', internal + ['late.colleague@lagoon.test'],
                                     subject='Overflow subject', date=recent(1), labels=('INBOX',)))
    run(mb, client)
    assert MailMessage.objects.count() == 1
    assert not UnmatchedSender.objects.filter(address='late.colleague@lagoon.test').exists()
    assert not MailMessage.objects.get().participants.filter(address='late.colleague@lagoon.test').exists()


# --- F3: the code version parked messages are tied to -------------------------------------------

def test_code_version_is_the_deploy_commit_or_the_engine_and_migration_state(monkeypatch):
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'abc123')
    assert sync.code_version() == 'abc123'
    monkeypatch.delenv('RENDER_GIT_COMMIT')
    monkeypatch.setattr(sync, '_LOCAL_VERSION', [])
    local = sync.code_version()
    assert local.startswith(sync.ENGINE_VERSION + '+') and len(local) == len(sync.ENGINE_VERSION) + 13
    monkeypatch.setattr(sync, '_LOCAL_VERSION', [])
    monkeypatch.setattr(sync, '_migration_state', lambda: 'differenthash')
    assert sync.code_version() != local


def test_parked_messages_come_back_when_the_local_version_changes(lagoon, monkeypatch):
    monkeypatch.delenv('RENDER_GIT_COMMIT', raising=False)
    mb = make_mailbox()
    client = primed(mb)
    CaptureFailure.objects.create(mailbox=mb, gmail_id='p1', error='IntegrityError', parked=True, attempts=3,
                                  code_version=sync.code_version(), first_failed_at=timezone.now(),
                                  last_failed_at=timezone.now())
    client.add_message(inbound('p1'))
    CaptureMailbox.objects.filter(pk=mb.pk).update(history_id=client.history_id)
    run(mb, client)
    assert MailMessage.objects.count() == 0                       # same version: stays parked
    monkeypatch.setattr(sync, '_LOCAL_VERSION', ['mail_capture-test-bump'])
    run(mb, client)
    assert MailMessage.objects.count() == 1 and CaptureFailure.objects.count() == 0


# --- nits: the suffix list --------------------------------------------------------------------

@pytest.mark.parametrize('domain', ['co..th', 'hotel..co.th', '.co.th', 'co.za', 'com.br', 'org.za', 'gob.mx',
                                    'co.uk', 'com.ar', 'com.tr', 'co.nz', 'hotel.ck', 'co.ck', 'com.np'])
def test_more_public_suffixes_are_refused(capture_on, domain):
    assert rules.is_public_suffix(domain)
    assert rules.rule_problem('domain', domain) and rules.company_domain_problem(domain)


@pytest.mark.parametrize('domain', ['somehotel.co.za', 'resort.com.br', 'hotel.co.ck', 'hotel.com.np',
                                    'hotelgroup.co.th', 'x.de'])
def test_registrable_domains_under_them_are_accepted(capture_on, domain):
    assert not rules.is_public_suffix(domain) and rules.rule_problem('domain', domain) == ''


def test_the_embedded_list_states_its_source():
    from mail_capture import public_suffixes
    doc = public_suffixes.__doc__
    assert 'publicsuffix.org' in doc and '2026-11-17' in doc and 'Mozilla Public License 2.0' in doc
    assert len(public_suffixes.SECOND_LEVELS) > 150


# --- the gmail_sync command: exit codes ------------------------------------------------------

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


def test_exit_0_while_the_master_switch_is_off(settings):
    settings.GOOGLE_CAPTURE_ENABLED = False
    assert gmail_sync('--incremental') == (0, 'capture disabled: GOOGLE_CAPTURE_ENABLED is off\n')


def test_exit_8_when_capture_is_on_but_cannot_run(switched_on):
    switched_on.CAPTURE_INTERNAL_DOMAINS = []
    code, text = gmail_sync('--incremental')
    assert code == 8 and 'CAPTURE_INTERNAL_DOMAINS' in text
    switched_on.CAPTURE_INTERNAL_DOMAINS = ['ourco.example']
    assert gmail_sync('--incremental')[0] == 8                  # no mailbox enabled
    make_mailbox()
    switched_on.GOOGLE_CAPTURE_CREDENTIALS_MODE = 'off'
    code, text = gmail_sync('--incremental')
    assert code == 8 and 'GOOGLE_CAPTURE_CREDENTIALS_MODE is off' in text


def test_exit_2_for_bad_arguments_and_a_wrong_mailbox(switched_on):
    make_mailbox()
    make_mailbox('off@ourco.example', enabled=False)
    make_mailbox('hr@ourco.example')
    switched_on.GOOGLE_CAPTURE_NEVER_MAILBOXES = ['hr@ourco.example']
    assert gmail_sync('--incremental', '--mailbox', 'nobody@ourco.example') == (
        2, 'no capture mailbox nobody@ourco.example\n')
    assert gmail_sync('--incremental', '--mailbox', 'off@ourco.example') == (
        2, 'mailbox off@ourco.example is not enabled\n')
    assert gmail_sync('--incremental', '--mailbox', 'hr@ourco.example') == (
        2, 'mailbox hr@ourco.example is on GOOGLE_CAPTURE_NEVER_MAILBOXES\n')
    assert gmail_sync()[0] == 2
    assert gmail_sync('--backfill', '--mailbox', SALES)[0] == 2
    assert gmail_sync('--backfill', '--since', '19-11-2099', '--mailbox', SALES)[0] == 2
    assert gmail_sync('--skip-once', 'abc', '--mailbox', SALES)[0] == 2           # who and why missing


def test_exit_codes_follow_the_outcome(switched_on, monkeypatch, lagoon):
    mb = make_mailbox()
    client = primed(mb)
    use_client(monkeypatch, client)
    assert gmail_sync('--incremental')[0] == 0
    client.add_message(inbound('f1'))
    client.fail_item('f1', 400, times=99)
    code, text = gmail_sync('--incremental')
    assert code == 5 and 'ok_with_failures' in text
    client.fail('list_labels', 429, times=99)
    monkeypatch.setattr(sync.time, 'sleep', lambda s: None)
    code, text = gmail_sync('--incremental')
    assert code == 4 and 'rate_limited' in text
    client._errors.clear()
    client.fail('list_labels', 403, times=99, reason='insufficientPermissions')
    code, text = gmail_sync('--incremental')
    assert code == 3 and 'auth_error' in text and 'permission denied' in text
    client._errors.clear()
    CaptureMailbox.objects.filter(pk=mb.pk).update(lease_token='other', lease_expires_at=timezone.now() + timedelta(hours=1))
    assert gmail_sync('--incremental')[0] == 7
    CaptureMailbox.objects.filter(pk=mb.pk).update(
        lease_token='', lease_expires_at=None, needs_attention=True, attention_reason='TypeError on gmail id f1',
        attention_code_version=sync.code_version())
    code, text = gmail_sync('--incremental')
    assert code == 6 and 'TypeError on gmail id f1' in text


def test_exit_1_when_the_run_errors(switched_on, monkeypatch, lagoon):
    make_mailbox()

    def broken(mailbox):
        raise RuntimeError('synthetic')
    monkeypatch.setattr('mail_capture.google_client.client_for', broken, raising=False)
    code, text = gmail_sync('--incremental')
    assert code == 1 and 'error (RuntimeError)' in text


def test_check_reports_auth_errors_and_needs_attention(switched_on, monkeypatch):
    mb = make_mailbox()
    client = FakeGmailClient(mb.email)
    use_client(monkeypatch, client)
    code, text = gmail_sync('--check')
    assert code == 0 and f'{SALES}: messages 0' in text
    CaptureMailbox.objects.filter(pk=mb.pk).update(needs_attention=True, attention_reason='TypeError on gmail id z')
    code, text = gmail_sync('--check')
    assert code == 6 and 'needs attention: TypeError on gmail id z' in text
    client.fail('get_profile', 403, reason='insufficientPermissions')
    code, text = gmail_sync('--check')
    assert code == 3 and 'auth_error permission_denied' in text


def test_the_most_severe_exit_code_wins():
    from mail_capture.management.commands.gmail_sync import worst
    assert worst([0, 5, 4]) == 4 and worst([5, 0]) == 5 and worst([1, 3]) == 3 and worst([]) == 0
    assert worst([7, 6]) == 6 and worst([8, 1]) == 8 and worst([2, 3]) == 2


def test_the_help_documents_the_exit_codes(capsys):
    from mail_capture.management.commands.gmail_sync import Command
    with pytest.raises(SystemExit):
        Command().run_from_argv(['manage.py', 'gmail_sync', '--help'])
    text = capsys.readouterr().out
    for line in ('1 run error', '2 bad arguments', '3 auth error', '4 rate limited', '5 ok with failures',
                 '6 needs attention', '7 busy', '8 not configured'):
        assert line in ' '.join(text.split())


def test_clear_attention_command(switched_on):
    mb = make_mailbox()
    CaptureMailbox.objects.filter(pk=mb.pk).update(needs_attention=True, attention_reason='x', consecutive_errors=4)
    code, text = gmail_sync('--clear-attention', '--mailbox', SALES, '--by', 'Test Operator', '--reason', 'fixed')
    assert code == 0
    mb.refresh_from_db()
    assert not mb.needs_attention and mb.consecutive_errors == 0
    log = MailboxAccessLog.objects.get(purpose='config')
    assert log.actor == 'person:Test Operator' and log.detail['reason'] == 'fixed'
