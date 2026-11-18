"""Default recipients: a contact whose email setting for that kind of email is off is never chosen.

Three situations per sender: (i) the company has a preferred contact (billing,
primary or decision maker), (ii) none, but the other contacts' settings are on,
(iii) none, and every contact's setting is off: nobody, and the sender says so.
No email is sent by these tests: the resolvers are called directly, and the
senders are only called where they return before building or sending anything.
"""
import pytest

from crm_app.models import Company, Contact
from crm_app.services import recipients
from crm_app.services.email_service import EmailService

FLAGS = ['receives_notifications', 'receives_renewal_emails', 'receives_seasonal_emails', 'receives_payment_emails',
         'receives_quarterly_emails', 'receives_soundtrack_alerts', 'receives_quote_emails',
         'receives_contract_emails', 'receives_invoice_emails']


@pytest.fixture
def company(db):
    return Company.objects.create(name='Example Recipient Hotel', billing_entity='BMAsia Limited')


def contact(company, email, **fields):
    return Contact.objects.create(company=company, name=email.split('@')[0], email=email, **fields)


def all_off():
    return {flag: False for flag in FLAGS}


SENDERS = {
    # name: (resolver, preferred contact fields, kind)
    'invoice': (recipients.invoice_recipients, {'contact_type': 'Billing'}, 'invoice'),
    'receipt': (recipients.receipt_recipients, {}, 'receipt'),
    'quote': (recipients.quote_recipients, {}, 'quote'),
    'contract': (recipients.contract_recipients, {}, 'contract'),
    'manual_renewal': (recipients.manual_renewal_recipients, {'contact_type': 'Decision Maker'}, 'renewal'),
}


@pytest.mark.parametrize('name', sorted(SENDERS))
def test_preferred_contact_is_chosen_when_its_setting_is_on(company, name):
    resolver, preferred, _ = SENDERS[name]
    contact(company, 'billing@example.test', **preferred)
    contact(company, 'other@example.test')
    expected = ['billing@example.test'] if preferred else ['billing@example.test', 'other@example.test']
    assert sorted(resolver(company)) == sorted(expected)


@pytest.mark.parametrize('name', sorted(SENDERS))
def test_without_a_preferred_contact_the_contacts_with_the_setting_on_are_chosen(company, name):
    resolver, _, _ = SENDERS[name]
    contact(company, 'a@example.test')
    contact(company, 'b@example.test')
    assert sorted(resolver(company)) == ['a@example.test', 'b@example.test']


@pytest.mark.parametrize('name', sorted(SENDERS))
def test_a_contact_with_the_setting_off_is_never_a_fallback(company, name):
    resolver, preferred, _ = SENDERS[name]
    contact(company, 'off@example.test', **all_off())
    assert resolver(company) == []
    contact(company, 'on@example.test')
    assert resolver(company) == ['on@example.test']


@pytest.mark.parametrize('name', sorted(SENDERS))
def test_a_preferred_contact_with_the_setting_off_is_skipped(company, name):
    resolver, preferred, _ = SENDERS[name]
    if not preferred:
        pytest.skip('no preferred contact for this sender')
    contact(company, 'preferred-off@example.test', **preferred, **all_off())
    contact(company, 'other@example.test')
    assert resolver(company) == ['other@example.test']


def test_inactive_contacts_are_never_chosen(company):
    contact(company, 'gone@example.test', is_active=False)
    assert recipients.invoice_recipients(company) == []


@pytest.mark.parametrize('sender, record', [
    ('send_invoice_email', 'invoice'), ('send_receipt_email', 'invoice'),
    ('send_quote_email', 'quote'), ('send_contract_email', 'contract'),
    ('send_manual_renewal_reminder', 'contract'),
])
def test_senders_report_a_clear_no_recipient_message_and_send_nothing(company, sender, record, monkeypatch):
    from datetime import date
    from decimal import Decimal

    from django.core import mail

    from crm_app.models import Contract, Invoice, Quote

    contact(company, 'off@example.test', **all_off())
    if record == 'invoice':
        obj = Invoice.objects.create(company=company, invoice_number='INV-RECIP-1', amount=Decimal('10'),
                                     total_amount=Decimal('10'), issue_date=date(2026, 11, 1),
                                     due_date=date(2026, 12, 1), receipt_number='RC-RECIP-1')
    elif record == 'quote':
        obj = Quote.objects.create(company=company, quote_number='QT-RECIP-1', valid_from=date(2026, 11, 1),
                                   valid_until=date(2026, 12, 1))
    else:
        obj = Contract.objects.create(company=company, contract_number='CT-RECIP-1', status='Active',
                                      start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                                      value=Decimal('10'), currency='THB')
    ok, message = getattr(EmailService(), sender)(obj.pk)
    assert ok is False
    assert 'No contact of Example Recipient Hotel is set to receive' in message
    assert mail.outbox == []


# ------------------------------------------------------------------ automated senders (suspended crons)


@pytest.mark.parametrize('resolver, preferred, flag', [
    (recipients.renewal_reminder_contacts, {'contact_type': 'Primary'}, 'receives_renewal_emails'),
    (recipients.payment_reminder_contacts, {'contact_type': 'Billing'}, 'receives_payment_emails'),
    (recipients.quarterly_checkin_contacts, {'contact_type': 'Primary'}, 'receives_quarterly_emails'),
])
def test_reminders_need_the_setting_and_the_master_switch(company, resolver, preferred, flag):
    chosen = contact(company, 'chosen@example.test', **preferred)
    contact(company, 'flag-off@example.test', **preferred, **{flag: False})
    contact(company, 'master-off@example.test', **preferred, receives_notifications=False)
    contact(company, 'unsubscribed@example.test', **preferred, unsubscribed=True)
    contact(company, 'not-preferred@example.test')
    assert resolver(company) == [chosen]


@pytest.mark.parametrize('kind, flag', [('quote', 'receives_quote_emails'), ('contract', 'receives_contract_emails')])
def test_followups_skip_contacts_with_the_setting_off(company, kind, flag):
    contact(company, 'a-off@example.test', **{flag: False})
    contact(company, 'b-master-off@example.test', receives_notifications=False)
    chosen = contact(company, 'c-on@example.test')
    assert recipients.followup_contact(company, kind) == chosen
    Contact.objects.filter(pk=chosen.pk).update(**{flag: False})
    assert recipients.followup_contact(company, kind) is None


def test_prospect_emails_skip_contacts_that_take_no_automated_email(company):
    primary_off = contact(company, 'primary@example.test', is_primary=True, receives_notifications=False)
    other = contact(company, 'other@example.test')
    assert recipients.prospect_contact(Contact.objects.filter(company=company)) == other
    Contact.objects.filter(pk=other.pk).update(unsubscribed=True)
    assert recipients.prospect_contact(Contact.objects.filter(company=company)) is None
    Contact.objects.filter(pk=primary_off.pk).update(receives_notifications=True)
    assert recipients.prospect_contact(Contact.objects.filter(company=company)) == primary_off


def test_a_contact_created_from_a_proposal_receives_nothing_by_default(company):
    new = contact(company, 'ap@lookalike.example.net', is_primary=False, **all_off())
    for resolver, _, _ in SENDERS.values():
        assert new.email not in resolver(company)
    assert recipients.renewal_reminder_contacts(company) == []
    assert recipients.payment_reminder_contacts(company) == []
    assert recipients.followup_contact(company, 'quote') is None
    assert recipients.prospect_contact(Contact.objects.filter(company=company)) is None
