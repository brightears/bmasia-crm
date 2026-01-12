# Corporate Contracts API Implementation - Phase 2

## Summary
Updated Django REST API serializers and views to support corporate contracts functionality. This is Phase 2 of the corporate contracts implementation.

## Changes Made

### 1. Serializers (`crm_app/serializers.py`)

#### Updated Imports
- Added `StaticDocument` to model imports

#### CompanySerializer
**New Fields:**
- `parent_company` (ForeignKey) - Reference to corporate parent
- `parent_company_name` (read-only) - Name of parent company
- `is_corporate_parent` (BooleanField) - Flag for corporate HQ
- `is_subsidiary` (read-only computed) - True if has a parent company
- `child_companies_count` (read-only computed) - Count of child companies (only for corporate parents)

**New Methods:**
```python
def get_is_subsidiary(self, obj):
    """Check if company is a subsidiary (has a parent)"""
    return obj.parent_company is not None

def get_child_companies_count(self, obj):
    """Count of child companies (only for corporate parents)"""
    if obj.is_corporate_parent:
        return obj.child_companies.count()
    return 0
```

#### ContractSerializer
**New Fields:**
- `contract_category` (CharField: 'standard', 'corporate_master', 'participation')
- `master_contract` (ForeignKey to self)
- `master_contract_number` (read-only) - Contract number of master agreement
- `customer_signatory_name` (CharField)
- `customer_signatory_title` (CharField)
- `bmasia_signatory_name` (CharField)
- `bmasia_signatory_title` (CharField)
- `custom_terms` (TextField)
- `participation_agreements_count` (read-only computed) - Count of participation agreements (only for corporate_master)

**New Method:**
```python
def get_participation_agreements_count(self, obj):
    """Count of participation agreements under this master contract"""
    if obj.contract_category == 'corporate_master':
        return obj.participation_agreements.count()
    return 0
```

#### StaticDocumentSerializer (NEW)
**Purpose:** Manage static documents like Standard Terms & Conditions

**Fields:**
- `id` (UUID, read-only)
- `name` (CharField)
- `document_type` (CharField with choices)
- `document_type_display` (read-only)
- `file` (FileField)
- `file_url` (read-only computed) - Absolute URL to file
- `version` (CharField)
- `effective_date` (DateField)
- `description` (TextField)
- `is_active` (BooleanField)
- `created_at`, `updated_at` (read-only)

**Method:**
```python
def get_file_url(self, obj):
    """Return the file URL if file exists"""
    if obj.file:
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url
    return None
```

### 2. Views (`crm_app/views.py`)

#### Updated Imports
- Added `StaticDocument` to model imports
- Added `StaticDocumentSerializer` to serializer imports

#### CompanyViewSet
**Updated Filtering:**
- Added `is_corporate_parent` to filterset_fields
- Added `parent_company` to filterset_fields

**Optimized Queries:**
- Added `select_related('parent_company')` for efficient parent lookups
- Added `prefetch_related('child_companies')` for child company queries

#### ContractViewSet
**Updated Filtering:**
- Added `contract_category` to filterset_fields

**New Endpoints:**

1. **GET /api/v1/contracts/master-agreements/**
   - Lists all active corporate master agreements
   - Used for dropdown selection when creating participation agreements
   - Filters: `contract_category='corporate_master'`, `is_active=True`
   - Ordered by: `-created_at`

2. **GET /api/v1/contracts/{id}/participation-agreements/**
   - Lists all participation agreements under a specific master contract
   - Validates that the contract is actually a corporate_master type
   - Returns error if called on non-master contract
   - Ordered by: `-created_at`

#### StaticDocumentViewSet (NEW)
**Base Configuration:**
- Model: `StaticDocument`
- Serializer: `StaticDocumentSerializer`
- Permission: `AllowAny`
- Filters: `document_type`, `is_active`
- Search: `name`, `description`
- Ordering: `name`, `version`, `effective_date`, `created_at` (default: `-created_at`)

**Endpoints:**

1. **GET /api/v1/static-documents/**
   - List all static documents
   - Supports filtering, searching, ordering

2. **POST /api/v1/static-documents/**
   - Create new static document
   - Requires file upload

3. **GET /api/v1/static-documents/{id}/**
   - Retrieve specific document

4. **PUT/PATCH /api/v1/static-documents/{id}/**
   - Update document

5. **DELETE /api/v1/static-documents/{id}/**
   - Delete document

6. **GET /api/v1/static-documents/{id}/download/** (Custom Action)
   - Downloads the PDF file as an attachment
   - Content-Type: `application/pdf`
   - Filename format: `{name}_v{version}.pdf`
   - Returns 404 if file doesn't exist

### 3. URLs (`crm_app/urls.py`)

**New Router Registration:**
```python
router.register(r'static-documents', views.StaticDocumentViewSet, basename='static-document')
```

## API Endpoint Summary

### Company Endpoints (Enhanced)
- `GET /api/v1/companies/` - Now includes `is_subsidiary`, `child_companies_count`
- `GET /api/v1/companies/{id}/` - Full corporate hierarchy details
- Filter by: `is_corporate_parent=true` to get only parent companies
- Filter by: `parent_company={id}` to get subsidiaries

### Contract Endpoints (Enhanced)
- `GET /api/v1/contracts/` - Now includes corporate contract fields
- `GET /api/v1/contracts/master-agreements/` - List active master agreements
- `GET /api/v1/contracts/{id}/participation-agreements/` - List participation agreements
- Filter by: `contract_category=corporate_master` for master agreements
- Filter by: `contract_category=participation` for participation agreements

### Static Document Endpoints (NEW)
- `GET /api/v1/static-documents/` - List all documents
- `POST /api/v1/static-documents/` - Upload new document
- `GET /api/v1/static-documents/{id}/` - Get document details
- `PUT/PATCH /api/v1/static-documents/{id}/` - Update document
- `DELETE /api/v1/static-documents/{id}/` - Delete document
- `GET /api/v1/static-documents/{id}/download/` - Download PDF file

## Example API Usage

### Creating a Corporate Master Agreement
```json
POST /api/v1/contracts/
{
  "company": "uuid-of-hilton-corporate",
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
```

### Creating a Participation Agreement
```json
POST /api/v1/contracts/
{
  "company": "uuid-of-hilton-pattaya",
  "contract_category": "participation",
  "master_contract": "uuid-of-master-agreement",
  "contract_type": "Annual",
  "status": "Active",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "value": 5000.00,
  "currency": "THB"
}
```

### Listing Corporate Parents
```
GET /api/v1/companies/?is_corporate_parent=true
```

### Listing Master Agreements
```
GET /api/v1/contracts/master-agreements/
```

### Getting Participation Agreements for a Master Contract
```
GET /api/v1/contracts/{master-contract-id}/participation-agreements/
```

### Uploading a Static Document
```json
POST /api/v1/static-documents/
Content-Type: multipart/form-data

{
  "name": "Standard Terms & Conditions - Thailand",
  "document_type": "standard_terms_th",
  "file": [PDF file],
  "version": "2.0",
  "effective_date": "2025-01-01",
  "description": "Updated terms for Thailand and Hong Kong clients",
  "is_active": true
}
```

### Downloading a Static Document
```
GET /api/v1/static-documents/{id}/download/
```

## Testing Recommendations

1. **Test Company Hierarchy:**
   - Create a corporate parent company
   - Create subsidiary companies linked to parent
   - Verify `is_subsidiary` and `child_companies_count` fields

2. **Test Master Agreements:**
   - Create a corporate master agreement
   - Verify it appears in `/contracts/master-agreements/`
   - Create participation agreements referencing the master

3. **Test Participation Agreements:**
   - Create participation agreement without master contract (should fail validation)
   - Create participation agreement with valid master contract
   - Verify count appears in master contract's `participation_agreements_count`

4. **Test Static Documents:**
   - Upload a PDF document
   - Verify `file_url` is generated correctly
   - Test download endpoint
   - Filter by `document_type` and `is_active`

5. **Test Filtering:**
   - Filter companies by `is_corporate_parent`
   - Filter contracts by `contract_category`
   - Verify query performance with prefetch optimizations

## Files Modified

1. `/crm_app/serializers.py`
   - Updated imports
   - Enhanced CompanySerializer
   - Enhanced ContractSerializer
   - Added StaticDocumentSerializer

2. `/crm_app/views.py`
   - Updated imports
   - Enhanced CompanyViewSet (filtering + query optimization)
   - Enhanced ContractViewSet (new endpoints)
   - Added StaticDocumentViewSet

3. `/crm_app/urls.py`
   - Registered StaticDocumentViewSet

## Next Steps (Phase 3 - Frontend)

1. Update Company form to support parent company selection
2. Create Contract Category selector (Standard/Master/Participation)
3. Add Master Contract dropdown for Participation Agreements
4. Create Static Documents management UI
5. Implement PDF upload functionality
6. Add corporate hierarchy visualization

## Database Compatibility

All changes are backward compatible. Existing API calls will continue to work with the following additions:
- CompanySerializer now includes additional fields (optional)
- ContractSerializer now includes additional fields (optional)
- New endpoints are additive and don't affect existing ones

No database migrations required for this phase (Phase 1 already created the database schema).
