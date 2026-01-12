# Corporate Contracts - Phase 1 Implementation Summary

**Date**: 2025-12-13
**Status**: COMPLETE - Models and Migration Created
**Migration File**: `crm_app/migrations/0040_add_corporate_contracts.py`

## Overview

Phase 1 adds database support for corporate contracts and participation agreements to the BMAsia CRM. This enables managing corporate clients with multiple venues/subsidiaries and creating master agreements with venue-specific participation agreements.

## Changes Implemented

### 1. Company Model Updates (`crm_app/models.py` lines 166-179)

**New Fields:**
```python
parent_company = models.ForeignKey(
    'self',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='child_companies',
    help_text="Corporate parent company (e.g., Hilton Corporate)"
)

is_corporate_parent = models.BooleanField(
    default=False,
    help_text="True if this is a corporate HQ that manages multiple venues"
)
```

**New Properties** (lines 212-220):
```python
@property
def is_subsidiary(self):
    """Check if this company is a subsidiary of a parent company"""
    return self.parent_company is not None

@property
def has_subsidiaries(self):
    """Check if this company has child companies"""
    return self.child_companies.exists()
```

**Use Cases:**
- Link individual venues to their corporate parent (e.g., "Hilton Pattaya" → "Hilton Corporate")
- Identify corporate headquarters that manage multiple properties
- Query all subsidiaries of a corporate parent
- Filter companies by corporate structure

### 2. Contract Model Updates (`crm_app/models.py` lines 617-643)

**New Fields:**
```python
CONTRACT_CATEGORY_CHOICES = [
    ('standard', 'Standard Contract'),
    ('corporate_master', 'Corporate Master Agreement'),
    ('participation', 'Participation Agreement'),
]

contract_category = models.CharField(
    max_length=20,
    choices=CONTRACT_CATEGORY_CHOICES,
    default='standard',
)

master_contract = models.ForeignKey(
    'self',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='participation_agreements',
    help_text="Reference to master agreement (for participation agreements)"
)

customer_signatory_name = models.CharField(max_length=255, blank=True)
customer_signatory_title = models.CharField(max_length=255, blank=True)
bmasia_signatory_name = models.CharField(max_length=255, blank=True)
bmasia_signatory_title = models.CharField(max_length=255, blank=True)
custom_terms = models.TextField(blank=True, help_text="Custom terms for master agreements")
```

**Validation Logic** (`clean()` method, lines 693-713):
- Participation agreements MUST reference a master contract
- Master contract MUST be of type 'corporate_master'
- Corporate master agreements CANNOT reference another master contract
- Raises Django ValidationError if rules violated

**Use Cases:**
- Create master agreements with corporate clients (standard terms, pricing)
- Link venue-specific participation agreements to the master
- Store custom terms for large corporate deals
- Track signatories for legal compliance
- Maintain hierarchical contract structure

### 3. StaticDocument Model (NEW - lines 2998-3022)

**Purpose:** Manage static document templates (Standard Terms & Conditions)

**Fields:**
```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
name = models.CharField(max_length=255)
document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES, unique=True)
file = models.FileField(upload_to='static_documents/')
version = models.CharField(max_length=20, default='1.0')
effective_date = models.DateField(null=True, blank=True)
description = models.TextField(blank=True)
is_active = models.BooleanField(default=True)
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

**Document Types:**
- `standard_terms_th` - Standard Terms for Thailand/Hong Kong clients
- `standard_terms_intl` - Standard Terms for International clients

**Use Cases:**
- Store PDF templates for standard terms
- Version control for legal documents
- Separate terms for different billing entities
- Auto-attach to contracts based on billing entity

### 4. Database Migration (`0040_add_corporate_contracts.py`)

**Operations:**
1. Add `parent_company` and `is_corporate_parent` to Company model
2. Add all corporate contract fields to Contract model
3. Create StaticDocument model with all fields
4. Add database indexes for performance:
   - `parent_company` (Company)
   - `contract_category` (Contract)
   - `master_contract` (Contract)

**Backward Compatibility:**
- All new fields have safe defaults (`null=True`, `blank=True`, or default values)
- Existing contracts automatically get `contract_category='standard'`
- No data migration required
- Zero downtime deployment safe

## Database Schema Changes

### Company Table
```sql
ALTER TABLE crm_app_company ADD COLUMN parent_company_id UUID NULL;
ALTER TABLE crm_app_company ADD COLUMN is_corporate_parent BOOLEAN DEFAULT FALSE;
CREATE INDEX crm_app_com_parent__idx ON crm_app_company(parent_company_id);
```

### Contract Table
```sql
ALTER TABLE crm_app_contract ADD COLUMN contract_category VARCHAR(20) DEFAULT 'standard';
ALTER TABLE crm_app_contract ADD COLUMN master_contract_id UUID NULL;
ALTER TABLE crm_app_contract ADD COLUMN customer_signatory_name VARCHAR(255);
ALTER TABLE crm_app_contract ADD COLUMN customer_signatory_title VARCHAR(255);
ALTER TABLE crm_app_contract ADD COLUMN bmasia_signatory_name VARCHAR(255);
ALTER TABLE crm_app_contract ADD COLUMN bmasia_signatory_title VARCHAR(255);
ALTER TABLE crm_app_contract ADD COLUMN custom_terms TEXT;

CREATE INDEX crm_app_con_categor_idx ON crm_app_contract(contract_category);
CREATE INDEX crm_app_con_master__idx ON crm_app_contract(master_contract_id);
```

### StaticDocument Table (NEW)
```sql
CREATE TABLE crm_app_staticdocument (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) UNIQUE NOT NULL,
    file VARCHAR(100) NOT NULL,
    version VARCHAR(20) DEFAULT '1.0',
    effective_date DATE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

## Example Use Cases

### Use Case 1: Hilton Corporate Master Agreement
```python
# Create corporate parent
hilton_corporate = Company.objects.create(
    name="Hilton Corporate",
    is_corporate_parent=True,
    country="Hong Kong"
)

# Create master agreement
master_contract = Contract.objects.create(
    company=hilton_corporate,
    contract_category='corporate_master',
    contract_number='MA-2025-HILTON-001',
    custom_terms='Volume discount: 15% for 10+ venues',
    customer_signatory_name='John Smith',
    customer_signatory_title='VP of Procurement',
    bmasia_signatory_name='Norbert Platzer',
    bmasia_signatory_title='Managing Director',
    # ... other standard fields
)
```

### Use Case 2: Venue-Specific Participation Agreement
```python
# Create subsidiary venue
hilton_pattaya = Company.objects.create(
    name="Hilton Pattaya",
    parent_company=hilton_corporate,
    country="Thailand"
)

# Create participation agreement
participation = Contract.objects.create(
    company=hilton_pattaya,
    contract_category='participation',
    master_contract=master_contract,  # Links to master
    contract_number='PA-2025-HILTON-PATTAYA',
    # Inherits terms from master, venue-specific details
    # ... other fields
)
```

### Use Case 3: Query Corporate Structure
```python
# Get all Hilton venues
hilton_venues = Company.objects.filter(parent_company=hilton_corporate)

# Get all participation agreements for master
participations = master_contract.participation_agreements.all()

# Check if company is a subsidiary
if hilton_pattaya.is_subsidiary:
    print(f"Parent: {hilton_pattaya.parent_company.name}")
```

## Testing Recommendations

### Unit Tests
```python
def test_company_corporate_structure():
    """Test parent-child company relationships"""
    parent = Company.objects.create(name="Parent Corp", is_corporate_parent=True)
    child = Company.objects.create(name="Child Venue", parent_company=parent)
    
    assert child.is_subsidiary == True
    assert parent.has_subsidiaries == True
    assert child in parent.child_companies.all()

def test_contract_validation():
    """Test participation agreement validation"""
    # Should raise ValidationError - no master contract
    with pytest.raises(ValidationError):
        contract = Contract(contract_category='participation')
        contract.clean()
    
    # Should succeed
    master = Contract.objects.create(contract_category='corporate_master', ...)
    participation = Contract(contract_category='participation', master_contract=master)
    participation.clean()  # Should not raise
```

### Integration Tests
- Test creating master + participation agreements
- Test querying corporate structures
- Test PDF generation with signatory details
- Test admin interface for corporate contracts

## Next Steps (Future Phases)

**Phase 2: Admin Interface**
- Custom admin views for corporate contracts
- Inline participation agreements on master contract admin
- Corporate structure visualization
- Bulk operations for subsidiaries

**Phase 3: Frontend (React)**
- Corporate contract forms
- Master agreement selector
- Participation agreement creation wizard
- Corporate structure tree view
- SignatureCanvas integration

**Phase 4: PDF Templates**
- Master Agreement PDF template
- Participation Agreement PDF (with master reference)
- Auto-attach Standard Terms from StaticDocument
- Signatory signature fields

**Phase 5: API Endpoints**
- `/api/companies/{id}/subsidiaries/`
- `/api/contracts/{id}/participation-agreements/`
- `/api/static-documents/`
- Corporate structure endpoints

## Files Modified

1. `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/models.py`
   - Lines 166-179: Company corporate fields
   - Lines 212-220: Company properties
   - Lines 617-643: Contract corporate fields
   - Lines 693-713: Contract clean() validation
   - Lines 2998-3022: StaticDocument model

2. `/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM/crm_app/migrations/0040_add_corporate_contracts.py`
   - Complete migration with all operations
   - Database indexes for performance
   - Backward compatible with existing data

## Deployment Instructions

### Local Development
```bash
# Activate virtual environment
source venv/bin/activate

# Create migration (already created)
# python manage.py makemigrations

# Review migration
python manage.py sqlmigrate crm_app 0040

# Apply migration
python manage.py migrate

# Verify in Django shell
python manage.py shell
>>> from crm_app.models import Company, Contract, StaticDocument
>>> Company._meta.get_field('parent_company')
>>> Contract._meta.get_field('contract_category')
>>> StaticDocument.objects.model
```

### Production (Render.com)
```bash
# Commit changes
git add crm_app/models.py
git add crm_app/migrations/0040_add_corporate_contracts.py
git commit -m "Add corporate contracts support - Phase 1"

# Push to GitHub
git push origin main

# Deploy to Render
curl -X POST -H "Authorization: Bearer $RENDER_API_KEY" \
  https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys

# Monitor deployment
# Check Render dashboard for migration execution

# Verify in production admin
# https://bmasia-crm.onrender.com/admin/crm_app/company/
# https://bmasia-crm.onrender.com/admin/crm_app/contract/
```

## Performance Considerations

### Indexes Added
- `parent_company` on Company (for corporate structure queries)
- `contract_category` on Contract (for filtering by type)
- `master_contract` on Contract (for participation agreement lookups)

### Query Optimization
```python
# Efficient corporate structure query
companies_with_parents = Company.objects.select_related('parent_company').all()

# Efficient participation agreement query
master_with_participations = Contract.objects.prefetch_related(
    'participation_agreements'
).filter(contract_category='corporate_master')
```

### Expected Impact
- Minimal impact on existing queries (new fields indexed)
- Corporate structure queries: O(1) with parent_company index
- Participation lookups: Optimized with master_contract index

## Security & Validation

### Model-Level Validation
- `clean()` method enforces business rules
- Django admin will call `clean()` automatically
- API should call `full_clean()` before save

### Data Integrity
- Foreign keys use SET_NULL (prevents cascade delete issues)
- Unique constraint on StaticDocument.document_type
- Contract validation prevents orphaned participation agreements

## Rollback Plan

If issues arise, rollback migration:
```bash
# Rollback to previous migration
python manage.py migrate crm_app 0039

# Or use custom rollback SQL
# DROP INDEX IF EXISTS crm_app_com_parent__idx;
# ALTER TABLE crm_app_company DROP COLUMN parent_company_id;
# ... etc
```

No data loss risk - all new fields are optional.

## Success Criteria

- [ ] Migration applies successfully in local dev
- [ ] Migration applies successfully in production
- [ ] Company admin shows new corporate fields
- [ ] Contract admin shows new category choices
- [ ] StaticDocument admin accessible
- [ ] Model validation works (test participation agreement)
- [ ] No existing functionality broken
- [ ] Database queries remain performant

## Related Documentation

- Django Self-Referential Foreign Keys: https://docs.djangoproject.com/en/5.0/ref/models/fields/#foreignkey
- Model Validation: https://docs.djangoproject.com/en/5.0/ref/models/instances/#validating-objects
- File Uploads: https://docs.djangoproject.com/en/5.0/topics/http/file-uploads/

---

**Implementation Status**: ✅ COMPLETE
**Ready for Testing**: YES
**Ready for Deployment**: YES (after testing)
**Dependencies**: None (backward compatible)
