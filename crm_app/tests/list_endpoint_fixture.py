"""A deterministic CRM dataset for the list-endpoint response and query-count tests.

Every name is invented. Every primary key, timestamp and date is fixed, so the
serialized output is the same on SQLite and PostgreSQL and on every run. Values
that the lists sort by (company and contact names, contract start dates, issue
dates, created_at, ...) are unique, so the row order never depends on how the
database breaks ties.

Companies never get a Soundtrack account id: a post-save signal would call the
external API for it.
"""
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from freezegun import freeze_time

from crm_app.models import (
    Company, Contact, Contract, ContractDocument, ContractLineItem,
    ContractServiceLocation, ContractZone, Device, Invoice, InvoiceLineItem,
    Note, Opportunity, OpportunityActivity, Quote, QuoteActivity, QuoteAttachment,
    QuoteLineItem, ServicePackageItem, Task, TaskComment, Ticket, TicketAttachment,
    TicketComment, User, Zone,
)

BUILD_STARTS_AT = datetime(2026, 1, 5, 2, 0, 0, tzinfo=dt_timezone.utc)
# The moment the responses are read (days_until_expiry, is_overdue, ... depend on it).
READ_AT = '2026-11-18T03:00:00Z'

_KINDS = {
    'user': 1, 'company': 2, 'contact': 3, 'device': 4, 'zone': 5, 'opportunity': 6,
    'activity': 7, 'contract': 8, 'contract_item': 9, 'service_location': 10,
    'zone_link': 11, 'invoice': 12, 'invoice_item': 13, 'quote': 14, 'quote_item': 15,
    'quote_activity': 16, 'quote_attachment': 17, 'task': 18, 'task_comment': 19,
    'note': 20, 'ticket': 21, 'ticket_comment': 22, 'ticket_attachment': 23,
}


def uid(kind, number):
    """A fixed UUID per (kind, number)."""
    return uuid.UUID(int=(_KINDS[kind] << 96) | number)


class _Clock:
    """Moves the frozen clock one second per created record, so created_at is unique."""

    def __init__(self, frozen):
        self.frozen = frozen

    def tick(self):
        self.frozen.tick(timedelta(seconds=1))


def _users(clock):
    admin = User.objects.create(
        id=uid('user', 1), username='list-admin', email='admin@example.com',
        first_name='Avery', last_name='Admin', role='Admin', is_active=True,
    )
    clock.tick()
    sales = User.objects.create(
        id=uid('user', 2), username='list-sales', email='sales@example.com',
        first_name='Sam', last_name='Seller', role='Sales', is_active=True,
    )
    clock.tick()
    # No first or last name: get_full_name() is ''.
    tech = User.objects.create(
        id=uid('user', 3), username='list-tech', email='tech@example.com',
        role='Tech', is_active=True,
    )
    clock.tick()
    return admin, sales, tech


def _service_items():
    return [
        ServicePackageItem.objects.create(
            id=990001 + n, name=f'Service item {n}', description=f'Included service {n}',
            is_standard=(n != 2), display_order=n,
        )
        for n in range(3)
    ]


def build_list_dataset(n_companies):
    """Create n_companies invented companies with all their related records.

    Returns the Admin user who reads the lists.
    """
    with freeze_time(BUILD_STARTS_AT) as frozen:
        clock = _Clock(frozen)
        admin, sales, tech = _users(clock)
        service_items = _service_items()
        companies = []
        current_terms = []
        for i in range(n_companies):
            company, current = _company_records(i, companies, current_terms, admin, sales, tech,
                                                service_items, clock)
            companies.append(company)
            current_terms.append(current)
    return admin


def _company_records(i, companies, current_terms, admin, sales, tech, service_items, clock):
    thai = i % 2 == 1
    currency = 'THB' if thai else 'USD'
    parent_index = i - i % 5
    parent = companies[parent_index] if i % 5 in (1, 2) and parent_index < len(companies) else None
    company = Company.objects.create(
        id=uid('company', i),
        name=f'Testco {i:03d}',
        legal_entity_name=f'Testco {i:03d} Holdings Ltd.' if i % 3 else '',
        country=['Thailand', 'Singapore', 'Vietnam'][i % 3],
        website=f'https://testco{i:03d}.example.com',
        industry=['Hotels', 'Restaurants', 'Bars', 'Retail Fashion'][i % 4],
        location_count=i % 4,
        music_zone_count=(i % 4) * 2 + 1,
        contracted_product=['soundtrack', 'beatbreeze', ''][i % 3],
        contracted_zone_count=i % 3,
        is_active=i % 7 != 6,
        notes=f'Invented notes {i}',
        address_line1=f'{i} Example Road',
        address_line2='' if i % 2 else 'Floor 2',
        city=['Bangkok', 'Singapore', 'Hanoi'][i % 3],
        postal_code='' if i % 3 == 2 else f'1{i:04d}',
        phone='+66 2 000 0000' if thai else '',
        email=f'office{i:03d}@example.com',
        billing_entity='BMAsia (Thailand) Co., Ltd.' if thai else 'BMAsia Limited',
        parent_company=parent,
        is_corporate_parent=i % 5 == 0,
    )
    clock.tick()

    contacts = []
    for k, letter in enumerate('abc'):
        contacts.append(Contact.objects.create(
            id=uid('contact', i * 10 + k), company=company,
            name=f'Contact {i:03d} {letter}', email=f'contact{i:03d}{letter}@example.com',
            phone='+66812345678' if k == 0 else '',
            title=['Manager', 'Director', 'Owner'][k],
            contact_type=['Primary', 'Billing', 'Technical'][k],
            is_primary=False,
            is_active=k != 1,
        ))
        clock.tick()
    # Contact.save() keeps one primary per company; imported data can hold more, so
    # the flags are set directly. a: primary unless i % 3 == 2; b: an inactive
    # primary; c: a second active primary when i % 3 == 1 (the first by name wins).
    for contact, primary in zip(contacts, [i % 3 != 2, True, i % 3 == 1]):
        if primary:
            Contact.objects.filter(pk=contact.pk).update(is_primary=True)
            contact.is_primary = True
    first_contact = contacts[0]

    zones = []
    device = None
    if i % 2 == 0:
        device = Device.objects.create(
            id=uid('device', i), company=company, name=f'Player {i:03d}', device_type='music_player',
        )
        clock.tick()
    for k in range(i % 4):
        zones.append(Zone.objects.create(
            id=uid('zone', i * 10 + k), company=company, name=f'Zone {i:03d} {k}',
            platform=['soundtrack', 'beatbreeze'][(i + k) % 2],
            status=['online', 'offline', 'no_device', 'pending'][(i + k) % 4],
            device=device if k == 0 else None,
            device_name='' if k else f'Box {i}',
        ))
        clock.tick()

    opportunities = []
    for k in range(2):
        opportunities.append(Opportunity.objects.create(
            id=uid('opportunity', i * 10 + k), company=company,
            name=f'Opportunity {i:03d} {k}',
            stage=['Contacted', 'Quotation Sent', 'Contract Sent', 'Won', 'Lost'][(i + k) % 5],
            expected_value=Decimal(f'{1000 + i * 10 + k}.25'),
            probability=(i * 7 + k * 13) % 100,
            owner=sales if (i + k) % 3 else None,
            is_active=k == 0,
            follow_up_date=date(2026, 11, 1) + timedelta(days=i % 30) if k == 0 else None,
        ))
        clock.tick()
    for k in range(2):
        OpportunityActivity.objects.create(
            id=uid('activity', i * 10 + k), opportunity=opportunities[0],
            user=admin if k == 0 else None, contact=first_contact if k == 0 else None,
            activity_type=['Call', 'Email'][k], subject=f'Activity {i} {k}',
            description=f'Invented activity {i} {k}',
        )
        clock.tick()

    quote = Quote.objects.create(
        id=uid('quote', i), quote_number=f'{"TH" if thai else "HK"}-QT9{i:04d}',
        company=company, contact=first_contact, opportunity=opportunities[0],
        status=['Draft', 'Sent', 'Accepted'][i % 3],
        sent_date=date(2026, 2, 1) if i % 3 == 1 else None,
        valid_from=date(2026, 1, 1) + timedelta(days=i),
        valid_until=date(2026, 12, 1) + timedelta(days=i),
        currency=currency, created_by=admin if i % 4 else None,
        discount_amount=Decimal('10.00'), tax_amount=Decimal('7.00'),
    )
    clock.tick()
    for k in range(2):
        QuoteLineItem.objects.create(
            id=uid('quote_item', i * 10 + k), quote=quote, product_service=f'Music {k}',
            description=f'Quoted service {k}', quantity=Decimal(k + 1),
            unit_price=Decimal(f'{100 + i}.10'), line_total=Decimal('0'),
        )
        clock.tick()
    QuoteActivity.objects.create(
        id=uid('quote_activity', i), quote=quote, user=admin if i % 3 else None,
        activity_type='Created', description=f'Quote {i} was created',
    )
    clock.tick()
    if i % 2 == 0:
        QuoteAttachment.objects.create(
            id=uid('quote_attachment', i), quote=quote, name=f'brief-{i}.pdf',
            file=f'quote_attachments/brief-{i}.pdf', size=1000 + i, uploaded_by=sales,
        )
        clock.tick()

    contracts = _contracts(i, company, currency, opportunities[0], quote, parent, companies,
                           current_terms, zones, admin, service_items, clock)
    previous, current, draft = contracts

    TaskComment_target = None
    for k in range(2):
        task = Task.objects.create(
            id=uid('task', i * 10 + k), company=company,
            assigned_to=sales if k == 0 else None, created_by=admin,
            title=f'Task {i:03d} {k}', description=f'Invented task {i} {k}',
            priority=['Low', 'Medium', 'High', 'Urgent'][(i + k) % 4],
            status=['To Do', 'In Progress', 'Done'][(i + k) % 3],
            task_type=['Call', 'Email', 'Follow-up'][(i + k) % 3],
            due_date=datetime(2026, 10, 1, 9, 0, tzinfo=dt_timezone.utc) + timedelta(hours=i * 5 + k),
            related_opportunity=opportunities[0] if k == 0 else None,
            related_contract=current if k == 0 else None,
            related_contact=first_contact if k == 0 else None,
        )
        clock.tick()
        if k == 0:
            TaskComment_target = task
    TaskComment.objects.create(
        id=uid('task_comment', i), task=TaskComment_target, user=admin, comment=f'Comment {i}',
    )
    clock.tick()

    for k in range(2):
        Note.objects.create(
            id=uid('note', i * 10 + k), company=company, author=admin if k == 0 else None,
            contact=first_contact if k == 0 else None, note_type='General', priority='Medium',
            title=f'Note {i} {k}', text=f'Invented note {i} {k}',
        )
        clock.tick()

    ticket = Ticket.objects.create(
        id=uid('ticket', i), ticket_number=f'TK-9{i:05d}', subject=f'Ticket {i}',
        description=f'Invented ticket {i}', status=['new', 'assigned', 'resolved'][i % 3],
        priority=['low', 'medium', 'high'][i % 3], category='technical', company=company,
        contact=first_contact, zone=zones[0] if zones else None,
        assigned_to=tech if i % 2 else None, assigned_team='Tech', created_by=admin,
        due_date=datetime(2026, 11, 1, tzinfo=dt_timezone.utc) + timedelta(days=i % 40),
    )
    clock.tick()
    for k in range(2):
        TicketComment.objects.create(
            id=uid('ticket_comment', i * 10 + k), ticket=ticket, author=[tech, admin][k],
            text=f'Ticket comment {i} {k}', is_internal=k == 1,
        )
        clock.tick()
    if i % 3 == 0:
        TicketAttachment.objects.create(
            id=uid('ticket_attachment', i), ticket=ticket, file=f'ticket_attachments/log-{i}.txt',
            name=f'log-{i}.txt', size=200 + i, uploaded_by=tech,
        )
        clock.tick()
    return company, current


def _contracts(i, company, currency, opportunity, quote, parent, companies, current_terms,
               zones, admin, service_items, clock):
    region = 'TH' if currency == 'THB' else 'HK'
    previous_start = date(2024, 1, 1) + timedelta(days=3 * i)
    current_start = date(2025, 1, 1) + timedelta(days=3 * i)
    draft_start = date(2026, 1, 1) + timedelta(days=3 * i)
    current_end = date(2027, 3, 1) + timedelta(days=i % 28)
    lapsed = i % 6 == 5

    previous = Contract.objects.create(
        id=uid('contract', i * 10), company=company, contract_number=f'{region}-CT9{i:04d}0',
        contract_type='Annual', service_type='soundtrack_essential_yearly', status='Renewed',
        start_date=previous_start, end_date=current_start - timedelta(days=1),
        value=Decimal(f'{900 + i}.00'), currency=currency, is_active=False,
    )
    clock.tick()
    master = None
    category = 'standard'
    if i % 5 == 0:
        category = 'corporate_master'
    elif parent is not None:
        category = 'participation'
        master = current_terms[companies.index(parent)]
    current = Contract.objects.create(
        id=uid('contract', i * 10 + 1), company=company, contract_number=f'{region}-CT9{i:04d}1',
        contract_type='Annual', service_type='soundtrack_unlimited_yearly' if i % 3 else 'beatbreeze',
        status='Expired' if lapsed else 'Active', is_active=not lapsed,
        start_date=current_start, end_date=current_end,
        value=Decimal(f'{1000 + i}.50'), tax_rate=Decimal('7.00'),
        tax_amount=Decimal(f'{70 + i}.04'), total_value=Decimal(f'{1070 + i}.54'),
        currency=currency, renewed_from=previous, opportunity=opportunity,
        quote=quote if i % 2 == 0 else None, contract_category=category, master_contract=master,
        soundtrack_account_id=f'ST-CONTRACT-{i}' if i % 3 == 0 else '',
        billing_frequency=['Annual', 'Quarterly'][i % 2], auto_renew=i % 2 == 0,
        price_per_zone=Decimal('500.00') if i % 4 == 0 else None,
    )
    clock.tick()
    draft = Contract.objects.create(
        id=uid('contract', i * 10 + 2), company=company, contract_number=f'{region}-CT9{i:04d}2',
        contract_type='Monthly' if i % 2 else 'Annual', status='Draft',
        start_date=draft_start, end_date=None if i % 4 == 0 else draft_start + timedelta(days=364),
        value=Decimal(f'{50 + i}.75'), currency='THB' if i % 3 == 0 else 'USD',
        is_active=i % 2 == 0,
    )
    clock.tick()
    current.service_items.set(service_items[:2])

    for contract, count in ((previous, 1), (current, 2)):
        for k in range(count):
            ContractLineItem.objects.create(
                id=uid('contract_item', i * 100 + (10 if contract is current else 0) + k),
                contract=contract, product_service=f'Zone licence {k}', description=f'Licence {k}',
                quantity=Decimal(k + 1), unit_price=Decimal(f'{200 + i}.00'),
                tax_rate=Decimal('7.00'), line_total=Decimal('0'),
            )
            clock.tick()
    if i % 2 == 0:
        for k in range(2):
            ContractServiceLocation.objects.create(
                id=uid('service_location', i * 10 + k), contract=current,
                location_name=f'Outlet {i:03d} {k}', platform=['soundtrack', 'beatbreeze'][k],
                sort_order=k, price=Decimal('250.00') if k == 0 else None,
            )
            clock.tick()

    for k, zone in enumerate(zones):
        links = [
            (previous, previous_start, previous.end_date, False),
            (current, current_start, None, True),
        ]
        if k == 0:
            links.append((draft, draft_start, None, True))
        for n, (contract, start, end, active) in enumerate(links):
            ContractZone.objects.create(
                id=uid('zone_link', i * 100 + k * 10 + n), contract=contract, zone=zone,
                start_date=start, end_date=end, is_active=active,
            )
            clock.tick()

    invoices = [
        (previous, 'Paid', previous_start),
        (current, 'Paid', current_start),
        (current, 'Sent', current_start + timedelta(days=90)),
    ]
    for k, (contract, status, issued) in enumerate(invoices):
        amount = Decimal(f'{300 + i}.33')
        invoice = Invoice.objects.create(
            id=uid('invoice', i * 10 + k), company=company, contract=contract,
            invoice_number=f'{region}-INV9{i:04d}{k}', status=status,
            issue_date=issued, due_date=issued + timedelta(days=30),
            paid_date=issued + timedelta(days=10) if status == 'Paid' else None,
            amount=amount, tax_amount=Decimal('21.02'), discount_amount=Decimal('1.00'),
            total_amount=Decimal('0'), currency=currency,
        )
        clock.tick()
        InvoiceLineItem.objects.create(
            id=uid('invoice_item', i * 10 + k), invoice=invoice, product_service='Music service',
            description=f'Service {k}', quantity=Decimal('1'), unit_price=amount,
            tax_rate=Decimal('7.00'), line_total=amount,
        )
        clock.tick()

    ContractDocument.objects.create(
        id=900000 + i, contract=current, document_type='generated', title=f'Agreement {i}',
        file=f'contract_documents/agreement-{i}.pdf', is_official=True,
        uploaded_by=admin if i % 2 == 0 else None,
    )
    clock.tick()
    return previous, current, draft
