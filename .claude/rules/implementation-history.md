# Implementation History - BMAsia CRM

## January 2026

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
