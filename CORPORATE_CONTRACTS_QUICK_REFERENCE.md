# Corporate Contracts - Quick Reference Guide

## Model Fields Quick Reference

### Company Model - New Fields

```python
# Field: parent_company
company.parent_company  # ForeignKey to parent Company (or None)
company.child_companies.all()  # QuerySet of subsidiary companies

# Field: is_corporate_parent
company.is_corporate_parent  # Boolean: True if corporate HQ

# Properties
company.is_subsidiary  # True if has parent_company
company.has_subsidiaries  # True if has child_companies
```

### Contract Model - New Fields

```python
# Field: contract_category (REQUIRED)
contract.contract_category  # 'standard', 'corporate_master', or 'participation'

# Field: master_contract
contract.master_contract  # ForeignKey to master Contract (or None)
contract.participation_agreements.all()  # QuerySet of linked participation agreements

# Fields: Signatories
contract.customer_signatory_name  # Customer signer name
contract.customer_signatory_title  # Customer signer title
contract.bmasia_signatory_name  # BMAsia signer name
contract.bmasia_signatory_title  # BMAsia signer title

# Field: custom_terms
contract.custom_terms  # TextField for master agreement terms
```

### StaticDocument Model - New

```python
# Access static documents
from crm_app.models import StaticDocument

# Get active standard terms
terms_th = StaticDocument.objects.get(
    document_type='standard_terms_th',
    is_active=True
)
terms_intl = StaticDocument.objects.get(
    document_type='standard_terms_intl',
    is_active=True
)

# Fields
document.name  # Display name
document.document_type  # 'standard_terms_th' or 'standard_terms_intl'
document.file  # FileField to PDF
document.version  # Version string (e.g., '1.0')
document.effective_date  # Date this version takes effect
document.is_active  # Boolean
```

## Common Query Patterns

### Corporate Structure Queries

```python
from crm_app.models import Company

# Get all corporate parents
corporate_hqs = Company.objects.filter(is_corporate_parent=True)

# Get all subsidiaries of a parent
hilton_corporate = Company.objects.get(name="Hilton Corporate")
hilton_venues = Company.objects.filter(parent_company=hilton_corporate)
# OR
hilton_venues = hilton_corporate.child_companies.all()

# Get parent of a subsidiary
hilton_pattaya = Company.objects.get(name="Hilton Pattaya")
if hilton_pattaya.is_subsidiary:
    parent = hilton_pattaya.parent_company

# Get all companies without a parent (top-level)
top_level_companies = Company.objects.filter(parent_company__isnull=True)

# Optimized query with parent info
companies = Company.objects.select_related('parent_company').all()
```

### Contract Category Queries

```python
from crm_app.models import Contract

# Get all master agreements
masters = Contract.objects.filter(contract_category='corporate_master')

# Get all participation agreements
participations = Contract.objects.filter(contract_category='participation')

# Get all standard contracts (default)
standards = Contract.objects.filter(contract_category='standard')

# Get participation agreements for a master
master = Contract.objects.get(contract_number='MA-2025-HILTON-001')
participations = master.participation_agreements.all()
# OR
participations = Contract.objects.filter(master_contract=master)

# Optimized query with master info
participations = Contract.objects.select_related('master_contract').filter(
    contract_category='participation'
)
```

### Combined Queries

```python
# Get all master agreements for corporate parents
master_contracts = Contract.objects.filter(
    contract_category='corporate_master',
    company__is_corporate_parent=True
)

# Get all participation agreements for a corporate group
hilton_corporate = Company.objects.get(name="Hilton Corporate")
hilton_participations = Contract.objects.filter(
    contract_category='participation',
    company__parent_company=hilton_corporate
)

# Get master contract for a participation agreement
participation = Contract.objects.get(contract_number='PA-2025-HILTON-PATTAYA')
master = participation.master_contract
```

## Validation Rules

### Contract Category Validation

```python
from crm_app.models import Contract
from django.core.exceptions import ValidationError

# Rule 1: Participation agreements MUST have master_contract
try:
    contract = Contract(
        contract_category='participation',
        master_contract=None  # INVALID!
    )
    contract.clean()  # Raises ValidationError
except ValidationError as e:
    print(e.message_dict['master_contract'])

# Rule 2: master_contract MUST be 'corporate_master' type
standard_contract = Contract.objects.get(contract_category='standard')
try:
    participation = Contract(
        contract_category='participation',
        master_contract=standard_contract  # INVALID! Not a master
    )
    participation.clean()  # Raises ValidationError
except ValidationError as e:
    print(e.message_dict['master_contract'])

# Rule 3: Corporate masters cannot reference another master
try:
    master2 = Contract(
        contract_category='corporate_master',
        master_contract=some_master  # INVALID!
    )
    master2.clean()  # Raises ValidationError
except ValidationError as e:
    print(e.message_dict['master_contract'])

# VALID: Participation with proper master
master = Contract.objects.get(contract_category='corporate_master')
participation = Contract(
    contract_category='participation',
    master_contract=master  # VALID
)
participation.clean()  # No error
```

## Django Admin Usage

### Creating Corporate Structure

1. Create parent company:
   - Go to Companies admin
   - Click "Add Company"
   - Check "Is corporate parent"
   - Fill in details
   - Save

2. Create subsidiary:
   - Go to Companies admin
   - Click "Add Company"
   - Select parent from "Parent company" dropdown
   - Fill in details
   - Save

### Creating Corporate Contracts

1. Create master agreement:
   - Go to Contracts admin
   - Click "Add Contract"
   - Select corporate parent company
   - Set "Contract category" = "Corporate Master Agreement"
   - Fill in signatory details
   - Add custom terms (optional)
   - Save

2. Create participation agreement:
   - Go to Contracts admin
   - Click "Add Contract"
   - Select subsidiary company
   - Set "Contract category" = "Participation Agreement"
   - Select master contract from dropdown
   - Fill in venue-specific details
   - Save

### Managing Static Documents

1. Upload standard terms:
   - Go to Static Documents admin
   - Click "Add Static Document"
   - Enter name (e.g., "Standard Terms - Thailand")
   - Select document type
   - Upload PDF file
   - Set version and effective date
   - Check "Is active"
   - Save

## API Usage (Future - Not Yet Implemented)

### Expected Endpoints

```python
# GET /api/companies/{id}/subsidiaries/
# Returns all child companies

# GET /api/companies/{id}/parent/
# Returns parent company

# GET /api/contracts/?contract_category=corporate_master
# Filter contracts by category

# GET /api/contracts/{id}/participation-agreements/
# Returns all participation agreements for a master

# GET /api/static-documents/?document_type=standard_terms_th
# Get static documents by type
```

## Code Examples

### Creating Corporate Structure (Python Shell)

```python
from crm_app.models import Company, Contract
from datetime import date, timedelta

# Step 1: Create corporate parent
hilton_corporate = Company.objects.create(
    name="Hilton Corporate",
    is_corporate_parent=True,
    country="Hong Kong",
    billing_entity="BMAsia Limited"
)

# Step 2: Create master agreement
master = Contract.objects.create(
    company=hilton_corporate,
    contract_category='corporate_master',
    contract_number='MA-2025-HILTON-001',
    contract_type='Annual',
    start_date=date.today(),
    end_date=date.today() + timedelta(days=365),
    value=1000000,  # $1M master agreement
    currency='USD',
    custom_terms='Volume discount: 15% for 10+ venues\nDedicated support\nQuarterly business reviews',
    customer_signatory_name='John Smith',
    customer_signatory_title='VP of Procurement',
    bmasia_signatory_name='Norbert Platzer',
    bmasia_signatory_title='Managing Director',
    status='Signed'
)

# Step 3: Create subsidiary venues
hilton_pattaya = Company.objects.create(
    name="Hilton Pattaya",
    parent_company=hilton_corporate,
    country="Thailand",
    billing_entity="BMAsia (Thailand) Co., Ltd."
)

hilton_bangkok = Company.objects.create(
    name="Hilton Bangkok",
    parent_company=hilton_corporate,
    country="Thailand",
    billing_entity="BMAsia (Thailand) Co., Ltd."
)

# Step 4: Create participation agreements
participation_pattaya = Contract.objects.create(
    company=hilton_pattaya,
    contract_category='participation',
    master_contract=master,
    contract_number='PA-2025-HILTON-PATTAYA',
    contract_type='Annual',
    start_date=date.today(),
    end_date=date.today() + timedelta(days=365),
    value=50000,  # $50K per venue
    currency='THB',
    status='Signed'
)

participation_bangkok = Contract.objects.create(
    company=hilton_bangkok,
    contract_category='participation',
    master_contract=master,
    contract_number='PA-2025-HILTON-BANGKOK',
    contract_type='Annual',
    start_date=date.today(),
    end_date=date.today() + timedelta(days=365),
    value=75000,  # $75K per venue
    currency='THB',
    status='Signed'
)

# Step 5: Verify structure
print(f"Parent: {hilton_corporate.name}")
print(f"Is corporate parent: {hilton_corporate.is_corporate_parent}")
print(f"Subsidiaries: {hilton_corporate.child_companies.count()}")
for venue in hilton_corporate.child_companies.all():
    print(f"  - {venue.name} (is_subsidiary={venue.is_subsidiary})")

print(f"\nMaster: {master.contract_number}")
print(f"Participation agreements: {master.participation_agreements.count()}")
for pa in master.participation_agreements.all():
    print(f"  - {pa.contract_number} for {pa.company.name}")
```

### Querying Corporate Data

```python
from crm_app.models import Company, Contract
from django.db.models import Sum, Count

# Get all corporate groups
corporate_groups = Company.objects.filter(
    is_corporate_parent=True
).prefetch_related('child_companies')

for parent in corporate_groups:
    venue_count = parent.child_companies.count()
    total_value = Contract.objects.filter(
        company__in=parent.child_companies.all()
    ).aggregate(Sum('value'))['value__sum'] or 0
    
    print(f"{parent.name}: {venue_count} venues, ${total_value:,.2f} total value")

# Get master agreements with participation counts
masters = Contract.objects.filter(
    contract_category='corporate_master'
).annotate(
    participation_count=Count('participation_agreements')
)

for master in masters:
    print(f"{master.contract_number}: {master.participation_count} participations")

# Find all contracts related to a corporate group
hilton_corporate = Company.objects.get(name="Hilton Corporate")
all_hilton_contracts = Contract.objects.filter(
    company__in=[hilton_corporate] + list(hilton_corporate.child_companies.all())
)
```

## Common Pitfalls

### 1. Forgetting to Call clean()

```python
# WRONG - validation won't run
contract = Contract(contract_category='participation')
contract.save()  # Saves without validation!

# RIGHT - validation runs
contract = Contract(contract_category='participation')
contract.full_clean()  # Validates before save
contract.save()

# RIGHT - Django admin does this automatically
# No need to call clean() manually in admin
```

### 2. Circular Parent References

```python
# WRONG - creates circular reference
company_a.parent_company = company_b
company_a.save()
company_b.parent_company = company_a  # BAD!
company_b.save()

# Prevent this in your code:
if new_parent and new_parent.parent_company == self:
    raise ValidationError("Cannot create circular parent relationship")
```

### 3. Deleting Parent Companies

```python
# When parent is deleted, children's parent_company becomes NULL (SET_NULL)
parent.delete()
# child.parent_company is now None
# child.is_subsidiary is now False

# Consider using a "soft delete" flag instead:
parent.is_active = False
parent.save()
```

### 4. Master Contract Must Exist Before Participation

```python
# WRONG - master doesn't exist yet
participation.master_contract = master  # master not saved!
participation.save()

# RIGHT - save master first
master.save()
participation.master_contract = master
participation.save()
```

## Performance Tips

### Use select_related() for Foreign Keys

```python
# SLOW - N+1 queries
companies = Company.objects.all()
for company in companies:
    if company.parent_company:  # Hits database each time!
        print(company.parent_company.name)

# FAST - 1 query with JOIN
companies = Company.objects.select_related('parent_company').all()
for company in companies:
    if company.parent_company:
        print(company.parent_company.name)
```

### Use prefetch_related() for Reverse Foreign Keys

```python
# SLOW - N+1 queries
parents = Company.objects.filter(is_corporate_parent=True)
for parent in parents:
    for child in parent.child_companies.all():  # Hits database each time!
        print(child.name)

# FAST - 2 queries total
parents = Company.objects.filter(
    is_corporate_parent=True
).prefetch_related('child_companies')
for parent in parents:
    for child in parent.child_companies.all():
        print(child.name)
```

### Index Usage

```python
# These queries use indexes (FAST):
Company.objects.filter(parent_company=some_company)
Contract.objects.filter(contract_category='corporate_master')
Contract.objects.filter(master_contract=some_master)

# These queries don't use indexes (slower):
Company.objects.filter(name__icontains='Hilton')  # Text search
Contract.objects.exclude(contract_category='standard')  # Negation
```

## Testing Checklist

When implementing features using these models:

- [ ] Test creating corporate parent + subsidiaries
- [ ] Test creating master + participation agreements
- [ ] Test validation (participation without master should fail)
- [ ] Test querying corporate structures
- [ ] Test deleting parent (children should survive)
- [ ] Test deleting master (participations should survive with NULL)
- [ ] Test admin interface for all new fields
- [ ] Test performance with select_related/prefetch_related
- [ ] Test edge cases (circular references, etc.)

---

**Last Updated**: 2025-12-13
**Migration**: 0040_add_corporate_contracts.py
**Phase**: 1 (Database Models)
