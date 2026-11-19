"""The second review's blockers and low items, as behaviour that must hold."""
import inspect
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import DataError, OperationalError
from django.utils import timezone

from crm_app.models import Company

from mail_capture import parse, purge, sync
from mail_capture.models import (
    CaptureFailure, CaptureRule, CaptureRun, CompanyDomain, MailConversation,
    MailMessage, MailParticipant, UnmatchedSender,
)
from mail_capture.signals import REASON_TEXT, mail_purged
from mail_capture.sync import sync_mailbox

from .builders import (
    SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent,
)


pytestmark = pytest.mark.django_db
PRIVATE = {'id': 'Label_9', 'name': 'CRM private', 'type': 'user'}
CLIENTS = {'id': 'Label_3', 'name': 'Clients', 'type': 'user'}


def run(mailbox, client, **kwargs):
    kwargs.setdefault('sleep', lambda s: None)
    return sync_mailbox(mailbox.pk, factory_for(client), **kwargs)


@pytest.fixture
def lagoon(capture_on):
    company = make_company('Lagoon Test Hotel')
    return company, make_contact(company, 'pat@lagoon.test', 'Pat Example')


def inbound(gid, **kwargs):
    kwargs.setdefault('date', recent(5))
    return gmail_message(gid, kwargs.pop('frm', 'Pat Example <pat@lagoon.test>'), kwargs.pop('to', [SALES]),
                         **kwargs)


# --- R2: a label rule needs confirmation like any other ---------------------------

def test_label_rule_purges_stored_mail_only_after_confirmation(lagoon, admin_client):
    mb = make_mailbox()
    client = primed(mb, labels=[CLIENTS])
    for i in range(3):
        client.add_message(inbound(f'c{i}', message_id=f'<c{i}@lagoon.test>', labels=('INBOX', 'Label_3')))
    run(mb, client)
    assert MailMessage.objects.count() == 3
    response = admin_client.post('/admin/mail_capture/capturerule/add/', {
        'kind': 'label', 'value': 'Clients', 'scope': 'org', 'action': 'skip', 'note': ''})
    assert response.status_code == 302 and 'confirm-purge' in response['Location']
    run(mb, client)
    run(mb, client)
    assert MailMessage.objects.count() == 3            # saved, not confirmed: nothing purged
    page = admin_client.get(response['Location']).content.decode()
    assert 'Messages purged: <strong>3</strong>' in page
    admin_client.post(response['Location'], {'confirm': 'yes'})
    run(mb, client)
    assert MailMessage.objects.count() == 0


def test_the_built_in_private_label_stays_immediate(lagoon):
    mb = make_mailbox()
    client = primed(mb, labels=[PRIVATE])
    client.add_message(inbound('p1'))
    run(mb, client)
    client.add_labels('p1', ['Label_9'])
    run(mb, client)
    assert MailMessage.objects.count() == 0


# --- R3: only data errors fail a single message ----------------------------------------

@pytest.mark.parametrize('error', [TypeError('a bug'), OperationalError('connection lost'),
                                   TimeoutError('slow'), KeyError('x'), ValueError('bad conversion')])
def test_a_non_data_error_aborts_the_run_without_moving_the_cursor(lagoon, monkeypatch, error):
    mb = make_mailbox()
    client = primed(mb)
    start = mb.history_id
    for i in range(3):
        client.add_message(inbound(f'e{i}', message_id=f'<e{i}@lagoon.test>'))
    real = sync._Runner._store

    def broken(self, plan, now, queue_ops):
        raise error

    monkeypatch.setattr(sync._Runner, '_store', broken)
    for _ in range(4):
        with pytest.raises(type(error)):
            run(mb, client)
    mb.refresh_from_db()
    assert mb.history_id == start and mb.consecutive_errors == 4
    assert CaptureFailure.objects.count() == 0          # no attempt counted, nothing parked
    assert set(CaptureRun.objects.values_list('outcome', flat=True)) == {'error'}
    monkeypatch.setattr(sync._Runner, '_store', real)
    assert run(mb, client).counts['stored'] == 3


def test_a_data_error_fails_only_that_message(lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad', message_id='<bad@lagoon.test>'))
    client.add_message(inbound('ok', message_id='<ok@lagoon.test>'))
    real = sync._Runner._store

    def refuse(self, plan, now, queue_ops):
        if plan.parsed.gmail_id == 'bad':
            raise DataError('value too long')
        return real(self, plan, now, queue_ops)

    monkeypatch.setattr(sync._Runner, '_store', refuse)
    result = run(mb, client)
    assert result.outcome == 'ok_with_failures' and result.counts['failed'] == 1
    assert CaptureFailure.objects.get().code_version == sync.code_version()


def test_parked_messages_are_retried_when_the_code_changes(lagoon, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('bad', message_id='<bad@lagoon.test>'))
    real = sync._Runner._store

    def refuse(self, plan, now, queue_ops):
        raise DataError('refused')

    monkeypatch.setattr(sync._Runner, '_store', refuse)
    for _ in range(4):
        run(mb, client)
    failure = CaptureFailure.objects.get()
    assert failure.parked
    monkeypatch.setattr(sync._Runner, '_store', real)
    run(mb, client)
    assert CaptureFailure.objects.get().parked          # same code: stays parked
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'a-new-deploy')
    run(mb, client)
    assert MailMessage.objects.count() == 1 and CaptureFailure.objects.count() == 0


def test_unpark_command_and_admin_action(lagoon, admin_client):
    mb = make_mailbox()
    for gid in ('a', 'b'):
        CaptureFailure.objects.create(mailbox=mb, gmail_id=gid, attempts=3, parked=True,
                                      first_failed_at=timezone.now(), last_failed_at=timezone.now())
    out = StringIO()
    call_command('mail_capture_unpark', '--all', '--dry-run', stdout=out)
    assert 'parked messages: 2' in out.getvalue() and CaptureFailure.objects.filter(parked=True).count() == 2
    call_command('mail_capture_unpark', '--mailbox', mb.email, stdout=StringIO())
    assert CaptureFailure.objects.filter(parked=True).count() == 0
    CaptureFailure.objects.update(parked=True, attempts=3)
    pk = CaptureFailure.objects.first().pk
    response = admin_client.post('/admin/mail_capture/capturefailure/', {
        'action': 'unpark', '_selected_action': [pk]})
    assert response.status_code == 302
    assert CaptureFailure.objects.get(pk=pk).parked is False


def test_a_failed_queue_write_keeps_its_failure_row(capture_on, monkeypatch):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('q1', frm='stranger@unknown.test'))

    def refuse(self, *args, **kwargs):
        raise DataError('refused')

    monkeypatch.setattr(sync._Runner, '_queue_one', refuse)
    result = run(mb, client)
    assert result.counts['failed'] == 1
    assert list(CaptureFailure.objects.values_list('gmail_id', flat=True)) == ['q1']


# --- low items ----------------------------------------------------------------------------------

@pytest.mark.parametrize('value', ['<>', '<none>', 'none', '<NULL>', '<unknown>', '<->', '<@>'])
def test_placeholder_message_ids_count_as_missing(lagoon, value):
    mb = make_mailbox()
    client = primed(mb)
    for gid, subject in (('x1', 'First'), ('x2', 'Second')):
        client.add_message(inbound(gid, subject=subject, message_id=value))
    run(mb, client)
    assert MailMessage.objects.count() == 2
    assert all('placeholder_message_id' in m.flags for m in MailMessage.objects.all())


def test_a_sample_leaves_with_its_rotated_key(capture_on, monkeypatch):
    monkeypatch.setattr(sync, 'MAX_MESSAGE_KEYS', 2)
    mb = make_mailbox()
    client = primed(mb)
    for i, subject in enumerate(['First secret', 'Second', 'Third']):
        client.add_message(inbound(f'u{i}', frm='stranger@unknown.test', subject=subject,
                                   message_id=f'<u{i}@x.test>', date=recent(5 - i)))
    run(mb, client)
    row = UnmatchedSender.objects.get()
    assert [s['s'] for s in row.samples] == ['Second', 'Third']
    assert 'First secret' not in str(list(UnmatchedSender.objects.values()))


def test_a_purge_clears_the_message_sample_from_other_queue_rows(capture_on):
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(gmail_message('o1', SALES, ['secret@unknown-co.test', 'other@another-co.test'],
                                     labels=('SENT',), subject='Shared secret subject', date=recent(3),
                                     message_id='<shared@ourco.example>'))
    client.add_message(gmail_message('o2', 'other@another-co.test', [SALES], subject='Keep me',
                                     date=recent(2), message_id='<keep@x.test>'))
    run(mb, client)
    other = UnmatchedSender.objects.get(address='other@another-co.test')
    assert sorted(s['s'] for s in other.samples) == ['Keep me', 'Shared secret subject']
    rule = CaptureRule.objects.create(kind='address', value='secret@unknown-co.test', action='skip')
    purge.confirm_rule(rule)
    purge.enforce_rules()
    other.refresh_from_db()
    assert [s['s'] for s in other.samples] == ['Keep me'] and other.message_count == 1
    assert not UnmatchedSender.objects.filter(address='secret@unknown-co.test').exists()


def test_private_copy_of_never_stored_mail_scrubs_its_samples(capture_on):
    mb = make_mailbox()
    client = FakeClientWith([gmail_message('s1', 'stranger@unknown.test', [SALES], subject='Medical',
                                           date=recent(2), message_id='<s1@x.test>')], mb)
    run(mb, client, kind='backfill', since=datetime(2000, 1, 1, tzinfo=dt_timezone.utc))
    assert UnmatchedSender.objects.count() == 1
    client._messages['s1']['labelIds'] = ['INBOX', 'Label_9']
    run(mb, client, kind='backfill', since=datetime(2000, 1, 1, tzinfo=dt_timezone.utc))
    assert not UnmatchedSender.objects.exists()


def FakeClientWith(messages, mailbox):
    from mail_capture.gmail_client import FakeGmailClient
    return FakeGmailClient(mailbox.email, messages=messages, labels=[PRIVATE])


@pytest.mark.parametrize('domain', ['ac.id', 'web.id', 'com.mm', 'org.vn', 'edu.au', 'com.mo', 'gov.my',
                                    'onmicrosoft.com', 'co.th', 'com.hk', 'com.sg', 'com.my', 'co.id',
                                    'com.vn', 'com.ph', 'com.mv', 'com.lk', 'co.in', 'co.ae', 'com.au',
                                    'co.jp', 'co.kr', 'com.tw', 'com.cn', 'com.kh', 'com.la', 'th', 'com'])
def test_too_broad_domains_are_refused(capture_on, domain):
    from mail_capture.rules import company_domain_problem, rule_problem
    assert rule_problem('domain', domain) and company_domain_problem(domain)


@pytest.mark.parametrize('domain', ['hotelgroup.co.th', 'resort.com.mv', 'tenant.onmicrosoft.com', 'x.com'])
def test_registrable_domains_are_accepted(capture_on, domain):
    from mail_capture.rules import rule_problem
    assert rule_problem('domain', domain) == ''


def test_a_customer_beyond_the_recipient_cap_is_still_matched(lagoon):
    company, contact = lagoon
    mb = make_mailbox()
    client = primed(mb)
    internal = [f'staff{i}@ourco.example' for i in range(130)]
    to = internal[:120] + ['Pat Example <pat@lagoon.test>'] + internal[120:]
    client.add_message(gmail_message('big', SALES, to, labels=('SENT',), date=recent(1)))
    run(mb, client)
    message = MailMessage.objects.get()
    assert MailParticipant.objects.filter(message=message, contact=contact).exists()
    assert 'bounded' in message.flags and message.conversation.company == company


def test_a_never_log_address_beyond_the_cap_still_blocks_capture(lagoon):
    CaptureRule.objects.create(kind='address', value='secret@hidden.test', action='skip')
    mb = make_mailbox()
    client = primed(mb)
    to = ['pat@lagoon.test'] + [f'staff{i}@ourco.example' for i in range(130)] + ['secret@hidden.test']
    client.add_message(gmail_message('big', SALES, to, labels=('SENT',), date=recent(1)))
    assert run(mb, client).counts['skipped_by_rule'] == 1


def test_html_comments_and_quoted_attributes():
    assert parse.html_to_text('a<!-- <script> -->b') == 'ab'
    assert parse.html_to_text('<a title="a>b" href="x">link</a>') == 'link'
    assert parse.html_to_text('<!--[if mso]><style>x{}</style><![endif]-->Hello') == 'Hello'
    assert parse.html_to_text('x < y and y > z') == 'x < y and y > z'


def test_quoted_local_part_with_a_space():
    [a] = parse.parse_address_list('"john doe"@x.test')
    assert (a.address, a.domain, a.valid) == ('"john doe"@x.test', 'x.test', True)


def test_missing_internal_date_uses_the_capture_time(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    message = inbound('n1', date=datetime(2099, 1, 1, tzinfo=dt_timezone.utc))
    message['internalDate'] = 'not-a-number'
    client.add_message(message)
    before = timezone.now()
    run(mb, client)
    stored = MailMessage.objects.get()
    assert before - timedelta(seconds=5) <= stored.sent_at <= timezone.now()
    assert 'no_internal_date' in stored.flags and stored.claimed_date.year == 2099
    assert stored.conversation.last_inbound_at.year != 2099


def test_a_purged_conversation_key_never_survives(lagoon):
    """Two conversations: one already carries the purged token of the other's
    key. Purging that key folds the second into the first."""
    company, _ = lagoon
    token_conv = MailConversation.objects.create(conversation_key=purge.purged_token('root@x.test'))
    keyed = MailConversation.objects.create(conversation_key='root@x.test')
    now = timezone.now()
    root = MailMessage.objects.create(rfc_message_id='root@x.test', conversation=keyed, sent_at=now,
                                      direction='inbound', subject='Root')
    MailMessage.objects.create(rfc_message_id='kept@x.test', conversation=keyed, sent_at=now,
                               direction='inbound', subject='Kept', in_reply_to='root@x.test')
    MailMessage.objects.create(rfc_message_id='old@x.test', conversation=token_conv, sent_at=now,
                               direction='inbound', subject='Old')
    purge.purge_messages([root.pk])
    assert not MailConversation.objects.filter(conversation_key='root@x.test').exists()
    assert MailConversation.objects.count() == 1
    assert MailConversation.objects.get().message_count == 2


def test_admin_has_no_search_box_on_captured_data(admin_client, lagoon):
    for model in ('mailmessage', 'mailconversation', 'mailparticipant', 'unmatchedsender', 'capturerule'):
        page = admin_client.get(f'/admin/mail_capture/{model}/').content.decode()
        assert 'id="searchbar"' not in page, model


# --- tests the mutation pass asked for ------------------------------------------------------------

def test_retention_never_deletes_a_running_run(lagoon):
    mb = make_mailbox()
    old = timezone.now() - timedelta(days=400)
    CaptureRun.objects.create(mailbox=mb, kind='incremental', started_at=old, outcome='running')
    CaptureRun.objects.create(mailbox=mb, kind='incremental', started_at=old, outcome='ok')
    purge.purge_old_records()
    assert list(CaptureRun.objects.values_list('outcome', flat=True)) == ['running']


@pytest.mark.parametrize('name', ['0001_initial', '0002_before_switch_on'])
def test_the_migrations_set_their_lock_timeout(name):
    from django.db.migrations import RunPython
    module = __import__(f'mail_capture.migrations.{name}', fromlist=['Migration'])
    ops = module.Migration.operations
    assert isinstance(ops[0], RunPython) and ops[0].code is module.set_lock_timeout
    assert isinstance(ops[-1], RunPython) and ops[-1].reverse_code is module.set_lock_timeout
    executed = []

    class Editor:
        class connection:
            vendor = 'postgresql'

        def execute(self, sql):
            executed.append(sql)

    module.set_lock_timeout(None, Editor())
    assert executed == ["SET LOCAL lock_timeout = '5s'"]


# --- 5a. seeding company domains -----------------------------------------------------------------

def test_seed_domains_dry_run_then_apply(capture_on):
    lagoon = make_company('Lagoon Test Hotel')
    make_contact(lagoon, 'pat@lagoon.test')
    make_contact(lagoon, 'sam@lagoon.test')
    make_contact(lagoon, 'someone@gmail.com')
    parent = make_company('Harbour Group')
    one = Company.objects.create(name='Harbour One', parent_company=parent)
    two = Company.objects.create(name='Harbour Two', parent_company=parent)
    make_contact(one, 'gm@harbourgroup.test')
    make_contact(two, 'fo@harbourgroup.test')
    a, b = make_company('Unrelated A'), make_company('Unrelated B')
    make_contact(a, 'x@shared-isp.test')
    make_contact(b, 'y@shared-isp.test')
    make_contact(a, 'staff@ourco.example')
    out = StringIO()
    call_command('mail_capture_seed_domains', stdout=out)
    text = out.getvalue()
    assert 'would write: 3' in text and CompanyDomain.objects.count() == 0
    assert 'domains_skipped_several_companies: 1' in text and 'contacts_on_freemail: 1' in text
    assert 'lagoon.test' not in text                     # counts only
    call_command('mail_capture_seed_domains', '--apply', stdout=StringIO())
    rows = set(CompanyDomain.objects.values_list('company__name', 'domain', 'shared_group_domain'))
    assert rows == {('Lagoon Test Hotel', 'lagoon.test', False),
                    ('Harbour One', 'harbourgroup.test', True), ('Harbour Two', 'harbourgroup.test', True)}
    call_command('mail_capture_seed_domains', '--apply', stdout=out)
    assert CompanyDomain.objects.count() == 3


# --- 5b. a reply from an uncaptured internal mailbox is a hint, never "answered" ----------

def test_claimed_internal_reply_is_recorded_as_a_hint_only(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    t1, t2 = recent(3), recent(1)
    client.add_message(inbound('r1', date=t1, message_id='<r1@lagoon.test>'))
    auth = 'mx.google.com; dkim=pass header.i=@ourco.example header.s=s1; spf=pass'
    client.add_message(gmail_message('r2', 'Agent <agent@ourco.example>', ['pat@lagoon.test', SALES],
                                     date=t2, references='<r1@lagoon.test>', labels=('INBOX',),
                                     extra=[('Authentication-Results', auth)]))
    run(mb, client)
    conv = MailConversation.objects.get()
    assert conv.last_outbound_at is None and conv.last_inbound_at == t1
    assert conv.last_claimed_internal_at == t2
    reply = MailMessage.objects.get(rfc_message_id='r2@mail.example.org')
    assert reply.direction == 'claimed_internal' and 'dkim_pass_internal' in reply.flags


def test_a_forged_authentication_results_header_is_not_believed(lagoon):
    mb = make_mailbox()
    client = primed(mb)
    forged = 'evil.test; dkim=pass header.d=ourco.example'
    client.add_message(gmail_message('f1', 'Agent <agent@ourco.example>', ['pat@lagoon.test'],
                                     date=recent(1), labels=('INBOX',),
                                     extra=[('Authentication-Results', 'mx.google.com; dkim=fail header.d=ourco.example'),
                                            ('Authentication-Results', forged)]))
    run(mb, client)
    assert 'dkim_pass_internal' not in MailMessage.objects.get().flags


# --- 6. the interface with the activity-log app -------------------------------------------------

def _receiver_takes_source_refs():
    if not apps.is_installed('agent_inbox'):
        return False
    try:
        from agent_inbox.redaction import on_mail_purged
    except ImportError:
        return False
    return 'source_refs' in inspect.signature(on_mail_purged).parameters


@pytest.mark.skipif(not _receiver_takes_source_refs(),
                    reason="agent_inbox's receiver does not take source_refs yet (PR 67)")
def test_a_purge_redacts_the_activity_logged_for_the_same_email(lagoon, django_capture_on_commit_callbacks):
    from agent_inbox.models import Activity
    company, _ = lagoon
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(inbound('m1', message_id='<m1@lagoon.test>', subject='Renewal question'))
    run(mb, client)
    activity = Activity.objects.create(
        company=company, kind='email', direction='inbound', occurred_at=timezone.now(),
        summary='Customer asked about renewal', body='Synthetic body', participants=[],
        source_system='gmail', source_ref='m1@lagoon.test', recorded_by_username='agent-test',
        recorded_via='job', idempotency_key='k-1', payload_sha256='0' * 64,
    )
    with django_capture_on_commit_callbacks(execute=True):
        client.delete_message('m1')
        run(mb, client)
    activity.refresh_from_db()
    assert activity.is_redacted and activity.summary == '' and activity.body == ''


def test_the_purge_signal_carries_codes_and_readable_reasons(lagoon, django_capture_on_commit_callbacks):
    seen = []
    mail_purged.connect(lambda sender, **kw: seen.append(kw), weak=False, dispatch_uid='t-reason')
    try:
        mb = make_mailbox()
        client = primed(mb)
        client.add_message(inbound('m1', message_id='<m1@lagoon.test>'))
        run(mb, client)
        with django_capture_on_commit_callbacks(execute=True):
            client.delete_message('m1')
            run(mb, client)
    finally:
        mail_purged.disconnect(dispatch_uid='t-reason')
    [kw] = seen
    assert kw['source_system'] == 'gmail' and kw['source_refs'] == ['m1@lagoon.test']
    assert kw['reason'] == 'gmail_deleted' and kw['reason_text'] == REASON_TEXT['gmail_deleted']
