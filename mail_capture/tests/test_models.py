"""Constraints, and that CRM deletes are never blocked or widened by capture."""
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from crm_app.models import EmailLog

from mail_capture.models import (
    CaptureRule, CompanyDomain, MailboxCopy, MailConversation, MailMatch, MailMessage,
    MailParticipant,
)
from mail_capture.sync import sync_mailbox

from .builders import OPS, SALES, factory_for, gmail_message, make_company, make_contact, make_mailbox, primed, recent


pytestmark = pytest.mark.django_db


@pytest.fixture
def captured(capture_on):
    company = make_company('Lagoon Test Hotel')
    contact = make_contact(company, 'pat@lagoon.test')
    CompanyDomain.objects.create(company=company, domain='lagoon.test')
    log = EmailLog.objects.create(
        company=company, contact=contact, email_type='manual', from_email=SALES,
        to_email='pat@lagoon.test', subject='s', body_html='', body_text='', status='sent',
        message_id='<crm-7@ourco.example>',
    )
    mb = make_mailbox()
    client = primed(mb)
    client.add_message(gmail_message('g1', 'pat@lagoon.test', [SALES], date=recent(2)))
    client.add_message(gmail_message('g2', SALES, ['pat@lagoon.test'], labels=('SENT',), date=recent(1),
                                     message_id='<crm-7@ourco.example>'))
    sync_mailbox(mb.pk, factory_for(client), sleep=lambda s: None)
    assert MailMessage.objects.count() == 2
    return company, contact, log, mb


def test_company_delete_unlinks_and_is_not_blocked(captured):
    company, contact, log, _ = captured
    company_id = str(company.pk)
    company.delete()   # cascades contacts and email logs in crm_app as before
    assert MailConversation.objects.count() == 2
    assert MailConversation.objects.filter(company__isnull=False).count() == 0
    assert MailParticipant.objects.filter(contact__isnull=False).count() == 0
    assert MailMessage.objects.filter(email_log__isnull=False).count() == 0
    assert CompanyDomain.objects.count() == 0
    # Matches point by type and id, so they never block the delete.
    assert MailMatch.objects.filter(target_id=company_id).exists()
    assert MailMessage.objects.count() == 2


def test_contact_delete_unlinks(captured):
    _, contact, _, _ = captured
    contact.delete()
    assert MailParticipant.objects.filter(contact__isnull=False).count() == 0


def test_email_log_delete_unlinks(captured):
    _, _, log, _ = captured
    log.delete()
    assert MailMessage.objects.filter(email_log__isnull=False).count() == 0


def test_mailbox_with_copies_is_protected(captured):
    _, _, _, mb = captured
    from django.db.models import ProtectedError
    with pytest.raises(ProtectedError):
        mb.delete()


def test_unique_message_id_and_copy_constraints(captured):
    _, _, _, mb = captured
    message = MailMessage.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        MailMessage.objects.create(rfc_message_id=message.rfc_message_id, conversation=message.conversation,
                                   sent_at=timezone.now(), direction='inbound')
    copy = MailboxCopy.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        MailboxCopy.objects.create(message=MailMessage.objects.exclude(pk=copy.message_id).first(),
                                   mailbox=mb, gmail_id=copy.gmail_id)
    with pytest.raises(IntegrityError), transaction.atomic():
        MailboxCopy.objects.create(message=copy.message, mailbox=mb, gmail_id='another-id')


def test_match_constraints(captured):
    message = MailMessage.objects.first()
    existing = message.matches.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        MailMatch.objects.create(message=message, target_type=existing.target_type,
                                 target_id=existing.target_id, method='manual', confidence='high',
                                 status='proposed')
    with pytest.raises(IntegrityError), transaction.atomic():
        MailMatch.objects.create(message=message, conversation=message.conversation,
                                 target_type='company', target_id='x', method='manual',
                                 confidence='high', status='proposed')


def test_rule_constraints(capture_on):
    CaptureRule.objects.create(kind='domain', value='lagoon.test')
    with pytest.raises(IntegrityError), transaction.atomic():
        CaptureRule.objects.create(kind='domain', value='LAGOON.test')
    with pytest.raises(IntegrityError), transaction.atomic():
        CaptureRule.objects.create(kind='domain', value='x.test', scope='mailbox')
    mb = make_mailbox(OPS)
    CaptureRule.objects.create(kind='domain', value='lagoon.test', scope='mailbox', mailbox=mb)


def test_unmatched_and_mailbox_normalise(capture_on):
    mb = make_mailbox('Sales.Team@OurCo.Example')
    assert mb.email == 'sales.team@ourco.example'
    domain = CompanyDomain.objects.create(company=make_company('X Test Co'), domain='@Lagoon.TEST.')
    assert domain.domain == 'lagoon.test'
