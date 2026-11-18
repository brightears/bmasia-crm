"""Who receives a customer email when the sender did not name the recipients.

One rule for every sender: a contact is chosen only when it is active, has an
email address and has the email setting for that kind of email switched on.
Automated emails (reminders, check-ins, follow-ups, prospecting) also need the
contact's master switch on and the contact not unsubscribed. Each sender may
prefer some contacts (for example the billing contact); when none of those is
eligible it falls back to the other eligible contacts, never to a contact whose
setting is off. When nobody is eligible the sender reports that no contact is
set to receive this kind of email and sends nothing.

Recipients a person chose in the send dialog are not filtered here.
"""
# Kind of email -> the contact setting that must be on.
KIND_FLAGS = {
    'quote': 'receives_quote_emails',
    'contract': 'receives_contract_emails',
    'invoice': 'receives_invoice_emails',
    'receipt': 'receives_invoice_emails',
    'renewal': 'receives_renewal_emails',
    'payment': 'receives_payment_emails',
    'quarterly': 'receives_quarterly_emails',
    'seasonal': 'receives_seasonal_emails',
    'zone_alert': 'receives_soundtrack_alerts',
    'prospect': None,
}
AUTOMATED = frozenset({'renewal', 'payment', 'quarterly', 'seasonal', 'zone_alert', 'prospect', 'followup'})
LABELS = {
    'quote': 'quote', 'contract': 'contract', 'invoice': 'invoice', 'receipt': 'receipt (invoice)',
    'renewal': 'renewal', 'payment': 'payment', 'quarterly': 'quarterly', 'seasonal': 'seasonal',
    'zone_alert': 'zone alert', 'prospect': 'automated',
}


def eligible_contacts(contacts, kind, automated=None):
    """The contacts in ``contacts`` (a queryset) that may receive this kind of email."""
    flag = KIND_FLAGS[kind]
    queryset = contacts.filter(is_active=True, email__isnull=False).exclude(email='')
    if flag:
        queryset = queryset.filter(**{flag: True})
    is_automated = (kind in AUTOMATED) if automated is None else automated
    if is_automated:
        queryset = queryset.filter(receives_notifications=True, unsubscribed=False)
    return queryset


def _wants(contact, notification_type):
    return notification_type in (contact.notification_types or [])


def preferred_then_eligible(contacts, kind, prefer, automated=None):
    """Emails of the eligible contacts that ``prefer(contact)`` picks, else of all eligible contacts."""
    eligible = list(eligible_contacts(contacts, kind, automated))
    chosen = [c for c in eligible if prefer(c)] or eligible
    seen, emails = set(), []
    for contact in chosen:
        if contact.email not in seen:
            seen.add(contact.email)
            emails.append(contact.email)
    return emails


def no_recipient_message(company, kind):
    return (f'No contact of {company.name} is set to receive {LABELS.get(kind, kind)} emails. '
            'Choose the recipients, or switch the email setting on for a contact.')


# ------------------------------------------------------------------ per sender

def quote_recipients(company):
    return preferred_then_eligible(company.contacts.all(), 'quote', lambda c: True)


def contract_recipients(company):
    return preferred_then_eligible(company.contacts.all(), 'contract', lambda c: True)


def invoice_recipients(company):
    return preferred_then_eligible(
        company.contacts.all(), 'invoice', lambda c: c.contact_type == 'Billing' or _wants(c, 'invoice'))


def receipt_recipients(company):
    return preferred_then_eligible(company.contacts.all(), 'receipt', lambda c: True)


def manual_renewal_recipients(company):
    return preferred_then_eligible(
        company.contacts.all(), 'renewal',
        lambda c: c.contact_type in ('Primary', 'Decision Maker') or _wants(c, 'renewal'), automated=False)


def renewal_reminder_contacts(company):
    return [c for c in eligible_contacts(company.contacts.all(), 'renewal')
            if c.contact_type in ('Primary', 'Decision Maker') or _wants(c, 'renewal')]


def payment_reminder_contacts(company):
    return [c for c in eligible_contacts(company.contacts.all(), 'payment')
            if c.contact_type == 'Billing' or _wants(c, 'payment')]


def quarterly_checkin_contacts(company):
    return [c for c in eligible_contacts(company.contacts.all(), 'quarterly')
            if c.contact_type == 'Primary' or _wants(c, 'quarterly')]


def followup_contact(company, kind):
    """The contact an automated quote or contract follow-up goes to when none is named."""
    return eligible_contacts(company.contacts.all(), kind, automated=True).first()


def prospect_contact(contacts):
    """The primary contact, else another contact, of those still taking automated email."""
    return eligible_contacts(contacts, 'prospect').order_by('-is_primary', 'name').first()

