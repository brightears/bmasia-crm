# Contract Content Management System - Frontend Implementation

## Overview
Implemented the frontend for the Contract Content Management System, adding support for contract templates, service package items, corporate PDF templates, and contract documents. This system allows users to create contracts with pre-approved templates, customizable content, and detailed service packages.

## Implementation Date
December 16, 2025

## Files Modified

### 1. `/bmasia-crm-frontend/src/types/index.ts`

Added new TypeScript interfaces for the Contract Content Management system:

#### New Interfaces:
- **ContractTemplate**: Pre-approved contract templates
  - Fields: id, name, template_type, content, is_default, is_active, version, created_at, updated_at
  - Template types: preamble, service_standard, service_managed, service_custom, payment_thailand, payment_international, activation

- **ServicePackageItem**: Predefined service package items
  - Fields: id, name, description, is_standard, display_order, created_at

- **CorporatePdfTemplate**: Corporate-specific PDF formats
  - Fields: id, name, template_format, include_exhibit_d, include_attachment_a, header_text, legal_terms, warranty_text, use_corporate_branding, company, company_name

- **ContractDocument**: Document attachments for contracts
  - Fields: id, contract, document_type, title, file, is_official, is_signed, signed_date, uploaded_by, uploaded_by_name, uploaded_at, notes
  - Document types: generated, principal_terms, attachment_a, exhibit_d, master_agreement, participation_agreement, standard_terms, insurance, other

#### Updated Contract Interface:
Added the following optional fields to the Contract interface:
- `preamble_template?: string` - FK to ContractTemplate
- `preamble_custom?: string` - Custom preamble text override
- `payment_template?: string` - FK to ContractTemplate
- `payment_custom?: string` - Custom payment terms override
- `activation_template?: string` - FK to ContractTemplate
- `activation_custom?: string` - Custom activation terms override
- `service_items?: string[]` - Array of ServicePackageItem IDs
- `custom_service_items?: Array<{ name: string; description: string }>` - Custom service items
- `show_zone_pricing_detail?: boolean` - Toggle for zone pricing display
- `price_per_zone?: number` - Per-zone pricing amount
- `bmasia_contact_name?: string` - BMAsia contact person name
- `bmasia_contact_email?: string` - BMAsia contact person email
- `bmasia_contact_title?: string` - BMAsia contact person title
- `customer_contact_name?: string` - Customer contact person name
- `customer_contact_email?: string` - Customer contact person email
- `customer_contact_title?: string` - Customer contact person title

### 2. `/bmasia-crm-frontend/src/services/api.ts`

#### New API Methods:

**Contract Templates:**
```typescript
async getContractTemplates(params?: any): Promise<ApiResponse<any>>
async getContractTemplate(id: string): Promise<any>
```

**Service Package Items:**
```typescript
async getServicePackageItems(): Promise<any[]>
```

**Corporate PDF Templates:**
```typescript
async getCorporatePdfTemplates(params?: any): Promise<ApiResponse<any>>
```

**Contract Documents:**
```typescript
async getContractDocuments(contractId: string): Promise<any[]>
async uploadContractDocument(contractId: string, data: FormData): Promise<any>
async deleteContractDocument(id: string): Promise<void>
```

#### API Endpoints:
- GET `/api/v1/contract-templates/` - List all contract templates
- GET `/api/v1/contract-templates/{id}/` - Get specific template
- GET `/api/v1/service-package-items/` - List all service package items
- GET `/api/v1/corporate-pdf-templates/` - List corporate PDF templates
- GET `/api/v1/contract-documents/?contract={id}` - Get documents for a contract
- POST `/api/v1/contract-documents/` - Upload new contract document
- DELETE `/api/v1/contract-documents/{id}/` - Delete contract document

### 3. `/bmasia-crm-frontend/src/components/ContractForm.tsx`

#### New State Management:
Added state for contract content management:
```typescript
const [contractTemplates, setContractTemplates] = useState<any[]>([]);
const [servicePackageItems, setServicePackageItems] = useState<any[]>([]);
const [selectedServiceItems, setSelectedServiceItems] = useState<any[]>([]);
const [customServiceItems, setCustomServiceItems] = useState<Array<{ name: string; description: string }>>([]);
const [customizePreamble, setCustomizePreamble] = useState(false);
const [customizePayment, setCustomizePayment] = useState(false);
const [customizeActivation, setCustomizeActivation] = useState(false);
```

#### New Form Fields:
Extended formData state with all new contract content fields:
- Template selections (preamble, payment, activation)
- Custom text overrides for each template
- Zone pricing fields
- Contact information fields (6 fields total)

#### New Data Loading Functions:
```typescript
const loadContractTemplates = async () => { ... }
const loadServicePackageItems = async () => { ... }
```

#### Updated Functions:
- **populateForm()**: Now populates all contract content fields from existing contract data
- **resetForm()**: Resets all new fields to default values
- **handleSubmit()**: Includes all new fields in contract data submission

#### New UI Section: "Contract Content"
Added a comprehensive collapsible section with:

1. **Template Selectors** (3 templates):
   - Preamble Template dropdown
   - Payment Terms Template dropdown (filters payment_thailand and payment_international)
   - Activation Terms Template dropdown
   - Each has a "Customize" checkbox to show custom text override textarea

2. **Service Package**:
   - Multi-select Autocomplete for predefined service items
   - Visual distinction (chips) for standard vs custom items
   - Custom service items section with add/remove functionality
   - Each custom item has name and description fields

3. **Zone Pricing**:
   - Toggle switch for "Show Zone Pricing Detail"
   - "Price Per Zone" number field (shown when toggle is on)
   - Currency symbol adapts to selected contract currency (฿, $, €, £)

4. **Contact Information**:
   - Two rows of 3 fields each:
     - BMAsia Contact: Name, Email, Title
     - Customer Contact: Name, Email, Title

## UI/UX Features

### Template Management
- Dropdowns show only active templates
- Default templates are labeled with "(Default)"
- Templates are filtered by type (preamble, payment, activation)
- Custom text override appears only when "Customize" is checked

### Service Package
- Multi-select with chips for easy visual reference
- Standard items shown with primary color (BMAsia orange)
- Custom items can be added dynamically with name and description
- Each custom item can be removed individually

### Zone Pricing
- Toggle-based display (only shows price field when enabled)
- Currency-aware input (automatically shows correct currency symbol)
- Integrated with existing contract currency selection

### Contact Information
- Clean 2-row layout for BMAsia and Customer contacts
- Email validation on email fields
- Consistent with existing form styling

## Integration with Backend

All new fields are properly typed and integrated with the backend Contract model:
- Template selections stored as foreign keys
- Custom text stored in separate text fields
- Service items stored as ManyToMany relationship
- Custom service items stored as JSONField
- All fields are optional to maintain backward compatibility

## Data Flow

1. **On Form Open**:
   - Loads contract templates from `/api/v1/contract-templates/`
   - Loads service package items from `/api/v1/service-package-items/`
   - Loads existing contract data if in edit mode

2. **During Edit**:
   - Populates template selections
   - Sets customize flags based on existing custom text
   - Loads selected service items
   - Loads custom service items

3. **On Submit**:
   - Serializes all template selections
   - Includes custom text overrides
   - Converts selected service items to ID array
   - Includes custom service items as JSON
   - Submits to existing contract create/update endpoints

## Backward Compatibility

All new fields are optional (marked with `?` in TypeScript):
- Existing contracts without these fields will work normally
- Forms can be submitted without filling new fields
- Default values ensure graceful degradation

## Material-UI Components Used

- **Select**: Template dropdowns
- **Switch**: Customize toggles, zone pricing toggle
- **TextField**: Custom text areas, contact fields, price per zone
- **Autocomplete**: Multi-select for service items
- **Chip**: Visual tags for selected service items
- **Paper**: Custom service item containers
- **IconButton**: Delete buttons for custom items
- **Button**: Add custom service item button
- **Divider**: Section separators
- **Typography**: Section headers and labels

## Styling Consistency

- Follows existing BMAsia CRM color scheme
- Uses BMAsia orange (#FFA500) for primary actions
- Consistent spacing and gap values (2, 3 for Box gap prop)
- Material-UI standard form controls throughout
- Responsive layout with flexbox

## Testing Recommendations

1. **Template Selection**:
   - Verify templates load correctly filtered by type
   - Test custom text override appearance/disappearance
   - Confirm default templates are labeled

2. **Service Package**:
   - Test multi-select functionality
   - Add and remove custom service items
   - Verify standard vs custom item visual distinction

3. **Zone Pricing**:
   - Toggle on/off functionality
   - Currency symbol changes with currency selection
   - Number input validation

4. **Contact Information**:
   - Email field validation
   - All 6 fields save and load correctly

5. **Form Submission**:
   - Create new contract with all fields
   - Edit existing contract preserves all fields
   - Empty optional fields don't cause errors

6. **Backward Compatibility**:
   - Load contracts created before this feature
   - Ensure no errors with missing fields

## Future Enhancements

Potential improvements for future iterations:

1. **Template Preview**: Show template content preview on selection
2. **Template Versioning**: Track template version history
3. **Service Item Categories**: Group service items by category
4. **Bulk Template Operations**: Apply templates to multiple contracts
5. **Template Approval Workflow**: Require approval for custom overrides
6. **Document Management UI**: Complete interface for contract document uploads
7. **PDF Template Preview**: Preview PDF format before generating
8. **Smart Defaults**: Auto-select templates based on contract type/country

## Backend API Endpoints Expected

The frontend expects these endpoints to be available:

```
GET  /api/v1/contract-templates/
GET  /api/v1/contract-templates/{id}/
GET  /api/v1/service-package-items/
GET  /api/v1/corporate-pdf-templates/
GET  /api/v1/contract-documents/?contract={contractId}
POST /api/v1/contract-documents/
DELETE /api/v1/contract-documents/{id}/
```

Contract endpoints should accept all new fields:
```
POST /api/v1/contracts/
PUT  /api/v1/contracts/{id}/
```

## Success Criteria

- All new fields display correctly in ContractForm
- Template dropdowns populate from API
- Service items multi-select works properly
- Custom service items can be added/removed
- Zone pricing toggle functions correctly
- Contact information fields save and load
- Form submission includes all new fields
- Backward compatible with existing contracts
- No console errors or warnings
- Consistent with existing UI/UX patterns

## Summary

Successfully implemented a comprehensive Contract Content Management system in the frontend, providing users with:
- Pre-approved template selection with customization options
- Flexible service package configuration
- Zone-based pricing controls
- Contact information management
- Full integration with backend API
- Backward compatible design
- Consistent Material-UI styling

The implementation follows React best practices, uses TypeScript for type safety, and maintains consistency with the existing BMAsia CRM codebase.
