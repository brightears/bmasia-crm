# Implementation History - BMAsia CRM

## February 2026

### Feb 9, 2026 - Filter Bar Consistency (All List Pages)

**Problem**: Each list page had inconsistent filter bars — date pickers that were clunky and often non-functional (backend didn't support the date range params sent by frontend), no sort dropdowns, and some misleading columns.

**Solution**: Standardized all 4 list pages with the same pattern:

```
┌──────────────────────────────────────────────────────────────┐
│  🔍 Search...  [Filter1 ▼]  [Filter2 ▼]  [Sort: Option ▼]   │
└──────────────────────────────────────────────────────────────┘
```

**Changes per page:**

| Page | Removed | Added | Other |
|------|---------|-------|-------|
| **Companies** | — | Sort dropdown (6 options) | Already done Feb 7 |
| **Contacts** | From Date, To Date, Clear btn, Last Contact column | Sort dropdown (6 options) | Status only shows "Inactive" chip; fixed `is_active` filter |
| **Contracts** | Start Date, End Date, Clear btn | Sort dropdown (6 options) | Renamed "Renewal Date" → "Renewal" |
| **Quotes** | Valid From, Valid Until, Clear btn | Sort dropdown (6 options) | — |

**Backend** (`crm_app/views.py`): Added `updated_at`, `company__name` to ordering_fields for ContactViewSet, ContractViewSet, and QuoteViewSet. Also added `contract_number` for ContractViewSet.

**Frontend pattern** (all pages):
- Flex layout (`display: 'flex', gap: 2`) replaces Grid
- `useCallback` for data loading functions
- `ordering: sortBy` param sent to API
- Sort dropdown uses `Sort` icon as startAdornment (no label)
- Page resets to 0 on filter/sort change

**Sort options per page:**
- **Companies**: Name A-Z/Z-A, Newest/Oldest, Recently Updated, Country
- **Contacts**: Name A-Z/Z-A, Newest/Oldest, Recently Updated, Company
- **Contracts**: Start Date Newest/Oldest, Ending Soonest, Highest Value, Company, Contract Number
- **Quotes**: Newest/Oldest, Expiring Soonest, Highest Value, Quote Number, Company

**Removed dependencies**: `DatePicker`, `LocalizationProvider`, `AdapterDateFns`, `GridLegacy` from Contacts/Contracts/Quotes pages.

---

### Feb 7, 2026 - Company List Sorting

**Problem**: Companies page only listed alphabetically by name with a search bar. Sales requested: "Can we sort company entries by creation date?"

**Backend** (`crm_app/views.py`): Added `updated_at` to CompanyViewSet ordering_fields:
```python
ordering_fields = ['name', 'created_at', 'updated_at', 'industry', 'country']
```

**Frontend** (`Companies.tsx`): Added sort dropdown next to search bar with 6 options:
- Name A-Z (`name`) — default
- Name Z-A (`-name`)
- Newest First (`-created_at`)
- Oldest First (`created_at`)
- Recently Updated (`-updated_at`)
- Country (`country`)

Passes `ordering` param to API. Sort change resets pagination to page 0. No new API methods needed — `getCompanies()` already passes through all params.

---

### Feb 7, 2026 - Zone Table PDF Improvements

**Problem 1**: Zone names from Soundtrack API include the full property prefix (e.g., "Paradise Island Resort Maldives - Bageecha") causing overflow in the Zone column since property is already shown in its own column.

**Fix**: Use `str(zone)` instead of `zone.name` in `_build_zones_table()`. Zone model's `__str__()` strips the prefix after `" - "` (e.g., "Bageecha").

**Problem 2**: Long company names (e.g., "Paradise Island Resort & Spa") overflow the Property column into Service.

**Fix**: Wrap property name in ReportLab `Paragraph` object (instead of plain string) to enable automatic word-wrap within the cell.

---

### Feb 7, 2026 - Manual Zone Creation for Contracts

**Problem**: Soundtrack zones could only be added via API dropdown - no manual creation. When Soundtrack Account ID didn't exist yet (account created after contract signing), users couldn't add any Soundtrack zones. Also, API preview zones had non-DB IDs that failed when saving to contracts.

**Solution** (`EnhancedZonePicker.tsx`):
1. **Manual "Add New Zone" for Soundtrack**: Text input + button (mirrors Beat Breeze pattern). Creates Zone in DB with `platform: 'soundtrack'`.
2. **"Import from Soundtrack API" button**: When preview zones found via API, one-click bulk-creates them as DB zones and auto-selects them.
3. **Fixed zone loading**: Dropdown always shows DB zones (proper UUIDs). Preview zones shown separately with Import action, not mixed into dropdown.

**No backend changes needed** - `POST /api/v1/zones/` already supported creating zones with any platform.

---

### Feb 7, 2026 - HK Stamp Aspect Ratio Fix

**Problem**: HK stamp (`BMAsia Stamp.png`) is 854x772px (not square). Rendered at fixed 1.6x1.6 inches, it appeared stretched/distorted. Thai stamp (`BMAsia Thai Stamp.png`) is 1000x1000px and rendered correctly.

**Fix** (`crm_app/views.py`): After loading stamp image, auto-detect aspect ratio and adjust height:
```python
iw, ih = stamp_img.imageWidth, stamp_img.imageHeight
if iw and ih and iw != ih:
    ratio = ih / iw
    stamp_img = Image(stamp_path, width=1.6*inch, height=1.6*inch * ratio)
```

Applied to both stamp locations: `_build_signature_blocks_table()` and master agreement signature section.

---

### Feb 7, 2026 - Differentiate Soundtrack vs Beat Breeze Zones in Contract PDFs

**Problem**: Contract PDF zones table showed all zones as generic "Zone 1, Zone 2..." without distinguishing Soundtrack from Beat Breeze. They have different licensing and pricing.

**Solution**: Added "Service" column to zones table (`_build_zones_table()` in `crm_app/views.py`):
- Zones grouped by platform: Soundtrack first, then Beat Breeze
- "Service" column shows "Soundtrack" or "Beat Breeze" per group
- Zone numbering restarts per service group
- Service name merged vertically when a platform has multiple zones
- Property name merged across all rows (existing behavior)

**Table format**:
```
Property    | Service     | Zone
Bright Ears | Soundtrack  | Zone 1: Pool Bar
            | Beat Breeze | Zone 1: Gym
            |             | Zone 2: Lobby
```

**Column widths**: Property 2.0", Service 1.3", Zone 2.2" (without pricing) / Property 1.7", Service 1.2", Zone 1.8", Price 1.7" (with pricing)

**Code consolidation**: Replaced hardcoded zone table (~lines 1590-1631) with call to shared `_build_zones_table()` helper - single source of truth for all contract PDF zone tables.

**Participation agreement**: Cleaned up labels from raw "SOUNDTRACK"/"BEATBREEZE" to "Soundtrack"/"Beat Breeze", renamed "Platform" column to "Service".

**Note**: Quotes and invoices do NOT render zone tables - only contracts do.

---

### Feb 7, 2026 - Company Address Form Consolidation & PDF Address Fix

**Problem**: Company form had overlapping address fields in two sections (City/Country in Basic Info + Address Line 1/2, State, Postal Code in a separate section). Filling both caused duplication in PDFs. Also, PDF address rendering split commas within field values and showed "Other" country.

**Company Form Reorganization** (`CompanyForm.tsx`):
- Removed old "Address Information" section and City from Basic Information
- Created single "Company Address" section: Address Line 1, Address Line 2, City, State/Province, Postal Code
- Country stays in Basic Information (drives billing entity auto-selection + seasonal campaigns)
- Each field appears exactly once - no duplication

**Form section order**:
1. Basic Information (Name, Legal Entity, Industry, Country, Billing Entity, Website)
2. Corporate Structure
3. Contact Information (Phone, Email)
4. Company Address (Address Line 1/2, City, State/Province, Postal Code)
5. Integration & Settings
6. Communication Preferences
7. Additional Notes

**PDF Address Fix** (`crm_app/views.py`):
- Added `format_address_multiline(company)` standalone function (line ~79)
- Builds address line-by-line from individual fields instead of `full_address.replace(', ', '<br/>')`
- Prevents commas within field values from being split into separate lines
- Filters out "Other" country (dropdown catch-all value) from professional documents
- Applied to all 5 PDF locations: Contract (3 types), Invoice, Quote
- Updated `_format_company_address()` to also filter "Other" for contract preambles

**CompanyDetail.tsx**: "Full Address" display only shows when it contains data beyond city+country

**No backend model/migration changes** - frontend-only form reorganization + backend PDF rendering fix

---

## January 2026

### Jan 22, 2026 - Signature Block Enhancements

**Image Size Increase**:
- Signature: 2.2×0.9 → 2.8×1.1 inches
- Stamp: 1.3×1.3 → 1.6×1.6 inches
- Table column widths updated to match

**Position & Alignment Tuning**:
- `LEFTPADDING`: 25 → 140 (iterative adjustments to center signature over line)
- Customer spacer: 0.85 → 1.15 inch (align both signature lines horizontally)

**Gap Reduction**:
- Strip trailing `<br/>` tags before `{{signature_blocks}}` to reduce whitespace
- Prevents extra empty page at end of contract

**Final Values** (`_build_signature_blocks_table()`):
| Setting | Value |
|---------|-------|
| Signature size | 2.8×1.1 inch |
| Stamp size | 1.6×1.6 inch |
| LEFTPADDING | 140 |
| BOTTOMPADDING | -35 |
| Customer spacer | 1.15 inch |

---

### Jan 22, 2026 - Zones Table KeepTogether (Final Fix)

**Problem**: When template has `<br/><br/>` right before `{{zones_table}}`, splitting at last break left heading in bulk_content

**Solution**: If `heading_content` is empty after split, use second-to-last `<br/><br/>` to capture actual heading

**Template structure handled**:
```
...clause 1...<br/><br/>
2. Locations for Provision of Services:<br/><br/>
{{zones_table}}
```

**Result**: Heading "2. Locations for Provision of Services:" now stays with zones table on same page

---

### Jan 21, 2026 - PDF Layout Fixes

**Zones Table Page Split**:
- Wrapped zones table in `KeepTogether()` to prevent header/data splitting across pages

**Signature Blocks Alignment**:
- Added `VALIGN: TOP` to inner cell tables for proper vertical alignment
- Adjusted signature `BOTTOMPADDING` from -20 to -35 for better line overlap

---

### Jan 21, 2026 - Signature Blocks Template Variable

**Feature**: `{{signature_blocks}}` for side-by-side signatures in contract PDFs

**Implementation**:
- Created `_build_signature_blocks_table()` helper method
- BMAsia (left column): signature image + stamp, name, title, company, auto-dated
- Client (right column): signature space, name, title, company, blank date
- Supports additional customer signatories from JSONField
- Recursive `render_segment()` function handles both `{{zones_table}}` and `{{signature_blocks}}`

**Usage**: Add `{{signature_blocks}}` at end of template for two-column signature table

---

### Jan 21, 2026 - Zones Table Position Fix

**Problem**: When `{{zones_table}}` in template, zones appeared after signatures (at end of PDF)
**Solution**: Split template at `{{zones_table}}` marker, insert proper Table flowable

**Implementation**:
- Created `_build_zones_table()` helper method (reusable Table flowable)
- Template splits at `{{zones_table}}` - renders before content, inserts table, renders after
- Backwards compatible: if no marker, table appends at end

**User Action**: Add `{{zones_table}}` between clause 2 and 3 in templates

---

### Jan 21, 2026 - Contract Template System Complete

**Key Insight**: Templates contain ENTIRE contract structure (not just preamble snippets)
- User creates full contract template with all clauses, signature blocks in HTML format
- Templates now determine PDF format (Standard, Corporate Master, Participation)
- PDF renders ONLY template content - no duplicate hardcoded clauses

**PDF Generation Fix**:
- When template exists: renders template content only, skips hardcoded clauses
- When no template: uses existing hardcoded clause structure (backwards compatible)
- Added `{{zones_table}}` special variable for inline zone list insertion
- Zones table appended after template if `{{zones_table}}` not used
- Signature section always renders normally

**PDF Format on Templates**:
- Added `pdf_format` field to ContractTemplate model
- Choices: `standard`, `corporate_master`, `participation`
- PDF routing uses template's `pdf_format` instead of contract's `contract_category`
- Backwards compatible: falls back to `contract_category` if no template

**ContractForm Simplification**:
- Removed Contract Category dropdown
- Template selection now required and determines PDF structure
- When template selected, auto-sets `contract_category` from template's `pdf_format`
- Master Contract dropdown shows for participation templates
- Custom Terms shows for corporate master templates

**ContractTemplateForm Updates**:
- Added PDF Format dropdown (Standard, Corporate Master, Participation)
- Added `{{zones_table}}` to variable guide
- Removed Template Type dropdown (not needed)
- Removed Default switch (just Active/Inactive)

**Template Variables Available**:
- Company: `{{company_name}}`, `{{legal_entity_name}}`, `{{client_address}}`
- Contact: `{{contact_name}}`, `{{contact_email}}`
- Contract: `{{contract_number}}`, `{{start_date}}`, `{{end_date}}`, `{{agreement_date}}`
- Financial: `{{value}}`, `{{currency}}`, `{{billing_frequency}}`, `{{payment_terms}}`
- Zones: `{{venue_names}}`, `{{number_of_zones}}`, `{{zones_table}}`
- Signatories: `{{client_signatory_name}}`, `{{client_signatory_title}}`

**Migration**: `0055_contracttemplate_pdf_format.py`

### Jan 15, 2026 - Contract Template Management

**Contract Template Dropdown in ContractForm**
- Added template selection dropdown after Contract Category
- Loads active templates from `/api/v1/contract-templates/`
- Saves selection as `preamble_template` on contract
- Pre-selects saved template when editing

**Contract Templates Management Page** (`/contract-templates`)
- New frontend page: `ContractTemplates.tsx`
- Full CRUD: Create, Edit, Duplicate, Delete templates
- Search by name/content
- Simplified form with variable guide (click to copy, double-click to insert)
- Navigation: Administration → Contract Templates
- API methods: `createContractTemplate`, `updateContractTemplate`, `deleteContractTemplate`

### Jan 14, 2026 - Contract Form Improvements

**Contract Tax Fields (VAT Support)**
- Added `tax_rate`, `tax_amount`, `total_value` fields to Contract model
- Auto-calculation: THB contracts get 7% VAT, USD contracts 0% tax
- Helper text in form: "Enter base price (excluding VAT)"
- Live VAT calculation display in ContractForm
- Migration: `0053_contract_tax_fields.py`

**Contract Content Section Removal**
- Removed unused template dropdowns (Preamble, Payment Terms, Activation Terms)
- Removed Service Package multi-select and custom service items
- These were built but never integrated into PDF generation
- Simplified form by ~300 lines of code

**Multiple Customer Signatories**
- Added `additional_customer_signatories` JSONField to Contract model
- UI: "Add Customer Signatory" button with name/title fields + delete button
- Contract PDF renders all signatories with signature lines
- Migration: `0054_contract_additional_signatories.py`

### Jan 14, 2026 - Finance PDF/Excel Export (Phase 7)
- **FinanceExportService** (`crm_app/services/finance_export_service.py`)
  - ReportLab PDF generation with BMAsia branding (#FFA500)
  - openpyxl Excel generation with auto-fit columns
- **Export Endpoints** added to ViewSets:
  - `/api/v1/profit-loss/export/pdf/` and `/excel/`
  - `/api/v1/cash-flow/export/pdf/` and `/excel/`
  - `/api/v1/balance-sheet/export/pdf/` and `/excel/`
- **Frontend Download Buttons** in ProfitLoss.tsx, CashFlow.tsx, BalanceSheet.tsx
- **UI Fix**: Toggle buttons (Monthly/Year-to-Date) now have `whiteSpace: nowrap`

### Jan 13, 2026 - Finance Module Phases 4, 5 & 6
- **Balance Sheet (Phase 6)**
  - BalanceSheetSnapshot model for quarterly snapshots with manual overrides
  - BalanceSheetService calculates Assets, Liabilities, Equity
  - Data: CashFlowSnapshot (cash), Invoice (AR), ExpenseEntry (CapEx/AP), P&L (retained earnings)
  - Depreciation: Thailand/HK rates (Computer 33.33%/3yr, Office 20%/5yr)
  - BalanceSheet.tsx with KPI cards, hierarchical statement table, quarterly trend chart
  - API: `/api/v1/balance-sheet/quarterly/`, `/trend/`
  - Migration: `0051_balance_sheet_module.py`

### Jan 13, 2026 - Finance Module Phases 4 & 5
- **Cash Flow Statement (Phase 5)**
  - CashFlowSnapshot model for monthly data with manual overrides
  - CashFlowService: Operating, Investing, Financing activities
  - Data: Invoice.paid_date (customers), ExpenseEntry.payment_date (suppliers)
  - CashFlow.tsx with KPI cards, statement table, trend chart
  - API: `/api/v1/cash-flow/monthly/`, `/ytd/`, `/trend/`
  - Migration: `0050_cash_flow_module.py`

- **Profit & Loss Report (Phase 4)**
  - ProfitLossService: monthly, YTD, comparative (YoY), trend
  - Structure: Revenue → COGS → Gross Profit → OpEx → Net Profit
  - ProfitLoss.tsx with KPI cards, P&L table, trend chart
  - API: `/api/v1/profit-loss/monthly/`, `/ytd/`, `/comparative/`, `/trend/`

### Jan 12, 2026 - Contract PDF Improvements
- Chris Andrews signature auto-added to BMAsia side
- Company stamps: Thai stamp vs International stamp
- BMAsia date auto-filled (contracts pre-signed)
- FROM/BILL TO card styling matching Quote PDF
- Zone table: Property name merged cells
- Static files: `crm_app/static/signatures/`

### Jan 10, 2026 - Quote PDF Improvements
- Removed "Status" from header
- FROM/BILL TO card styling
- Compact bank details (8pt font)
- Notes field only shows if content exists

### Jan 9, 2026 - Quote Form Enhancements
- Product/Service dropdown with auto-populate descriptions
- Terms & Conditions presets
- UUID serialization fix for audit logs
- Custom JSON Renderer for DRF

### Jan 6-7, 2026 - Zone Management & Email Routing
- Contract-level Soundtrack Account ID
- Live Zone Preview from API
- Orphan detection during sync
- Email sender routing by sequence type
- Per-user SMTP configuration complete

### Jan 4-5, 2026 - Seasonal Automation & Contact Preferences
- 10 seasonal email templates (Christmas, CNY, Diwali, etc.)
- Country-based targeting via SEASONAL_COUNTRY_MAP
- SeasonalTriggerDate model for variable holidays
- Granular contact email preferences (4 toggles)
- Multi-year contract support (send_renewal_reminders toggle)

## November 2025

### Nov 26, 2025 - Email Automations Consolidation
- Merged Email Automation + Email Sequences
- Single page with filter tabs (All/Automatic/Manual)
- AutoEnrollmentService for automatic enrollment
- 3 pre-built system automations

### Nov 19, 2025 - Email Sequences (Drip Campaigns)
- Multi-step automation with conditional logic
- Time-based delays and scheduling
- Enrollment tracking with lifecycle management
- Cron job processing every 20 minutes

## October 2025

### Oct 12, 2025 - Email System Complete
- Per-user SMTP system with intelligent fallback
- EmailSendDialog component
- PDF generation fixed for all document types
- Production testing complete

### Oct 11, 2025 - Contract Management
- Currency display with locale mapping
- PDF download functionality
- Email infrastructure started

## December 2025

### Contract Content Management System
- ContractTemplate model (preamble, payment terms, activation)
- ServicePackageItem model (10 default items)
- ContractDocument model for attachments
- CorporatePdfTemplate model (Hilton HPA format)

## Migration History (Recent)
- `0054_contract_additional_signatories.py` - Multiple customer signatories
- `0053_contract_tax_fields.py` - VAT/tax support for contracts
- `0052_contract_status_simplification.py` - Contract status cleanup
- `0051_balance_sheet_module.py` - BalanceSheetSnapshot model
- `0050_cash_flow_module.py` - CashFlowSnapshot model
- `0049_expense_module.py` - Expense tracking
- `0047_zone_management_improvements.py` - Zone improvements
- `0046_soundtrack_offline_alerts.py` - Offline alerts
- `0045_contract_send_renewal_reminders.py` - Multi-year support
- `0044_contact_email_preferences.py` - Email preferences
- `0043_seasonal_automation_system.py` - Seasonal campaigns
