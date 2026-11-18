"""A deterministic dataset for the Today page (/action-center/) and /dashboard/stats/.

Every name is invented; keys, timestamps and the values each section sorts by are unique,
so the item order never depends on how the database breaks ties. READ_AT is a Wednesday
morning in Bangkok; the records sit around it: overdue, due today and tomorrow, due this
week, expiring, stale, and contracts that started this month and in the trend months.
Companies never get a Soundtrack account id (a post-save signal would call the API).
"""
import uuid
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from freezegun import freeze_time

from crm_app.models import Company, Contact, Contract, Invoice, Opportunity, Task, User

READ_AT = '2026-11-18T03:00:00Z'  # 10:00 in Bangkok
_BUILD_AT = datetime(2026, 9, 1, 2, 0, tzinfo=dt_timezone.utc)
_KINDS = {'user': 31, 'company': 32, 'contact': 33, 'task': 34, 'invoice': 35,
          'opportunity': 36, 'contract': 37}


def uid(kind, number):
    return uuid.UUID(int=(_KINDS[kind] << 96) | number)


def _at(day, hour=9, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=dt_timezone.utc)


def build_today_dataset(n_companies, first=0):
    """Create companies first .. first + n_companies - 1; returns (admin, sales).

    Call it again with a higher `first` to add more companies to the same dataset.
    """
    with freeze_time(_BUILD_AT + timedelta(hours=first)) as frozen:
        def tick():
            frozen.tick(timedelta(seconds=1))

        admin, _ = User.objects.get_or_create(
            id=uid('user', 1),
            defaults=dict(username='today-admin', role='Admin', first_name='Avery', last_name='Admin'))
        sales, _ = User.objects.get_or_create(
            id=uid('user', 2),
            defaults=dict(username='today-sales', role='Sales', first_name='Sam', last_name='Seller'))
        tick()
        for i in range(first, first + n_companies):
            _company(i, admin, sales, tick)
    return admin, sales


def _company(i, admin, sales, tick):
    thai = i % 2 == 1
    company = Company.objects.create(
        id=uid('company', i), name=f'Todayco {i:03d}',
        billing_entity='BMAsia (Thailand) Co., Ltd.' if thai else 'BMAsia Limited',
    )
    tick()
    contacts = []
    for k, letter in enumerate('ab'):
        if i % 4 == 2:
            break  # no contacts at all
        contacts.append(Contact.objects.create(
            id=uid('contact', i * 10 + k), company=company, name=f'Contact {i:03d} {"ba"[k]}',
            email=f'today{i:03d}{letter}@example.com', phone='+66 81 000 0000' if k else '',
            is_primary=False, is_active=True, unsubscribe_token=f'today-{i}-{k}',
        ))
        tick()
    if i % 4 == 0:  # one active primary
        Contact.objects.filter(pk=contacts[0].pk).update(is_primary=True)
    elif i % 4 == 1:  # an inactive primary only: the first active contact by name is used
        Contact.objects.filter(pk=contacts[0].pk).update(is_primary=True, is_active=False)
    elif i % 4 == 3:  # two active primaries (imported data): the first by name wins
        Contact.objects.filter(pk__in=[c.pk for c in contacts]).update(is_primary=True)
    owner = sales if i % 2 == 0 else admin

    today = date(2026, 11, 18)
    task_specs = [
        ('overdue', _at(today - timedelta(days=3 + i), 2, i), 'To Do'),
        ('overdue-done', _at(today - timedelta(days=2), 3, i), 'Done'),
        ('today', _at(today, 8, i), 'In Progress'),       # 15:00 Bangkok
        ('tomorrow', _at(today + timedelta(days=1), 4, i), 'To Do'),
        ('week', _at(today + timedelta(days=3 + i % 4), 5, i), 'To Do'),
        ('cancelled', _at(today - timedelta(days=4), 6, i), 'Cancelled'),
    ]
    for k, (label, due, status) in enumerate(task_specs):
        Task.objects.create(
            id=uid('task', i * 10 + k), company=company, title=f'Task {i:03d} {label}',
            assigned_to=sales if (i + k) % 2 == 0 else admin, created_by=admin,
            priority=['Low', 'Medium', 'High', 'Urgent'][(i + k) % 4], status=status,
            task_type=['Call', 'Email', 'Follow-up'][k % 3], due_date=due,
            related_contact=contacts[-1] if contacts and k == 0 and i % 3 == 0 else None,
        )
        tick()

    for k, (status, due) in enumerate([
        ('Sent', today - timedelta(days=10 + i)),
        ('Overdue', today - timedelta(days=40 + i)),
        ('Sent', today + timedelta(days=i % 6)),
        ('Paid', today - timedelta(days=5)),
        ('Draft', today - timedelta(days=7)),
    ]):
        Invoice.objects.create(
            id=uid('invoice', i * 10 + k), company=company,
            invoice_number=f'{"TH" if thai else "HK"}-INV8{i:04d}{k}', status=status,
            issue_date=date(2026, 8, 1) + timedelta(days=i * 5 + k), due_date=due,
            amount=Decimal(f'{200 + i}.10'), tax_amount=Decimal('14.01'),
            discount_amount=Decimal('0.00'), total_amount=Decimal('0'),
            currency='THB' if thai else 'USD',
        )
        tick()

    # Stale (follow-up in the past; no follow-up and untouched for 14 days), upcoming, won.
    for k, (stage, follow_up, active) in enumerate([
        ('Contacted', today - timedelta(days=2 + i), True),
        ('Quotation Sent', None, True),
        ('Contract Sent', today + timedelta(days=1 + i % 10), True),
        ('Won', today - timedelta(days=1), True),
        ('Lost', None, True),
        ('Contacted', today + timedelta(days=3), False),
    ]):
        Opportunity.objects.create(
            id=uid('opportunity', i * 10 + k), company=company, name=f'Deal {i:03d} {k}',
            stage=stage, follow_up_date=follow_up, is_active=active, owner=owner if k else None,
            expected_value=Decimal(f'{5000 + i * 10 + k}.00') if k != 1 else None,
            actual_close_date=today - timedelta(days=3 + k) if stage in ('Won', 'Lost') else None,
        )
        tick()

    region = 'TH' if thai else 'HK'
    earlier = Contract.objects.create(
        id=uid('contract', i * 10), company=company, contract_number=f'{region}-CT8{i:04d}0',
        status='Renewed', is_active=False, start_date=date(2024, 1, 1) + timedelta(days=i),
        end_date=date(2025, 1, 1) + timedelta(days=i), value=Decimal(f'{100 + i}.00'),
        currency='THB' if thai else 'USD',
    )
    tick()
    month_starts = [date(2026, 11, 2), date(2026, 10, 3), date(2026, 9, 4), date(2026, 8, 5),
                    date(2026, 7, 6), date(2026, 6, 7)]
    for k, start in enumerate(month_starts):
        # Lifecycle: explicit, inferred from renewed_from, inferred from an earlier contract
        # of the company, or new (company 0's November contract has no earlier one).
        lifecycle = ['', 'addon', '', 'renewal', '', ''][k]
        Contract.objects.create(
            id=uid('contract', i * 10 + 1 + k), company=company,
            contract_number=f'{region}-CT8{i:04d}{1 + k}', status='Active', is_active=True,
            start_date=start + timedelta(days=i % 20),
            end_date=today + timedelta(days=5 + i * 3 + k) if k < 2 else date(2027, 6, 1),
            value=Decimal(f'{1000 + i * 7 + k}.25'), currency='THB' if thai else 'USD',
            lifecycle_type=lifecycle, renewed_from=earlier if k == 2 and i % 2 else None,
            customer_signatory_name=f'Signer {i}' if i % 2 == 0 and k == 0 else '',
        )
        tick()
    if i == 0:
        Contract.objects.filter(pk=uid('contract', 0)).delete()
    # Churn: ended this month (Expired) and last month (Cancelled), not renewed. Company 0
    # has none, so its oldest contract (June) counts as new business.
    for k, (status, end) in enumerate([] if i == 0 else [('Expired', date(2026, 11, 3)),
                                       ('Cancelled', date(2026, 10, 9))]):
        Contract.objects.create(
            id=uid('contract', i * 10 + 8 + k), company=company,
            contract_number=f'{region}-CT8{i:04d}{8 + k}', status=status, is_active=False,
            start_date=date(2025, 11, 3) + timedelta(days=k * 30 + i),
            end_date=end + timedelta(days=i % 10), value=Decimal(f'{300 + i}.50'),
            currency='THB' if thai else 'USD',
        )
        tick()
