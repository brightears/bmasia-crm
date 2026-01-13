# Finance Module - Usage Examples

## Quick Start Guide

### 1. Setting Contract Lifecycle Type

```python
from crm_app.models import Contract

# Auto-classification (system determines based on business logic)
contract = Contract.objects.get(contract_number='C-2026-001')
contract.lifecycle_type = 'new'
contract.lifecycle_effective_date = contract.start_date
contract.save()

# Manual classification (prevents auto-updates)
contract = Contract.objects.get(contract_number='C-2026-002')
contract.lifecycle_type = 'renewal'
contract.lifecycle_type_manually_set = True
contract.lifecycle_effective_date = contract.start_date
contract.save()
```

### 2. Creating Monthly Revenue Snapshots

```python
from crm_app.models import MonthlyRevenueSnapshot
from decimal import Decimal

# Create snapshot for January 2026 new contracts (Thailand entity, THB)
snapshot = MonthlyRevenueSnapshot.objects.create(
    year=2026,
    month=1,
    category='new',
    currency='THB',
    billing_entity='bmasia_th',
    contract_count=5,
    contracted_value=Decimal('500000.00'),
    cash_received=Decimal('450000.00'),
    notes='Strong start to the year with 5 new hotels'
)

# Update with manual override
snapshot.contracted_value = Decimal('520000.00')
snapshot.is_manually_overridden = True
snapshot.override_reason = 'Added late-reported contract C-2026-005'
snapshot.save()
```

### 3. Setting Revenue Targets

```python
from crm_app.models import MonthlyRevenueTarget, User
from decimal import Decimal

user = User.objects.get(username='admin')

# Set Q1 2026 targets for new contracts (HK entity, USD)
for month in [1, 2, 3]:
    target = MonthlyRevenueTarget.objects.create(
        year=2026,
        month=month,
        category='new',
        currency='USD',
        billing_entity='bmasia_hk',
        target_contract_count=3,
        target_revenue=Decimal('75000.00'),
        target_cash_flow=Decimal('70000.00'),
        created_by=user,
        notes=f'Q1 2026 new business target - Month {month}'
    )
```

### 4. Logging Revenue Events

```python
from crm_app.models import ContractRevenueEvent, Contract
from decimal import Decimal
from datetime import date

contract = Contract.objects.get(contract_number='C-2026-001')

# Log new contract signed
event = ContractRevenueEvent.objects.create(
    contract=contract,
    event_type='new_contract',
    event_date=date(2026, 1, 15),
    contract_value_change=Decimal('100000.00'),
    monthly_value_change=Decimal('8333.33'),
    zone_count_change=4,
    expected_payment_date=date(2026, 2, 1),
    notes='Hilton Pattaya - 4 zones',
    created_by=user
)

# Log payment received
payment_event = ContractRevenueEvent.objects.create(
    contract=contract,
    event_type='payment_received',
    event_date=date(2026, 2, 1),
    expected_payment_date=date(2026, 2, 1),
    actual_payment_date=date(2026, 2, 1),
    payment_amount=Decimal('100000.00'),
    notes='Full payment received on time',
    created_by=user
)

# Log zone addition (add-on)
addon_event = ContractRevenueEvent.objects.create(
    contract=contract,
    event_type='addon_zones',
    event_date=date(2026, 3, 1),
    contract_value_change=Decimal('25000.00'),
    monthly_value_change=Decimal('2083.33'),
    zone_count_change=1,
    notes='Added pool area zone',
    created_by=user
)
```

## Common Queries

### Get Monthly Revenue Summary

```python
from crm_app.models import MonthlyRevenueSnapshot
from django.db.models import Sum

# Get all snapshots for January 2026
jan_snapshots = MonthlyRevenueSnapshot.objects.filter(
    year=2026,
    month=1
)

# Get total revenue by category
summary = jan_snapshots.values('category').annotate(
    total_contracts=Sum('contract_count'),
    total_revenue=Sum('contracted_value'),
    total_cash=Sum('cash_received')
)

for item in summary:
    print(f"{item['category']}: {item['total_contracts']} contracts, "
          f"{item['total_revenue']} contracted, {item['total_cash']} collected")
```

### Compare Targets vs Actuals

```python
from crm_app.models import MonthlyRevenueSnapshot, MonthlyRevenueTarget

# Get January 2026 new contracts (Thailand entity)
actual = MonthlyRevenueSnapshot.objects.get(
    year=2026, month=1, category='new', 
    currency='THB', billing_entity='bmasia_th'
)
target = MonthlyRevenueTarget.objects.get(
    year=2026, month=1, category='new',
    currency='THB', billing_entity='bmasia_th'
)

# Calculate variance
contract_variance = actual.contract_count - target.target_contract_count
revenue_variance = actual.contracted_value - target.target_revenue
cash_variance = actual.cash_received - target.target_cash_flow

print(f"Contracts: {actual.contract_count} vs {target.target_contract_count} "
      f"({'+'if contract_variance >= 0 else ''}{contract_variance})")
print(f"Revenue: {actual.contracted_value} vs {target.target_revenue} "
      f"({'+'if revenue_variance >= 0 else ''}{revenue_variance})")
```

### Get Contract Event Timeline

```python
from crm_app.models import ContractRevenueEvent, Contract

contract = Contract.objects.get(contract_number='C-2026-001')

# Get all events for this contract
events = ContractRevenueEvent.objects.filter(
    contract=contract
).order_by('event_date')

print(f"Event timeline for {contract.contract_number}:")
for event in events:
    print(f"{event.event_date}: {event.get_event_type_display()}")
    if event.contract_value_change != 0:
        print(f"  Value change: {event.contract_value_change}")
    if event.zone_count_change != 0:
        print(f"  Zone change: {event.zone_count_change}")
```

### Get Overdue Payments

```python
from crm_app.models import ContractRevenueEvent
from datetime import date

# Find payments that are overdue (expected date passed, no actual payment date)
overdue = ContractRevenueEvent.objects.filter(
    event_type='payment_overdue',
    expected_payment_date__lt=date.today(),
    actual_payment_date__isnull=True
).select_related('contract', 'contract__company')

print(f"Found {overdue.count()} overdue payments:")
for payment in overdue:
    days_overdue = (date.today() - payment.expected_payment_date).days
    print(f"{payment.contract.company.name}: {payment.payment_amount} "
          f"(overdue by {days_overdue} days)")
```

### Get New vs Renewal Revenue Breakdown

```python
from crm_app.models import MonthlyRevenueSnapshot
from django.db.models import Sum, Count

# Get 2026 revenue by category (all months, all entities)
breakdown = MonthlyRevenueSnapshot.objects.filter(
    year=2026
).values('category').annotate(
    total_contracts=Sum('contract_count'),
    total_revenue=Sum('contracted_value'),
    months_tracked=Count('id')
)

print("2026 Revenue Breakdown:")
for item in breakdown:
    avg_monthly = item['total_revenue'] / item['months_tracked']
    print(f"{item['category'].upper()}: {item['total_contracts']} contracts, "
          f"{item['total_revenue']} total, {avg_monthly:.2f} avg/month")
```

### Filter by Billing Entity

```python
from crm_app.models import MonthlyRevenueSnapshot
from django.db.models import Sum

# Compare Thailand vs HK performance for January 2026
for entity in ['bmasia_th', 'bmasia_hk']:
    stats = MonthlyRevenueSnapshot.objects.filter(
        year=2026,
        month=1,
        billing_entity=entity
    ).aggregate(
        total_contracts=Sum('contract_count'),
        total_revenue=Sum('contracted_value'),
        total_cash=Sum('cash_received')
    )
    
    entity_name = 'Thailand' if entity == 'bmasia_th' else 'Hong Kong'
    print(f"\n{entity_name} Performance (Jan 2026):")
    print(f"  Contracts: {stats['total_contracts']}")
    print(f"  Revenue: {stats['total_revenue']}")
    print(f"  Cash: {stats['total_cash']}")
```

## Bulk Operations

### Create Year of Targets

```python
from crm_app.models import MonthlyRevenueTarget
from decimal import Decimal

user = User.objects.get(username='admin')

# Create targets for all 12 months of 2026 (new contracts, Thailand)
targets_data = {
    'year': 2026,
    'category': 'new',
    'currency': 'THB',
    'billing_entity': 'bmasia_th',
    'created_by': user
}

# Quarterly ramp-up pattern
quarterly_targets = [
    {'count': 3, 'revenue': 150000, 'cash': 140000},  # Q1
    {'count': 4, 'revenue': 200000, 'cash': 190000},  # Q2
    {'count': 5, 'revenue': 250000, 'cash': 240000},  # Q3
    {'count': 6, 'revenue': 300000, 'cash': 290000},  # Q4
]

for quarter_idx, quarter_targets in enumerate(quarterly_targets):
    for month_in_quarter in range(3):
        month = quarter_idx * 3 + month_in_quarter + 1
        MonthlyRevenueTarget.objects.create(
            month=month,
            target_contract_count=quarter_targets['count'],
            target_revenue=Decimal(str(quarter_targets['revenue'])),
            target_cash_flow=Decimal(str(quarter_targets['cash'])),
            notes=f'Q{quarter_idx + 1} 2026 target',
            **targets_data
        )

print("Created 12 months of targets for 2026")
```

### Bulk Update Lifecycle Types

```python
from crm_app.models import Contract
from django.utils import timezone

# Auto-classify all contracts based on simple logic
contracts = Contract.objects.filter(lifecycle_type='')

for contract in contracts:
    # Example logic - customize based on business rules
    if contract.status == 'Active' and not hasattr(contract, 'previous_contract'):
        contract.lifecycle_type = 'new'
        contract.lifecycle_effective_date = contract.start_date
    elif contract.status == 'Renewed':
        contract.lifecycle_type = 'renewal'
        contract.lifecycle_effective_date = contract.start_date
    elif contract.status == 'Terminated':
        contract.lifecycle_type = 'churn'
        contract.lifecycle_effective_date = contract.end_date
    
    contract.save(update_fields=['lifecycle_type', 'lifecycle_effective_date'])

print(f"Updated {contracts.count()} contracts with lifecycle types")
```

## Django Admin Integration Examples

```python
# In crm_app/admin.py

from django.contrib import admin
from .models import MonthlyRevenueSnapshot, MonthlyRevenueTarget, ContractRevenueEvent

@admin.register(MonthlyRevenueSnapshot)
class MonthlyRevenueSnapshotAdmin(admin.ModelAdmin):
    list_display = ['year', 'month', 'category', 'currency', 'billing_entity', 
                    'contract_count', 'contracted_value', 'cash_received', 
                    'is_manually_overridden']
    list_filter = ['year', 'category', 'currency', 'billing_entity', 
                   'is_manually_overridden']
    search_fields = ['notes']
    ordering = ['-year', '-month', 'category']
    
    fieldsets = (
        ('Period', {
            'fields': ('year', 'month')
        }),
        ('Classification', {
            'fields': ('category', 'currency', 'billing_entity')
        }),
        ('Metrics', {
            'fields': ('contract_count', 'contracted_value', 'cash_received')
        }),
        ('Manual Override', {
            'fields': ('is_manually_overridden', 'override_reason'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )

@admin.register(MonthlyRevenueTarget)
class MonthlyRevenueTargetAdmin(admin.ModelAdmin):
    list_display = ['year', 'month', 'category', 'currency', 'billing_entity',
                    'target_contract_count', 'target_revenue', 'target_cash_flow',
                    'created_by']
    list_filter = ['year', 'category', 'currency', 'billing_entity']
    ordering = ['-year', '-month', 'category']
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ContractRevenueEvent)
class ContractRevenueEventAdmin(admin.ModelAdmin):
    list_display = ['contract', 'event_type', 'event_date', 
                    'contract_value_change', 'monthly_value_change',
                    'zone_count_change', 'created_by']
    list_filter = ['event_type', 'event_date']
    search_fields = ['contract__contract_number', 'contract__company__name', 'notes']
    ordering = ['-event_date', '-created_at']
    raw_id_fields = ['contract']
    
    fieldsets = (
        ('Event Details', {
            'fields': ('contract', 'event_type', 'event_date')
        }),
        ('Financial Impact', {
            'fields': ('contract_value_change', 'monthly_value_change', 
                      'zone_count_change')
        }),
        ('Payment Tracking', {
            'fields': ('expected_payment_date', 'actual_payment_date', 
                      'payment_amount'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
```

## Performance Tips

### Use select_related for Foreign Keys

```python
# Efficient: Single query with JOIN
events = ContractRevenueEvent.objects.select_related(
    'contract', 'contract__company', 'created_by'
).filter(event_date__year=2026)

# Inefficient: N+1 queries
events = ContractRevenueEvent.objects.filter(event_date__year=2026)
for event in events:
    print(event.contract.company.name)  # Separate query each time!
```

### Use Aggregation at Database Level

```python
from django.db.models import Sum, Count, Avg

# Efficient: Aggregation in database
stats = MonthlyRevenueSnapshot.objects.filter(
    year=2026
).aggregate(
    total_contracts=Sum('contract_count'),
    total_revenue=Sum('contracted_value'),
    avg_cash_collected=Avg('cash_received'),
    months_tracked=Count('id')
)

# Inefficient: Python-side calculation
snapshots = MonthlyRevenueSnapshot.objects.filter(year=2026)
total = sum(s.contracted_value for s in snapshots)  # Loads all records!
```

### Bulk Create for Performance

```python
from crm_app.models import ContractRevenueEvent

# Efficient: Single INSERT with multiple rows
events_to_create = []
for contract in contracts:
    events_to_create.append(
        ContractRevenueEvent(
            contract=contract,
            event_type='renewal',
            event_date=contract.start_date,
            contract_value_change=contract.value,
            created_by=user
        )
    )

ContractRevenueEvent.objects.bulk_create(events_to_create)

# Inefficient: Multiple INSERTs
for contract in contracts:
    ContractRevenueEvent.objects.create(...)  # Separate query!
```

---

**Note**: All code examples assume proper imports and error handling. 
In production, always wrap database operations in try/except blocks and 
use Django transactions for data consistency.
