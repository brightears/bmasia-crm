# Contract Content Management - Quick Reference

## New TypeScript Types

### ContractTemplate
```typescript
{
  id: string;
  name: string;
  template_type: 'preamble' | 'service_standard' | 'service_managed' |
                 'service_custom' | 'payment_thailand' |
                 'payment_international' | 'activation';
  content: string;
  is_default: boolean;
  is_active: boolean;
  version: string;
  created_at: string;
  updated_at: string;
}
```

### ServicePackageItem
```typescript
{
  id: string;
  name: string;
  description: string;
  is_standard: boolean;
  display_order: number;
  created_at: string;
}
```

### CorporatePdfTemplate
```typescript
{
  id: string;
  name: string;
  template_format: string;
  include_exhibit_d: boolean;
  include_attachment_a: boolean;
  header_text: string;
  legal_terms: string;
  warranty_text: string;
  use_corporate_branding: boolean;
  company: string;
  company_name?: string;
}
```

### ContractDocument
```typescript
{
  id: string;
  contract: string;
  document_type: 'generated' | 'principal_terms' | 'attachment_a' |
                 'exhibit_d' | 'master_agreement' | 'participation_agreement' |
                 'standard_terms' | 'insurance' | 'other';
  title: string;
  file: string;
  is_official: boolean;
  is_signed: boolean;
  signed_date?: string;
  uploaded_by?: string;
  uploaded_by_name?: string;
  uploaded_at: string;
  notes?: string;
}
```

## New Contract Fields

All fields are optional for backward compatibility:

```typescript
interface Contract {
  // ... existing fields ...

  // Template selections
  preamble_template?: string;
  preamble_custom?: string;
  payment_template?: string;
  payment_custom?: string;
  activation_template?: string;
  activation_custom?: string;

  // Service package
  service_items?: string[];
  custom_service_items?: Array<{ name: string; description: string }>;

  // Zone pricing
  show_zone_pricing_detail?: boolean;
  price_per_zone?: number;

  // Contact information
  bmasia_contact_name?: string;
  bmasia_contact_email?: string;
  bmasia_contact_title?: string;
  customer_contact_name?: string;
  customer_contact_email?: string;
  customer_contact_title?: string;
}
```

## API Methods

```typescript
// Contract Templates
apiService.getContractTemplates(params?: any): Promise<ApiResponse<any>>
apiService.getContractTemplate(id: string): Promise<any>

// Service Package Items
apiService.getServicePackageItems(): Promise<any[]>

// Corporate PDF Templates
apiService.getCorporatePdfTemplates(params?: any): Promise<ApiResponse<any>>

// Contract Documents
apiService.getContractDocuments(contractId: string): Promise<any[]>
apiService.uploadContractDocument(contractId: string, data: FormData): Promise<any>
apiService.deleteContractDocument(id: string): Promise<void>
```

## API Endpoints

```
GET    /api/v1/contract-templates/
GET    /api/v1/contract-templates/{id}/
GET    /api/v1/service-package-items/
GET    /api/v1/corporate-pdf-templates/
GET    /api/v1/contract-documents/?contract={contractId}
POST   /api/v1/contract-documents/
DELETE /api/v1/contract-documents/{id}/
```

## ContractForm New Features

### Template Selectors
- Preamble Template dropdown (filtered by `template_type === 'preamble'`)
- Payment Template dropdown (filtered by `template_type in ['payment_thailand', 'payment_international']`)
- Activation Template dropdown (filtered by `template_type === 'activation'`)
- Each has "Customize" checkbox + custom text textarea

### Service Package
- Multi-select Autocomplete for service items
- Visual distinction: standard items (primary color) vs custom items
- Add custom service items with name + description
- Remove custom items individually

### Zone Pricing
- Toggle: "Show Zone Pricing Detail"
- Number field: "Price Per Zone" (shows when toggle is on)
- Currency symbol adapts to contract currency

### Contact Information
- 6 fields total (2 rows of 3):
  - BMAsia: Name, Email, Title
  - Customer: Name, Email, Title

## Component State

```typescript
// New state variables
const [contractTemplates, setContractTemplates] = useState<any[]>([]);
const [servicePackageItems, setServicePackageItems] = useState<any[]>([]);
const [selectedServiceItems, setSelectedServiceItems] = useState<any[]>([]);
const [customServiceItems, setCustomServiceItems] = useState<Array<{ name: string; description: string }>>([]);
const [customizePreamble, setCustomizePreamble] = useState(false);
const [customizePayment, setCustomizePayment] = useState(false);
const [customizeActivation, setCustomizeActivation] = useState(false);
```

## Usage Examples

### Loading Templates
```typescript
const loadContractTemplates = async () => {
  try {
    const response = await ApiService.getContractTemplates({ page_size: 1000 });
    setContractTemplates(response.results || []);
  } catch (err) {
    console.error('Failed to load contract templates:', err);
  }
};
```

### Loading Service Items
```typescript
const loadServicePackageItems = async () => {
  try {
    const items = await ApiService.getServicePackageItems();
    setServicePackageItems(items);
  } catch (err) {
    console.error('Failed to load service package items:', err);
  }
};
```

### Submitting Contract Data
```typescript
const contractData = {
  ...formData,
  value: parseFloat(formData.value),
  discount_percentage: parseFloat(formData.discount_percentage) || 0,
  start_date: formData.start_date.toISOString().split('T')[0],
  end_date: formData.end_date.toISOString().split('T')[0],
  price_per_zone: formData.price_per_zone ? parseFloat(formData.price_per_zone) : null,
  service_items: selectedServiceItems.map(item => item.id),
  custom_service_items: customServiceItems.length > 0 ? customServiceItems : null,
};
```

## Material-UI Components

- `Select`: Template dropdowns
- `Switch`: Customize toggles
- `TextField`: Text inputs, textareas
- `Autocomplete`: Multi-select service items
- `Chip`: Service item tags
- `Paper`: Custom service item containers
- `IconButton`: Delete buttons
- `Button`: Add buttons
- `FormControl`: Form wrappers
- `InputLabel`: Field labels
- `MenuItem`: Dropdown options
- `InputAdornment`: Currency symbols

## Filter Examples

### Filter Preamble Templates
```typescript
contractTemplates.filter(t => t.template_type === 'preamble' && t.is_active)
```

### Filter Payment Templates
```typescript
contractTemplates.filter(t =>
  ['payment_thailand', 'payment_international'].includes(t.template_type) &&
  t.is_active
)
```

### Filter Activation Templates
```typescript
contractTemplates.filter(t => t.template_type === 'activation' && t.is_active)
```

## Styling

### BMAsia Orange
```typescript
sx={{ color: '#FFA500', bgcolor: '#FFA500', borderColor: '#FFA500' }}
```

### Common Spacing
```typescript
sx={{ gap: 2 }}  // Between form elements
sx={{ mt: 2, mb: 2 }}  // Margin top/bottom
sx={{ p: 2 }}  // Padding
```

### Currency Symbols
```typescript
const currencySymbol = {
  'THB': '฿',
  'EUR': '€',
  'GBP': '£',
  'USD': '$'
}[formData.currency] || '$';
```

## Files Changed

1. `/bmasia-crm-frontend/src/types/index.ts` - Added 4 new interfaces, updated Contract
2. `/bmasia-crm-frontend/src/services/api.ts` - Added 7 new API methods
3. `/bmasia-crm-frontend/src/components/ContractForm.tsx` - Added Contract Content section

## Testing Checklist

- [ ] Templates load from API
- [ ] Template dropdowns filter correctly by type
- [ ] Customize checkboxes show/hide textareas
- [ ] Service items multi-select works
- [ ] Custom service items add/remove
- [ ] Zone pricing toggle shows/hides field
- [ ] Currency symbol changes with currency
- [ ] Contact fields save correctly
- [ ] Edit mode populates all fields
- [ ] Create mode starts empty
- [ ] Form submission includes all fields
- [ ] Old contracts load without errors
- [ ] No console errors

## Important Notes

1. All new fields are optional - backward compatible
2. Template filters require `is_active: true`
3. Default templates show "(Default)" label
4. Service items can be standard or custom
5. Custom service items stored as JSON array
6. Price per zone requires show_zone_pricing_detail: true
7. Email fields have type="email" validation
8. Currency symbol auto-updates
9. Load functions called on form open
10. Reset clears all new state variables
