# Contract Content Management System - Quick Reference

## Model Overview

### CorporatePdfTemplate
**Location**: `crm_app/models.py` (Line 876)  
**Purpose**: Corporate-specific PDF layouts and branding

**Key Fields**:
- `template_format`: Choice (standard, hilton_hpa, marriott, ihg, accor, custom)
- `include_exhibit_d`: Boolean - Generate legal terms exhibit
- `include_attachment_a`: Boolean - Generate scope of work
- `company`: OneToOneField → Company (corporate parents only)
- `corporate_logo`: ImageField (optional)

**Relationship**: One template per corporate parent company

---

### ContractTemplate
**Location**: `crm_app/models.py` (Line 909)  
**Purpose**: Reusable contract language templates

**Template Types**:
- `preamble` - Introduction text
- `service_standard` - Standard service package
- `service_managed` - Managed service package
- `service_custom` - Custom service package
- `payment_thailand` - Thailand payment terms
- `payment_international` - International payment terms
- `activation` - Activation terms

**Key Fields**:
- `content`: TextField with `{{variable}}` placeholders
- `is_default`: Auto-select for new contracts
- `is_active`: Enable/disable
- `version`: Version string (e.g., "1.0")

---

### ServicePackageItem
**Location**: `crm_app/models.py` (Line 940)  
**Purpose**: Pre-defined service items (reusable)

**Key Fields**:
- `name`: Short name (max 100 chars)
- `description`: Full description (TextField)
- `is_standard`: Show in selector
- `display_order`: Sort order (IntegerField)

**Usage**: Select multiple items per contract via ManyToMany

---

### ContractDocument
**Location**: `crm_app/models.py` (Line 958)  
**Purpose**: Manage contract attachments

**Document Types**:
- `generated` - System Generated PDF
- `principal_terms` - Principal Terms
- `attachment_a` - Scope of Work
- `exhibit_d` - Legal Terms
- `master_agreement` - Master Agreement
- `participation_agreement` - Participation Agreement
- `standard_terms` - Standard Terms & Conditions
- `insurance` - Insurance Certificate
- `other` - Other

**Key Fields**:
- `file`: FileField (uploads to `contract_documents/%Y/%m/`)
- `is_official`: Boolean - Official signing version
- `is_signed`: Boolean - Signing status
- `uploaded_by`: ForeignKey → User

---

## Contract Model Extensions

### Template Fields (Lines 655-683)
```python
# Preamble
contract.preamble_template → ContractTemplate (nullable)
contract.preamble_custom → TextField (overrides template)

# Payment Terms
contract.payment_template → ContractTemplate (nullable)
contract.payment_custom → TextField (overrides template)

# Activation Terms
contract.activation_template → ContractTemplate (nullable)
contract.activation_custom → TextField (overrides template)
```

### Service Package Fields (Lines 685-695)
```python
contract.service_items → ManyToMany ServicePackageItem
contract.custom_service_items → JSONField [{"name": "...", "description": "..."}]
```

### Zone Pricing Fields (Lines 697-708)
```python
contract.show_zone_pricing_detail → Boolean (default: True)
contract.price_per_zone → Decimal (nullable)
```

### Contact Fields (Lines 710-716)
```python
# BMAsia Contact
contract.bmasia_contact_name → CharField(255)
contract.bmasia_contact_email → EmailField
contract.bmasia_contact_title → CharField(255)

# Customer Contact
contract.customer_contact_name → CharField(255)
contract.customer_contact_email → EmailField
contract.customer_contact_title → CharField(255)
```

---

## Usage Examples

### Creating a Corporate PDF Template
```python
from crm_app.models import Company, CorporatePdfTemplate

company = Company.objects.get(name="Hilton Asia Pacific", is_corporate_parent=True)

template = CorporatePdfTemplate.objects.create(
    name="Hilton HPA Template",
    template_format="hilton_hpa",
    include_exhibit_d=True,
    include_attachment_a=True,
    header_text="Custom preamble for Hilton...",
    legal_terms="Hilton-specific legal clauses...",
    company=company,
    use_corporate_branding=True
)
```

### Creating a Contract Template
```python
from crm_app.models import ContractTemplate

preamble = ContractTemplate.objects.create(
    name="Standard Preamble v1.0",
    template_type="preamble",
    content="This Agreement is entered into between {{customer_name}} and BMAsia...",
    is_default=True,
    is_active=True,
    version="1.0"
)
```

### Creating Service Package Items
```python
from crm_app.models import ServicePackageItem

music_curation = ServicePackageItem.objects.create(
    name="Music Curation",
    description="Professional music programming and playlist management",
    is_standard=True,
    display_order=1
)

system_maintenance = ServicePackageItem.objects.create(
    name="System Maintenance",
    description="Regular system updates and technical support",
    is_standard=True,
    display_order=2
)
```

### Using Templates in a Contract
```python
from crm_app.models import Contract, ContractTemplate, ServicePackageItem

contract = Contract.objects.get(contract_number="C-2025-001")

# Set template references
contract.preamble_template = ContractTemplate.objects.get(template_type="preamble", is_default=True)
contract.payment_template = ContractTemplate.objects.get(template_type="payment_thailand")
contract.activation_template = ContractTemplate.objects.get(template_type="activation", is_default=True)

# Or override with custom text
contract.payment_custom = "Custom payment terms: Net 30 days..."

# Add service items
contract.service_items.add(music_curation, system_maintenance)

# Add custom service items
contract.custom_service_items = [
    {"name": "Custom Installation", "description": "Special installation requirements"}
]

# Set zone pricing
contract.show_zone_pricing_detail = True
contract.price_per_zone = Decimal("5000.00")

# Set contacts
contract.bmasia_contact_name = "John Smith"
contract.bmasia_contact_email = "john@bmasiamusic.com"
contract.customer_contact_name = "Jane Doe"
contract.customer_contact_email = "jane@customer.com"

contract.save()
```

### Uploading Contract Documents
```python
from crm_app.models import ContractDocument
from django.contrib.auth import get_user_model

User = get_user_model()
contract = Contract.objects.get(contract_number="C-2025-001")
user = User.objects.get(username="admin")

doc = ContractDocument.objects.create(
    contract=contract,
    document_type="principal_terms",
    title="Principal Terms - Hilton Pattaya",
    file=uploaded_file,  # Django file object
    is_official=True,
    uploaded_by=user,
    notes="Official version for signing"
)
```

---

## Database Queries

### Get all contracts using a specific template
```python
contracts = Contract.objects.filter(preamble_template=template)
```

### Get all service items for a contract
```python
standard_items = contract.service_items.all()
custom_items = contract.custom_service_items  # JSON array
```

### Get all documents for a contract
```python
docs = contract.documents.all()
official_docs = contract.documents.filter(is_official=True)
signed_docs = contract.documents.filter(is_signed=True)
```

### Get corporate template for a company
```python
company = Company.objects.get(name="Hilton Asia Pacific")
template = company.pdf_template  # OneToOne relationship
```

### Get all contracts using specific service item
```python
service = ServicePackageItem.objects.get(name="Music Curation")
contracts = service.contracts.all()
```

---

## Migration Commands

```bash
# Create migration
python manage.py makemigrations

# Show migration SQL (optional)
python manage.py sqlmigrate crm_app 0040

# Apply migration
python manage.py migrate

# Rollback (if needed)
python manage.py migrate crm_app 0039
```

---

## Next Implementation Steps

### Phase 2: Admin Interface
1. Register models in `admin.py`
2. Add inline editing for ContractDocument
3. Add filters and search fields
4. Add bulk actions

### Phase 3: API Serializers
1. Create DRF serializers in `serializers.py`
2. Add nested serializers for relationships
3. Create API endpoints (viewsets)
4. Add permissions

### Phase 4: Frontend
1. Add TypeScript types in `types/index.ts`
2. Create React components
3. Add template selectors
4. Add document upload UI

---

## Important Notes

1. **Template vs. Custom**: Always check if `_custom` field has content before using the template
2. **Service Items**: Contracts can have both standard items (ManyToMany) AND custom items (JSONField)
3. **Corporate Templates**: Only available for companies with `is_corporate_parent=True`
4. **Document Uploads**: Files are organized by year/month: `contract_documents/2025/12/filename.pdf`
5. **Zone Pricing**: When `show_zone_pricing_detail=False`, hide per-zone breakdown in PDFs
6. **Contact Information**: Separate from Contact model - these are contract-specific contacts

---

**File**: `/crm_app/models.py`  
**Lines**: 2, 873-990, 655-716  
**Status**: ✅ Ready for migration
