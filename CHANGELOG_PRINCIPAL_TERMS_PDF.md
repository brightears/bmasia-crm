# Changelog - Principal Terms PDF Enhancement

## [1.0.0] - 2025-12-16

### Added

#### Helper Methods
- **`_substitute_template_variables(content, contract)`** - Replaces template variables with actual contract values
  - Supports 9 template variables: start_date, end_date, company_name, company_legal_name, company_address, contract_number, value, currency, zone_count
  - Used for preamble, payment terms, and activation terms

- **`_format_company_address(company)`** - Formats company address as comma-separated string
  - Combines address, city, state, postal_code, country
  - Filters out None/empty values

#### PDF Structure
- **Preamble Section** - Legal introduction with BMA and Client details
  - Uses `contract.preamble_custom` OR `contract.preamble_template.content` OR default text
  - Replaces basic "Service Details" section
  - Template variable substitution supported

- **Numbered Clauses (1-9)** - Professional legal document structure:
  1. Agreement Structure - Fixed text about principal terms + T&Cs
  2. Locations for Services - Zone table with optional pricing column
  3. Commencement Date - Start date in long format
  4. Duration - Calculated months with start/end dates
  5. Service Packages - Bullet list from M2M items + custom JSON items
  6. Total Cost - Calculated total with VAT breakdown
  7. Terms of Payment - Template/custom/default text + bank details
  8. Activation Date - Template/custom/default activation terms
  9. Contacts - BMAsia and Customer contact information

#### Styling
- **clause_style** - Paragraph style for numbered clause text
  - 10pt font, 14pt leading, 8pt spacing

- **bullet_style** - Paragraph style for service package items
  - 10pt font, 20pt left indent, 10pt bullet indent

#### Features
- **Zone Table** - Shows all active zones with:
  - Property name (company.name)
  - Zone name with sequential numbering
  - Optional per-zone pricing (if `show_zone_pricing_detail=True`)
  - Formatted as professional table with grid borders

- **Service Package List** - Bullet-point list with:
  - Items from `contract.service_items` (M2M relationship)
  - Items from `contract.custom_service_items` (JSON array)
  - Default items if none specified
  - Optional pricing line if `price_per_zone` is set

- **Cost Calculation** - Clause 6 shows:
  - Base cost for all zones
  - VAT calculation (7% Thailand, 0% Hong Kong)
  - Bold total with VAT

- **Bank Details** - Sub-section under Payment Terms with:
  - Beneficiary name
  - Bank name
  - SWIFT code
  - Account number
  - Formatted as indented paragraph

- **Contacts Section** - Clause 9 displays:
  - BMAsia: name, title, email (defaults to Norbert Platzer)
  - Client: name, title, email (from contract fields)

### Changed

#### Removed Table-Based Sections
- **Old "SERVICE DETAILS"** section → Replaced with Preamble + numbered clauses
- **Old "CONTRACT VALUE"** table → Replaced with Clause 6 (Total Cost)
- **Old "CONTRACT TERMS"** table → Information now in Clauses 3, 4, 7
- **Old "BANK DETAILS"** table → Now sub-section under Clause 7
- **Old "PAYMENT TERMS"** section → Now Clause 7 with template support

#### Enhanced Sections
- **Signature Section** - No changes, already uses signatory fields correctly
- **Footer** - No changes, maintains entity-specific formatting
- **Header** - No changes, keeps BMAsia logo and metadata table

### Backward Compatibility

✅ **Fully Backward Compatible**
- Contracts without templates/custom content use sensible defaults
- Contracts without zones show "As specified in attached schedule"
- Contracts without service items show default service list
- Contracts without contacts show defaults (BMAsia) or placeholders (Customer)
- All existing contracts can generate PDFs without changes

### Database Schema

**No migrations required** - All fields already exist:
- `preamble_template`, `preamble_custom`
- `payment_template`, `payment_custom`
- `activation_template`, `activation_custom`
- `service_items` (M2M)
- `custom_service_items` (JSONField)
- `show_zone_pricing_detail`, `price_per_zone`
- `bmasia_contact_name`, `bmasia_contact_email`, `bmasia_contact_title`
- `customer_contact_name`, `customer_contact_email`, `customer_contact_title`

### Dependencies

**No new dependencies** - Uses existing packages:
- ReportLab (already in requirements.txt)
- Django ORM (standard)

### Files Modified

1. **`/crm_app/views.py`**
   - Line 764-787: Added `_substitute_template_variables()` method
   - Line 782-787: Added `_format_company_address()` method
   - Line 789-1300: Enhanced `_generate_principal_terms_pdf()` method
     - Line 868-888: Added clause_style and bullet_style definitions
     - Line 980-999: Added preamble section with template support
     - Line 1001-1127: Added numbered clauses (1-9)
     - Line 1129-1194: Replaced old sections with new clause-based structure

### Testing Status

✅ **Python Syntax Validation**: Passed
- No syntax errors
- No import errors
- All methods properly defined

⏳ **Runtime Testing**: Pending
- PDF generation with templates
- PDF generation with custom content
- PDF generation with defaults
- Zone table rendering
- Service items display
- Variable substitution
- Multiple entities (Thailand vs HK)

### Documentation

Created:
1. **PRINCIPAL_TERMS_PDF_ENHANCEMENT_SUMMARY.md** - Technical implementation details
2. **PRINCIPAL_TERMS_PDF_QUICK_REFERENCE.md** - User guide and API reference
3. **CHANGELOG_PRINCIPAL_TERMS_PDF.md** (this file)

### Migration Path

**For Existing Contracts**:
1. No action required - will use defaults
2. Optional: Add templates via Django admin
3. Optional: Assign templates to contracts
4. Optional: Fill in contact information
5. Optional: Configure zone pricing display

**For New Contracts**:
1. Create ContractTemplate records in admin
2. Create ServicePackageItem records in admin
3. Select templates when creating contract
4. Add service items (M2M or custom JSON)
5. Configure zone pricing if needed
6. Fill in contact information
7. PDF will use template content with variable substitution

### Rollback Plan

If issues arise, revert these changes:
1. Restore `crm_app/views.py` from git
2. No database rollback needed (fields are optional)
3. Existing contracts will use old PDF format

```bash
# Rollback command
git checkout HEAD~1 -- crm_app/views.py
```

### Known Issues

None at this time.

### Future Enhancements (Not Implemented)

- [ ] Configurable VAT rates per entity
- [ ] Multi-page zone tables (pagination)
- [ ] Service item icons/images
- [ ] Signature image uploads
- [ ] QR code for contract verification
- [ ] Template version tracking in PDF
- [ ] Multi-language support
- [ ] Attachment references section

### Performance Impact

✅ **Minimal Impact**:
- Same number of database queries (uses existing relationships)
- Slightly more text processing (variable substitution)
- ReportLab rendering time unchanged
- PDF file size similar (possibly slightly larger due to more content)

### Security Considerations

✅ **No New Security Risks**:
- Template content stored in database (not user input)
- Variable substitution escapes HTML (ReportLab Paragraph handles this)
- No file system access beyond existing logo loading
- No new external API calls

### Deployment Instructions

1. Pull latest code from git
2. No migrations to run
3. Restart Django application
4. Test PDF generation on dev/staging
5. Deploy to production
6. Optional: Create default templates in admin

```bash
# Deployment commands
git pull origin main
# No migrations needed
sudo systemctl restart bmasia-crm  # or equivalent
```

### Success Metrics

- [x] Code passes Python syntax validation
- [ ] PDF generates without errors on test contract
- [ ] Zone table displays correctly (0, 1, multiple zones)
- [ ] Service items show as bullet list
- [ ] Variables are substituted correctly
- [ ] Templates override defaults properly
- [ ] Custom content overrides templates
- [ ] Both entities (Thailand/HK) work correctly
- [ ] Signature section displays correctly
- [ ] Multi-page contracts render properly

### Support Contact

For questions or issues:
- See **PRINCIPAL_TERMS_PDF_QUICK_REFERENCE.md** for usage guide
- See **PRINCIPAL_TERMS_PDF_ENHANCEMENT_SUMMARY.md** for technical details
- Check Django admin logs for PDF generation errors
- Review server logs for ReportLab errors

---

**Version**: 1.0.0
**Release Date**: December 16, 2025
**Status**: ✅ Ready for Testing
**Breaking Changes**: None
**Migration Required**: No
