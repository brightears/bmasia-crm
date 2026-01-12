# Principal Terms PDF - Quick Reference Guide

## Template Variables Reference

Use these variables in any template content (preamble, payment terms, activation terms):

| Variable | Example Output | Description |
|----------|----------------|-------------|
| `{{start_date}}` | 01 January 2025 | Contract start date (long format) |
| `{{end_date}}` | 31 December 2025 | Contract end date (long format) |
| `{{company_name}}` | Hilton Pattaya | Company display name |
| `{{company_legal_name}}` | CPN Pattaya Hotel Co., Ltd. | Legal entity name (fallback to name) |
| `{{company_address}}` | 123 Main St, Bangkok, 10110, Thailand | Full address (comma-separated) |
| `{{contract_number}}` | C-2025-001 | Contract reference number |
| `{{value}}` | THB 120,000.00 | Contract value with currency |
| `{{currency}}` | THB | Currency code only |
| `{{zone_count}}` | 10 | Number of active zones |

## Creating Contract Templates

### 1. Preamble Template
```
This agreement is made on {{start_date}} between:

BMAsia (Thailand) Co., Ltd., with registered address at 725 S-Metro Building... (BMA),

and

{{company_legal_name}}, with registered address at {{company_address}} (Client).

(Together "The Parties")

Whereas BMA is a certified legal reseller of Soundtrack Your Brand...
```

### 2. Payment Terms Template (Thailand)
```
Payment by bank transfer on a net received, paid in full basis to BMA's TMB-Thanachart Bank, Bangkok, Thailand due immediately on invoicing to activate the music subscription. All bank transfer fees are borne by the Client less Withholding Tax required by Thai Law.
```

### 3. Payment Terms Template (International)
```
Payment by bank transfer on a net received, paid in full basis to BMA's HSBC Bank, Hong Kong due immediately as invoiced to activate the music subscription. All bank transfer fees and taxes are borne by the Client.
```

### 4. Activation Terms Template
```
Music service will be activated within 3 business days of receipt of payment and completion of account setup on the Soundtrack Your Brand platform.
```

## Contract Model Fields

### Content Management (choose template OR custom)
```python
contract.preamble_template     # FK to ContractTemplate (type: preamble)
contract.preamble_custom       # TextField - custom text overrides template

contract.payment_template      # FK to ContractTemplate (type: payment_*)
contract.payment_custom        # TextField - custom text overrides template

contract.activation_template   # FK to ContractTemplate (type: activation)
contract.activation_custom     # TextField - custom text overrides template
```

### Service Package
```python
contract.service_items         # M2M to ServicePackageItem
contract.custom_service_items  # JSONField: [{"name": "...", "description": "..."}]
```

Example custom_service_items:
```json
[
  {
    "name": "Priority Support - 24/7",
    "description": "Dedicated support line with 1-hour response time"
  },
  {
    "name": "Quarterly Music Strategy Review",
    "description": "Face-to-face meeting to review music performance"
  }
]
```

### Zone Pricing
```python
contract.show_zone_pricing_detail  # Boolean - show price column in zone table
contract.price_per_zone            # Decimal - price per zone per year
```

### Contact Information
```python
# BMAsia contacts
contract.bmasia_contact_name   = "Norbert Platzer"
contract.bmasia_contact_email  = "norbert@bmasiamusic.com"
contract.bmasia_contact_title  = "Managing Director"

# Customer contacts
contract.customer_contact_name   = "John Smith"
contract.customer_contact_email  = "john.smith@hotel.com"
contract.customer_contact_title  = "General Manager"
```

### Signatory Information (already in use)
```python
contract.bmasia_signatory_name   = "Norbert Platzer"
contract.bmasia_signatory_title  = "Managing Director"
contract.customer_signatory_name = "John Smith"
contract.customer_signatory_title = "General Manager"
```

## Django Admin Setup

### 1. Create Contract Templates

Navigate to: **Admin > Contract Templates > Add Contract Template**

Fields:
- **Name**: "Standard Preamble" or "Thailand Payment Terms"
- **Template Type**: Select from dropdown (preamble, payment_thailand, etc.)
- **Content**: Enter text with `{{variables}}`
- **Is Default**: Check to auto-select for new contracts
- **Is Active**: Must be checked to be available
- **Version**: "1.0" or "2024.1"

### 2. Create Service Package Items

Navigate to: **Admin > Service Package Items > Add Service Package Item**

Fields:
- **Name**: "Playlist Design Assistance"
- **Description**: "Monthly consultation to design and refresh playlists..."
- **Is Standard**: Check to show in contract creation form
- **Display Order**: 1, 2, 3... (controls sort order)

### 3. Assign to Contract

When creating/editing a contract:

**Content Section**:
- Select "Preamble Template" dropdown OR enter "Preamble Custom" text
- Select "Payment Template" dropdown OR enter "Payment Custom" text
- Select "Activation Template" dropdown OR enter "Activation Custom" text

**Service Package Section**:
- Select items from "Service Items" multi-select
- Add JSON to "Custom Service Items" field (if needed)
- Check "Show Zone Pricing Detail" to display price column
- Enter "Price Per Zone" (e.g., 12000.00)

**Contact Information Section**:
- Fill in BMAsia contact fields
- Fill in Customer contact fields

## PDF Generation Workflow

1. **User clicks "Export PDF" on Contract detail page**
2. **System checks contract type**:
   - If `contract_category == 'corporate_master'` → Generate Master Agreement PDF
   - Else → Generate Principal Terms PDF (our enhanced version)
3. **System builds numbered clauses**:
   - Clause 1: Agreement Structure (fixed)
   - Clause 2: Locations (from zones)
   - Clause 3: Commencement Date (from start_date)
   - Clause 4: Duration (calculated)
   - Clause 5: Service Packages (from service_items + custom_service_items)
   - Clause 6: Total Cost (calculated with VAT)
   - Clause 7: Payment Terms (from template/custom/default)
   - Clause 8: Activation (from template/custom/default)
   - Clause 9: Contacts (from contact fields)
4. **System substitutes variables** in all template content
5. **System adds signature section** (using signatory fields)
6. **PDF downloaded** to user's device

## Default Behavior (No Templates/Custom Content)

If a contract has NO templates selected and NO custom content:

- **Preamble**: Default legal text with BMA/Client details
- **Service Items**: Default list (playlist design, activation, monthly refresh, etc.)
- **Payment Terms**: Entity-specific default (Thailand vs Hong Kong)
- **Activation**: "Within 3 business days of payment..."
- **Contacts**: BMAsia defaults to Norbert Platzer, Customer shows "[Customer Contact Name]"

## Tips & Best Practices

### 1. Use Templates for Standard Language
Create templates for commonly used text blocks. This ensures:
- ✅ Consistent language across contracts
- ✅ Legal team approval before use
- ✅ Version tracking of terms
- ✅ Quick contract creation

### 2. Use Custom Text for Special Cases
Use custom fields when:
- Contract requires unique terms
- One-off negotiated language
- Customer-specific requirements
- Quick overrides without template creation

### 3. Service Package Strategy
- Create ServicePackageItem records for standard offerings
- Use custom_service_items JSON for contract-specific services
- Keep descriptions clear and professional
- Order items logically (most important first)

### 4. Zone Pricing
- Enable `show_zone_pricing_detail` for transparent per-zone pricing
- Disable for contracts with custom zone-specific rates
- Use `price_per_zone` for standard per-zone annual fees

### 5. Contact Information
- Always fill in bmasia_contact_* fields (defaults to Norbert)
- Get customer_contact_* from primary decision maker
- Ensure emails are accurate for contract communications
- Use formal titles (Managing Director, General Manager, etc.)

## Troubleshooting

### Issue: Variables not being replaced
**Solution**: Check variable syntax - must be exactly `{{variable_name}}` with double curly braces

### Issue: Zone table not showing
**Solution**: Ensure contract has active zones linked via ContractZone records

### Issue: Service items not appearing
**Solution**:
1. Check that ServicePackageItem records exist and are assigned to contract
2. Verify custom_service_items JSON is valid format
3. Check that default items are being used if none specified

### Issue: Wrong payment terms showing
**Solution**: Check contract priority:
1. Uses `payment_custom` first (if not empty)
2. Then `payment_template.content` (if template selected)
3. Finally entity default (based on billing_entity)

### Issue: Contacts showing as "[Customer Contact Name]"
**Solution**: Fill in customer_contact_name, customer_contact_email, customer_contact_title fields in contract

### Issue: PDF download fails
**Solution**:
1. Check that company has billing_entity set
2. Verify contract has start_date and end_date
3. Check server logs for ReportLab errors
4. Ensure contract.company exists

## API Integration (Future)

For future frontend integration:

```javascript
// Get contract with templates/items
GET /api/contracts/{id}/
Response includes:
  - preamble_template: { id, name, content }
  - payment_template: { id, name, content }
  - activation_template: { id, name, content }
  - service_items: [{ id, name, description }]
  - custom_service_items: [{ name, description }]

// Get available templates
GET /api/contract-templates/?template_type=preamble
GET /api/contract-templates/?template_type=payment_thailand

// Get available service items
GET /api/service-package-items/?is_standard=true

// Download PDF
GET /api/contracts/{id}/download_pdf/
```

## Example Complete Contract Setup

```python
contract = Contract.objects.get(id=123)

# Select templates
contract.preamble_template = ContractTemplate.objects.get(name="Standard Preamble")
contract.payment_template = ContractTemplate.objects.get(name="Thailand Payment Terms")
contract.activation_template = ContractTemplate.objects.get(name="Standard Activation")

# Add service items
playlist_design = ServicePackageItem.objects.get(name="Playlist Design")
monthly_refresh = ServicePackageItem.objects.get(name="Monthly Music Refresh")
contract.service_items.set([playlist_design, monthly_refresh])

# Add custom service
contract.custom_service_items = [
    {"name": "VIP Events Support", "description": "On-site music management for special events"}
]

# Configure zone pricing
contract.show_zone_pricing_detail = True
contract.price_per_zone = 12000.00

# Set contacts
contract.bmasia_contact_name = "Norbert Platzer"
contract.bmasia_contact_email = "norbert@bmasiamusic.com"
contract.bmasia_contact_title = "Managing Director"

contract.customer_contact_name = "John Smith"
contract.customer_contact_email = "john.smith@hotel.com"
contract.customer_contact_title = "General Manager"

# Set signatories
contract.bmasia_signatory_name = "Norbert Platzer"
contract.bmasia_signatory_title = "Managing Director"
contract.customer_signatory_name = "John Smith"
contract.customer_signatory_title = "General Manager"

contract.save()
```

## Version History

- **v1.0** (Dec 16, 2025): Initial enhanced implementation with numbered clauses
  - Added helper methods for variable substitution
  - Implemented 9-clause structure
  - Added zone table with pricing
  - Added service package bullet list
  - Added contacts section
  - Template support for preamble, payment, activation

---

**For Technical Support**: See `PRINCIPAL_TERMS_PDF_ENHANCEMENT_SUMMARY.md` for implementation details.
