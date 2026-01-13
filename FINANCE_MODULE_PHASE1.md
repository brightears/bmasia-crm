# Finance & Accounting Module - Phase 1: Revenue Tracking

## Overview
Phase 1 of the Finance Module implements comprehensive revenue tracking capabilities for BMAsia CRM, enabling detailed monitoring of contract lifecycle, monthly revenue snapshots, targets, and revenue-impacting events.

## Implementation Date
January 13, 2026

## Database Models Implemented

### 1. Contract Model Enhancements
**File**: `/crm_app/models.py` (lines 748-770)

Added three new fields to track contract revenue lifecycle:

```python
lifecycle_type = models.CharField(
    max_length=20,
    choices=LIFECYCLE_TYPE_CHOICES,
    blank=True,
    help_text="Revenue type classification for finance tracking"
)

lifecycle_type_manually_set = models.BooleanField(
    default=False,
    help_text="If true, lifecycle_type was manually set and won't be auto-updated"
)

lifecycle_effective_date = models.DateField(
    null=True,
    blank=True,
    help_text="Date when this lifecycle type became effective"
)
```

**Lifecycle Type Choices**:
- `new` - New Contract
- `renewal` - Renewal
- `addon` - Add-on (Zone Addition)
- `churn` - Canceled/Churned

**Purpose**: Enables automatic classification of contracts for revenue reporting and allows manual overrides when business logic differs from automation.

**Index Added**: `['lifecycle_type', 'lifecycle_effective_date']` for optimized queries.

---

### 2. MonthlyRevenueSnapshot Model
**File**: `/crm_app/models.py` (lines 3412-3501)

Tracks actual monthly revenue metrics by category, currency, and billing entity.

**Key Fields**:
- `year`, `month` - Time period
- `category` - Revenue type (new/renewal/addon/churn)
- `currency` - USD, THB, EUR, GBP
- `billing_entity` - BMAsia HK vs BMAsia Thailand
- `contract_count` - Number of contracts in category
- `contracted_value` - Total contract value
- `cash_received` - Actual cash collected
- `is_manually_overridden` - Flag for manual adjustments
- `override_reason` - Audit trail for manual changes

**Unique Constraint**: `[year, month, category, currency, billing_entity]`
- Ensures one snapshot per combination
- Prevents duplicate entries

**Indexes** (4 total):
1. `[year, month]` - Time-based queries
2. `[category, year, month]` - Category filtering
3. `[billing_entity, year, month]` - Entity-specific reports
4. `[currency, year, month]` - Currency-specific analysis

**Use Cases**:
- Monthly financial dashboards
- Revenue trend analysis by category
- Cash flow vs. contracted value comparison
- Multi-entity and multi-currency reporting

---

### 3. MonthlyRevenueTarget Model
**File**: `/crm_app/models.py` (lines 3504-3576)

Stores management-set revenue targets for forecasting and goal tracking.

**Key Fields**:
- `year`, `month` - Target period
- `category` - Revenue category
- `currency` - Target currency
- `billing_entity` - Entity-specific targets
- `target_contract_count` - Goal number of contracts
- `target_revenue` - Contracted revenue goal
- `target_cash_flow` - Cash collection goal
- `created_by` - User who set the target

**Unique Constraint**: `[year, month, category, currency, billing_entity]`

**Indexes** (3 total):
1. `[year, month]` - Time-based queries
2. `[category, year, month]` - Category filtering
3. `[billing_entity, year, month]` - Entity filtering

**Use Cases**:
- Target vs. actual comparison dashboards
- Sales performance tracking
- Budget forecasting
- Entity-level goal management

---

### 4. ContractRevenueEvent Model
**File**: `/crm_app/models.py` (lines 3579-3675)

Event log for all revenue-impacting contract changes with detailed audit trail.

**Event Types**:
- `new_contract` - New Contract Signed
- `renewal` - Contract Renewed
- `addon_zones` - Zones Added
- `removal_zones` - Zones Removed
- `value_increase` - Value Increased
- `value_decrease` - Value Decreased
- `payment_received` - Payment Received
- `payment_overdue` - Payment Overdue
- `churn` - Contract Churned/Canceled
- `reactivation` - Contract Reactivated

**Key Fields**:
- `contract` - FK to Contract
- `event_type` - Type of event (see above)
- `event_date` - When event occurred
- `contract_value_change` - Delta in total contract value
- `monthly_value_change` - Delta in MRR
- `zone_count_change` - Delta in zone count
- `expected_payment_date` - When payment was due
- `actual_payment_date` - When payment received
- `payment_amount` - Amount paid
- `created_by` - User who logged event

**Indexes** (4 total):
1. `[contract, event_date]` - Contract timeline queries
2. `[event_type, event_date]` - Event-specific analysis
3. `[event_date]` - Chronological queries
4. `[contract, event_type]` - Contract event filtering

**Use Cases**:
- Detailed revenue change audit trail
- Payment tracking and overdue alerts
- Zone expansion/contraction analysis
- Revenue recognition timing
- Customer lifetime value calculations

---

## Migration Details

**Migration File**: `crm_app/migrations/0048_finance_revenue_tracking.py`

**Operations**:
1. Create `MonthlyRevenueSnapshot` table
2. Create `MonthlyRevenueTarget` table
3. Create `ContractRevenueEvent` table
4. Add 3 lifecycle fields to `Contract` table
5. Create 12 database indexes for query optimization
6. Add 2 unique constraints for data integrity
7. Add foreign key relationships to `Contract` and `User`

**Database Impact**:
- **New Tables**: 3
- **Modified Tables**: 1 (Contract)
- **New Indexes**: 12
- **New Constraints**: 2 unique_together

**Migration Status**: Generated, not yet applied

---

## Performance Optimizations

### Indexing Strategy
All models include strategic indexes for common query patterns:

1. **Time-based queries** - `[year, month]` indexes
2. **Category filtering** - `[category, year, month]` indexes
3. **Entity separation** - `[billing_entity, year, month]` indexes
4. **Contract timeline** - `[contract, event_date]` indexes
5. **Event analysis** - `[event_type, event_date]` indexes

### Query Performance Expectations
- Monthly dashboard queries: <50ms (indexed)
- Contract event history: <100ms (indexed by contract)
- Year-over-year comparisons: <200ms (indexed by year/month)
- Multi-currency reports: <150ms (indexed by currency)

---

## Data Integrity Features

### Unique Constraints
1. **MonthlyRevenueSnapshot**: One snapshot per `[year, month, category, currency, billing_entity]`
2. **MonthlyRevenueTarget**: One target per `[year, month, category, currency, billing_entity]`

### Foreign Key Protection
- `ContractRevenueEvent.contract` - CASCADE on delete (events deleted with contract)
- `ContractRevenueEvent.created_by` - SET_NULL on delete (preserve events if user deleted)
- `MonthlyRevenueTarget.created_by` - SET_NULL on delete

### Audit Trail
- All models inherit from `TimestampedModel` (created_at, updated_at)
- `created_by` fields track who set targets or logged events
- Manual override tracking with `is_manually_overridden` and `override_reason`

---

## Next Steps (Phase 2+)

### Immediate Tasks
1. Run migration on development database
2. Test data insertion for all models
3. Create Django admin interfaces
4. Build API serializers and viewsets

### Future Phases
- **Phase 2**: Payment tracking & overdue alerts
- **Phase 3**: Expense tracking
- **Phase 4**: Profitability analysis
- **Phase 5**: Financial reporting dashboards
- **Phase 6**: Automated revenue recognition

---

## Technical Notes

### Decimal Precision
- Revenue fields: `max_digits=15, decimal_places=2` (up to 13 digits + 2 decimals)
- Supports values up to 9,999,999,999,999.99 (9.9 trillion)
- Sufficient for all realistic BMAsia contract values

### Currency Support
Current: USD, THB, EUR, GBP
Future: Easily extensible by adding to `CURRENCY_CHOICES`

### Billing Entity Support
Current: BMAsia HK, BMAsia Thailand
Architecture supports adding more entities if needed

### TimestampedModel Base Class
All models automatically track:
- `created_at` - When record was created
- `updated_at` - When record was last modified

---

## Files Modified

1. `/crm_app/models.py`
   - Contract model: Added lines 748-770 (lifecycle fields)
   - Contract Meta: Added index line 778
   - MonthlyRevenueSnapshot: Lines 3412-3501
   - MonthlyRevenueTarget: Lines 3504-3576
   - ContractRevenueEvent: Lines 3579-3675

2. `/crm_app/migrations/0048_finance_revenue_tracking.py` (NEW)
   - 170 lines
   - 12 indexes created
   - 2 unique constraints added
   - 3 new tables, 1 modified table

---

## Database Schema Summary

### Contract (Extended)
```
id (UUID, PK)
... (existing 40+ fields)
lifecycle_type (VARCHAR 20)
lifecycle_type_manually_set (BOOLEAN)
lifecycle_effective_date (DATE NULL)
```

### MonthlyRevenueSnapshot
```
id (UUID, PK)
year (INT)
month (INT)
category (VARCHAR 20)
currency (VARCHAR 3)
billing_entity (VARCHAR 20)
contract_count (INT)
contracted_value (DECIMAL 15,2)
cash_received (DECIMAL 15,2)
is_manually_overridden (BOOLEAN)
override_reason (TEXT)
notes (TEXT)
created_at (DATETIME)
updated_at (DATETIME)

UNIQUE (year, month, category, currency, billing_entity)
```

### MonthlyRevenueTarget
```
id (UUID, PK)
year (INT)
month (INT)
category (VARCHAR 20)
currency (VARCHAR 3)
billing_entity (VARCHAR 20)
target_contract_count (INT)
target_revenue (DECIMAL 15,2)
target_cash_flow (DECIMAL 15,2)
notes (TEXT)
created_by (UUID, FK -> User)
created_at (DATETIME)
updated_at (DATETIME)

UNIQUE (year, month, category, currency, billing_entity)
```

### ContractRevenueEvent
```
id (UUID, PK)
contract (UUID, FK -> Contract)
event_type (VARCHAR 30)
event_date (DATE)
contract_value_change (DECIMAL 12,2)
monthly_value_change (DECIMAL 12,2)
zone_count_change (INT)
expected_payment_date (DATE NULL)
actual_payment_date (DATE NULL)
payment_amount (DECIMAL 12,2 NULL)
notes (TEXT)
created_by (UUID, FK -> User)
created_at (DATETIME)
updated_at (DATETIME)
```

---

## Migration Command

To apply this migration to development database:
```bash
cd /path/to/bmasia-crm
source env/bin/activate
python manage.py migrate
```

To apply to production (Render):
```bash
# This will be handled automatically on next deployment
# Or manually via Render dashboard → Run command → python manage.py migrate
```

---

## Testing Checklist

- [ ] Migration applies cleanly to development database
- [ ] All indexes created successfully
- [ ] Unique constraints enforced
- [ ] Foreign key relationships work
- [ ] TimestampedModel fields auto-populate
- [ ] Django admin can create/edit all models
- [ ] API endpoints functional (Phase 2)
- [ ] Data validation works (choices, required fields)
- [ ] Manual override workflow tested
- [ ] Query performance meets expectations

---

**Created by**: Claude Code (database-optimizer)
**Date**: January 13, 2026
**BMAsia CRM Version**: Phase 1 - Finance Module
