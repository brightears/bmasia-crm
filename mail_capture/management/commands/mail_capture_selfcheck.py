"""Read-only smoke test for mail capture.

Prints the switch state and row counts, then runs the whole pipeline (parse,
rules, matching, storage, de-duplication, conversation times, the queue,
dry-run, idempotency) against the bundled synthetic fixtures with
``FakeGmailClient``. Everything the pipeline writes happens inside one
transaction that is always rolled back, so nothing is left behind. No Google
API is called and no real mailbox is read: the fake client is the only client
the pipeline accepts while capture is switched off.

Output is counts only. Exit status is non-zero when an expectation fails.
"""
import uuid
from datetime import date, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings

from mail_capture import conf
from mail_capture.gmail_client import FakeGmailClient
from mail_capture.models import (
    CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog, MailboxCopy,
    MailConversation, MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)


FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'selfcheck'
FIXTURE_DOMAIN = 'ourco.example'
SALES = f'sales@{FIXTURE_DOMAIN}'
OPS = f'ops@{FIXTURE_DOMAIN}'
DOC_NUMBER = 'TH-CT99001'

TABLES = (
    CaptureMailbox, CaptureRule, CaptureRun, CompanyDomain, MailboxAccessLog, MailboxCopy,
    MailConversation, MailMatch, MailMessage, MailParticipant, UnmatchedSender,
)


class _Rollback(Exception):
    pass


def _counts():
    return {model.__name__: model.objects.count() for model in TABLES}


class Command(BaseCommand):
    help = 'Print mail-capture switch state and run the pipeline on synthetic fixtures (rolled back).'

    def add_arguments(self, parser):
        parser.add_argument('--no-pipeline', action='store_true',
                            help='Only print the switch state and counts.')

    def handle(self, *args, **options):
        state = conf.capture_state()
        out = self.stdout.write
        out(f"GOOGLE_CAPTURE_ENABLED: {'on' if conf.flag_enabled() else 'off'}")
        out(f'capture state: {"enabled" if state.enabled else "disabled"}'
            + (f' ({state.reason})' if state.reason else ''))
        out(f'internal domains configured: {len(conf.internal_domains())}')
        out(f'mailboxes: {CaptureMailbox.objects.count()} '
            f'(enabled {CaptureMailbox.objects.filter(enabled=True).count()})')
        out(f'rules: {CaptureRule.objects.count()}')
        out(f'company domains: {CompanyDomain.objects.count()}')
        out(f'stored messages: {MailMessage.objects.count()}, '
            f'open unmatched senders: {UnmatchedSender.objects.filter(status="open").count()}')
        if options['no_pipeline']:
            return

        before = _counts()
        failures = []
        report = {}
        try:
            with transaction.atomic():
                with override_settings(CAPTURE_INTERNAL_DOMAINS=[FIXTURE_DOMAIN],
                                       CAPTURE_INTERNAL_ADDRESSES=[]):
                    report, failures = self._pipeline()
                raise _Rollback()
        except _Rollback:
            pass
        after = _counts()
        for key, value in report.items():
            out(f'pipeline {key}: {value}')
        if after != before:
            failures.append('rows were left behind after the rollback')
        if failures:
            for failure in failures:
                self.stderr.write(f'FAILED: {failure}')
            raise CommandError(f'mail capture self-check failed ({len(failures)} checks)')
        out('pipeline: OK (all writes rolled back)')

    # -- the pipeline ----------------------------------------------------------
    def _pipeline(self):
        from crm_app.models import Company, Contact, Contract
        from mail_capture.sync import sync_mailbox

        tag = uuid.uuid4().hex[:8]
        lagoon = Company.objects.create(name=f'Mail capture self-check lagoon {tag}')
        Contact.objects.create(company=lagoon, name='Casey Synthetic', email='casey@selfcheck-lagoon.test')
        for n in (1, 2):
            group = Company.objects.create(name=f'Mail capture self-check group {n} {tag}')
            CompanyDomain.objects.create(company=group, domain='selfcheck-harbour.test')
        have_contract = not Contract.objects.filter(contract_number=DOC_NUMBER).exists()
        if have_contract:
            Contract.objects.create(
                company=lagoon, contract_number=DOC_NUMBER, start_date=date(2099, 1, 1),
                value=Decimal('0'), status='Draft',
            )

        mailboxes = {}
        clients = {}
        for email, cursor in ((SALES, '5000'), (OPS, '7000')):
            if CaptureMailbox.objects.filter(email=email).exists():
                return {}, ['a mailbox for the fixture address already exists']
            mailboxes[email] = CaptureMailbox.objects.create(email=email, enabled=True, history_id=cursor)
            clients[email] = FakeGmailClient.from_fixture_dir(FIXTURES, email)

        def factory(mailbox):
            return clients[mailbox.email]

        def sync(email, **kwargs):
            return sync_mailbox(
                mailboxes[email].pk, factory, actor='selfcheck', sleep=lambda s: None,
                fake_only=True, maintenance=False, **kwargs,
            )

        since = date(2000, 1, 1)
        results = [
            sync(SALES, kind='backfill', since=since),
            sync(OPS, kind='backfill', since=since),
            sync(SALES), sync(OPS),
        ]
        failures = [f'run {i} ended {r.outcome}' for i, r in enumerate(results) if r.outcome != 'ok']
        first = _counts()
        rerun = [sync(SALES, kind='backfill', since=since), sync(OPS)]
        failures += [f'rerun ended {r.outcome}' for r in rerun if r.outcome != 'ok']
        dry = sync(SALES, kind='backfill', since=since, dry_run=True)
        second = _counts()
        for name in ('CaptureRun', 'MailboxAccessLog'):
            first.pop(name), second.pop(name)
        if first != second:
            failures.append('a re-run or the dry run changed stored rows')

        expected_messages = 5 if have_contract else 4
        checks = {
            'messages stored': (MailMessage.objects.count(), expected_messages),
            'mailbox copies': (MailboxCopy.objects.count(), expected_messages + 1),
            'unmatched senders queued': (UnmatchedSender.objects.count(), 3 if not have_contract else 2),
            'messages with a body': (MailMessage.objects.exclude(body_text=None).count(), 0),
            'synthetic message ids': (MailMessage.objects.filter(message_id_synthetic=True).count(), 1),
            'internal-only skipped': (results[0].counts['skipped_internal'], 1),
            'skipped by rule or label': (results[0].counts['skipped_by_rule'], 1),
            'bulk or system skipped': (results[0].counts['skipped_system'], 1),
            'dry run stored': (dry.counts['stored'], 0),
        }
        conversation = MailConversation.objects.filter(conversation_key='sc-01@selfcheck-lagoon.test').first()
        if conversation is None:
            failures.append('the replied conversation was not built')
        else:
            checks['conversation messages'] = (conversation.message_count, 3)
            checks['conversation linked'] = (conversation.company_id == lagoon.pk, True)
            checks['last inbound (UTC hour)'] = (
                conversation.last_inbound_at.astimezone(dt_timezone.utc).hour, 2)
            checks['last outbound (UTC hour)'] = (
                conversation.last_outbound_at.astimezone(dt_timezone.utc).hour, 4)
        if have_contract:
            checks['document-number links'] = (
                MailMatch.objects.filter(method='doc_number', target_type='contract').count(), 1)
        report = {}
        for name, (got, want) in checks.items():
            report[name] = got
            if got != want:
                failures.append(f'{name}: got {got}, expected {want}')
        report['api calls (fake)'] = sum(len(c.calls) for c in clients.values())
        report['runs'] = CaptureRun.objects.count()
        return report, failures
