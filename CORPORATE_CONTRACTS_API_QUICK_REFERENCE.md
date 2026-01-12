# Corporate Contracts API - Quick Reference

## New API Endpoints

### Company Endpoints (Enhanced)

#### Get Corporate Parents
```
GET /api/v1/companies/?is_corporate_parent=true
```
Returns all companies flagged as corporate parents/headquarters.

#### Get Subsidiaries of a Parent
```
GET /api/v1/companies/?parent_company={uuid}
```
Returns all subsidiaries under a specific parent company.

#### Company Response (New Fields)
```json
{
  "id": "uuid",
  "name": "Hilton Pattaya",
  "parent_company": "uuid-of-hilton-corporate",
  "parent_company_name": "Hilton Corporate",
  "is_corporate_parent": false,
  "is_subsidiary": true,
  "child_companies_count": 0,
  ...
}
```

### Contract Endpoints (Enhanced)

#### List Master Agreements
```
GET /api/v1/contracts/master-agreements/
```
Returns all active corporate master agreements (for dropdown selection).

**Response:**
```json
[
  {
    "id": "uuid",
    "contract_number": "C-2025-0101-001",
    "contract_category": "corporate_master",
    "company": "uuid",
    "company_name": "Hilton Corporate",
    "participation_agreements_count": 5,
    "customer_signatory_name": "John Smith",
    "customer_signatory_title": "CPO",
    "custom_terms": "Volume pricing...",
    ...
  }
]
```

#### Get Participation Agreements for Master Contract
```
GET /api/v1/contracts/{master-contract-id}/participation-agreements/
```
Returns all participation agreements under a specific master contract.

**Response:**
```json
[
  {
    "id": "uuid",
    "contract_number": "C-2025-0105-012",
    "contract_category": "participation",
    "master_contract": "uuid-of-master",
    "master_contract_number": "C-2025-0101-001",
    "company": "uuid",
    "company_name": "Hilton Pattaya",
    ...
  }
]
```

#### Filter Contracts by Category
```
GET /api/v1/contracts/?contract_category=corporate_master
GET /api/v1/contracts/?contract_category=participation
GET /api/v1/contracts/?contract_category=standard
```

#### Contract Response (New Fields)
```json
{
  "id": "uuid",
  "contract_number": "C-2025-0105-012",
  "contract_category": "participation",
  "master_contract": "uuid-of-master",
  "master_contract_number": "C-2025-0101-001",
  "customer_signatory_name": "Jane Doe",
  "customer_signatory_title": "General Manager",
  "bmasia_signatory_name": "Norbert Platzer",
  "bmasia_signatory_title": "Managing Director",
  "custom_terms": "Special terms...",
  "participation_agreements_count": 0,
  ...
}
```

### Static Documents Endpoints (NEW)

#### List Static Documents
```
GET /api/v1/static-documents/
GET /api/v1/static-documents/?document_type=standard_terms_th
GET /api/v1/static-documents/?is_active=true
GET /api/v1/static-documents/?search=thailand
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Standard Terms & Conditions - Thailand",
    "document_type": "standard_terms_th",
    "document_type_display": "Standard Terms - Thailand/Hong Kong",
    "file": "/media/static_documents/terms_th_v2.pdf",
    "file_url": "https://bmasia-crm.onrender.com/media/static_documents/terms_th_v2.pdf",
    "version": "2.0",
    "effective_date": "2025-01-01",
    "description": "Updated terms for Thailand and Hong Kong clients",
    "is_active": true,
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
]
```

#### Get Single Document
```
GET /api/v1/static-documents/{uuid}/
```

#### Create Static Document
```
POST /api/v1/static-documents/
Content-Type: multipart/form-data

{
  "name": "Standard Terms & Conditions - Thailand",
  "document_type": "standard_terms_th",
  "file": [PDF file upload],
  "version": "2.0",
  "effective_date": "2025-01-01",
  "description": "Updated terms for Thailand and Hong Kong clients",
  "is_active": true
}
```

#### Update Static Document
```
PATCH /api/v1/static-documents/{uuid}/
Content-Type: application/json

{
  "description": "Updated description",
  "is_active": false
}
```

#### Download PDF File
```
GET /api/v1/static-documents/{uuid}/download/
```
Returns the PDF file with proper `Content-Disposition` header for download.
Filename format: `{name}_v{version}.pdf`

#### Delete Static Document
```
DELETE /api/v1/static-documents/{uuid}/
```

## Document Types

```python
DOCUMENT_TYPE_CHOICES = [
    ('standard_terms_th', 'Standard Terms - Thailand/Hong Kong'),
    ('standard_terms_intl', 'Standard Terms - International'),
]
```

## Contract Categories

```python
CONTRACT_CATEGORY_CHOICES = [
    ('standard', 'Standard Contract'),
    ('corporate_master', 'Corporate Master Agreement'),
    ('participation', 'Participation Agreement'),
]
```

## Example Workflows

### 1. Create Corporate Structure
```bash
# 1. Create corporate parent
POST /api/v1/companies/
{
  "name": "Hilton Corporate",
  "is_corporate_parent": true,
  "country": "USA"
}

# 2. Create subsidiary
POST /api/v1/companies/
{
  "name": "Hilton Pattaya",
  "parent_company": "{uuid-of-hilton-corporate}",
  "country": "Thailand"
}

# 3. Verify hierarchy
GET /api/v1/companies/{hilton-corporate-uuid}/
# Returns: child_companies_count: 1

GET /api/v1/companies/{hilton-pattaya-uuid}/
# Returns: is_subsidiary: true, parent_company_name: "Hilton Corporate"
```

### 2. Create Master Agreement with Participation Agreements
```bash
# 1. Create corporate master agreement
POST /api/v1/contracts/
{
  "company": "{hilton-corporate-uuid}",
  "contract_category": "corporate_master",
  "contract_type": "Annual",
  "status": "Active",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "value": 100000.00,
  "currency": "USD",
  "customer_signatory_name": "John Smith",
  "customer_signatory_title": "Chief Procurement Officer",
  "bmasia_signatory_name": "Norbert Platzer",
  "bmasia_signatory_title": "Managing Director",
  "custom_terms": "Volume pricing: 10% discount for 50+ zones"
}

# 2. Get list of master agreements (for dropdown)
GET /api/v1/contracts/master-agreements/
# Returns: [{ id: "master-uuid", contract_number: "C-2025-0101-001", ... }]

# 3. Create participation agreement for Hilton Pattaya
POST /api/v1/contracts/
{
  "company": "{hilton-pattaya-uuid}",
  "contract_category": "participation",
  "master_contract": "{master-uuid}",
  "contract_type": "Annual",
  "status": "Active",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "value": 5000.00,
  "currency": "THB"
}

# 4. Get all participation agreements under master
GET /api/v1/contracts/{master-uuid}/participation-agreements/
# Returns: [{ id: "participation-uuid", company_name: "Hilton Pattaya", ... }]

# 5. Verify master contract shows count
GET /api/v1/contracts/{master-uuid}/
# Returns: participation_agreements_count: 1
```

### 3. Manage Static Documents
```bash
# 1. Upload new T&C document
POST /api/v1/static-documents/
Content-Type: multipart/form-data
{
  "name": "Standard Terms - Thailand",
  "document_type": "standard_terms_th",
  "file": [PDF file],
  "version": "2.0",
  "effective_date": "2025-01-01",
  "is_active": true
}

# 2. List active documents
GET /api/v1/static-documents/?is_active=true

# 3. Get Thailand T&C
GET /api/v1/static-documents/?document_type=standard_terms_th

# 4. Download PDF
GET /api/v1/static-documents/{uuid}/download/

# 5. Deactivate old version
PATCH /api/v1/static-documents/{old-uuid}/
{
  "is_active": false
}
```

## Frontend Integration Tips

### Dropdown for Master Agreements
```typescript
// Fetch master agreements for dropdown
const response = await api.get('/api/v1/contracts/master-agreements/');
const masterAgreements = response.data;

// Show in dropdown
<Select>
  {masterAgreements.map(ma => (
    <MenuItem value={ma.id}>
      {ma.contract_number} - {ma.company_name}
    </MenuItem>
  ))}
</Select>
```

### Company Hierarchy Display
```typescript
// Fetch company with hierarchy
const company = await api.get(`/api/v1/companies/${id}/`);

if (company.is_corporate_parent) {
  console.log(`Corporate HQ with ${company.child_companies_count} subsidiaries`);
}

if (company.is_subsidiary) {
  console.log(`Subsidiary of ${company.parent_company_name}`);
}
```

### Static Document Selection
```typescript
// Fetch active T&C documents
const docs = await api.get('/api/v1/static-documents/', {
  params: {
    document_type: billing_entity === 'BMAsia (Thailand) Co., Ltd.'
      ? 'standard_terms_th'
      : 'standard_terms_intl',
    is_active: true
  }
});

// Use file_url for display/download
const downloadUrl = docs.data[0].file_url;
```

## Validation Rules

### Participation Agreements
- **Must** have a `master_contract` reference
- `master_contract` **must** be of type `corporate_master`
- Cannot reference a `master_contract` that is itself a participation agreement

### Corporate Master Agreements
- **Cannot** have a `master_contract` reference
- Can have multiple participation agreements linked to it

### Static Documents
- `document_type` must be unique (only one active document per type)
- `file` field is required
- Supports file upload via multipart/form-data

## Error Responses

### Invalid Master Contract Reference
```json
{
  "master_contract": [
    "Master contract must be of type \"Corporate Master Agreement\"."
  ]
}
```

### Missing Master Contract for Participation Agreement
```json
{
  "master_contract": [
    "Participation agreements must reference a master contract."
  ]
}
```

### Wrong Contract Type for Endpoint
```json
{
  "error": "This endpoint only works for corporate master agreements"
}
```

### File Not Found
```json
{
  "error": "File not found on server"
}
```

## Performance Notes

1. **Company Queries** - Use `select_related('parent_company')` for efficient parent lookups
2. **Contract Queries** - Master agreements prefetch participation agreements
3. **Filtering** - Use database-level filters (`?contract_category=corporate_master`) instead of client-side filtering
4. **Static Documents** - File URLs are pre-computed to avoid multiple URL building operations

## Migration Status

✅ Phase 1: Database schema (completed)
✅ Phase 2: API endpoints (this phase)
⏳ Phase 3: Frontend UI (next phase)
