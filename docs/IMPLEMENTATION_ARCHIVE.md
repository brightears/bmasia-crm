# Implementation History Archive

> **Note**: This file contains archived implementation history (Feb 11, 2026 and earlier). It is NOT automatically loaded by Claude Code. For recent implementation history (Feb 12+), see `.claude/rules/implementation-history.md`.

---

## February 2026 (Feb 7-11)

### Feb 11, 2026 - ContractForm UI Cleanup & Line Items → PDF

**Problem**: ContractForm was cluttered with redundant fields and sections. Line items existed in the form but weren't connected to the PDF, resulting in generic contract language instead of itemized pricing.

**1. Declutter Line Items Table** (`ContractForm.tsx`):
- Widened dialog from `maxWidth="md"` (960px) to `maxWidth="lg"` (1280px) — matches InvoiceForm
- Removed Discount % column from line items table (8→7 columns: Product/Service, Description, Qty, Unit Price, Tax %, Line Total, Actions)
- Removed Zone Pricing section entirely (redundant with line items for mixed Soundtrack/Beat Breeze pricing)
- Fixed spinner arrows on Financial Terms Discount % field
- When importing from quote, discount is folded into unit price (e.g., $14K at 10% off → $12,600 at 0% discount)

**2. Connect Line Items to PDF + Auto-Calculate Value**:
- Frontend auto-sets contract value from line items total on save
- Backend serializer (`ContractSerializer.create/update`) auto-sums `line_items.line_total` → `contract.value`, recalculates tax fields
- Contract PDF shows line items breakdown when contract has `line_items` array
- Legacy contracts without line items fall back to "X zones for Y per month" format (backward compatible)
- Fixed duplicate "THB THB" bug in PDF total cost clause

**3. Simplify Financial Terms → Payment & Billing** (`ContractForm.tsx`):
- Removed Contract Value field (auto-calculated from line items)
- Removed Tax Calculation display (moved to Line Items summary)
- Removed Discount % field (deprecated in favor of per-item discounts)
- Renamed section "Financial Terms" → "Payment & Billing" (Currency + Payment Terms + Billing Frequency only)
- Line Items summary now shows Subtotal + VAT (for THB) + Total
- Payment & Billing section order: Currency, Payment Terms, Billing Frequency

---

### Feb 11, 2026 - Contract Document Cross-Leak Fix

**Problem**: When viewing "Bright Ears" contract documents, Shangri-La documents appeared in the list. Root cause: `ContractDocumentViewSet` had **no `get_queryset()` override** — returned ALL documents.

**Fix** (`crm_app/views.py`):
- Added `get_queryset()` override to `ContractDocumentViewSet` to filter by `contract_id` param
- Added client-side safety filter in `ContractDocuments.tsx`

---

### Feb 11, 2026 - Contract Line Items + Quote→Contract→Invoice Data Chain

**Feature Overview**: Complete data flow from Quote → Contract → Invoice with persistent line items and source tracking.

- **ContractLineItem Model**: New model mirroring QuoteLineItem
- **Contract quote FK**: Optional, tracks source quote for audit trail
- **ContractForm**: Line Items section with Product/Service dropdown, Source Quote dropdown
- **InvoiceForm**: Prioritizes contract `line_items` when available
- Migration: `0063_contract_line_items.py`

---

### Feb 11, 2026 - Invoice Auto-Fill from Contract: Zones, Service Period, Qty & UI Polish

- Zone Description Auto-Fill with platform grouping (Soundtrack/Beat Breeze)
- Service Period fields auto-filled from contract dates
- Quantity = Zone Count (was always 1)
- Migration: `0062_invoice_service_period.py`

---

### Feb 10, 2026 - Invoice Line Items Persistence, PDF Fixes & Edit Fix

- **InvoiceLineItem Model**: New model, persisted to DB
- **PDF Page Breaks**: KeepTogether for Bank Details + Payment sections
- **Edit Blank Page Fix**: Optional chaining on `line_items?.length`
- Migration: `0060_invoice_line_items.py`

---

### Feb 10, 2026 - Invoice Payment Terms Persistence + PDF Improvements

- Added `payment_terms` and `payment_terms_text` fields to Invoice model
- Entity-specific bank instructions (Thailand TMB, international HSBC)
- Migration: `0061_invoice_payment_terms_fields.py`

---

### Feb 10, 2026 - Invoice Audit: Contract Auto-Fill, Smart VAT/Currency & Optional Contract

- Added `company` FK to Invoice (always required)
- Made `contract` FK optional (null=True)
- Smart currency: THB (Thailand) or USD (international)
- Migration: `0059_invoice_optional_contract.py`

---

### Feb 10, 2026 - Dashboard v2: Entity Filter, Revenue Breakdown & Churn Tracking

- Entity filter on all dashboard querysets
- Revenue breakdown: new_revenue, renewal_revenue, churned_revenue, net_revenue
- Revenue trend with stacked AreaChart

---

### Feb 10, 2026 - Dashboard Redesign: Business Health Snapshot

- 6 KPI cards with trend indicators
- Pipeline funnel with Recharts BarChart
- Deleted 14 unused components (~7,000 lines)
- Default landing: `/` → `/today`

---

### Feb 10, 2026 - "Today" Action Center

- ActionCenterViewSet with urgency tiers (Overdue, Today, Coming Up)
- Role-based filtering for Sales users
- Replaced QuickActions placeholder

---

### Feb 10, 2026 - Tasks Audit & Improvements (5 Phases)

- Backend Model Fix: Added FKs for opportunity, contract, contact
- Email Notifications on assignment
- Daily Digest Cron: `crn-d65drn75r7bs73cpu72g`
- Simplified Kanban: 3 columns (To Do, In Progress, Done)
- Auto-create task from Opportunity
- Migration: `0058_task_improvements.py`

---

### Feb 10, 2026 - Opportunities PDF Design Fixes

- Changed THB symbol from `'฿'` to `'THB '` (Helvetica font limitation)
- Skip internal keys (`_entity_raw`) in PDF header

---

### Feb 10, 2026 - Prospect Workflow: Auto-Infer service_type from Quotes

- Infer `service_type` from Quote line items (soundtrack/beatbreeze)
- Meaningful Opportunity name: `{company.name} - {service_label}`

---

### Feb 10, 2026 - Service Type + Multi-Entity Pipeline Enhancement

- Added `service_type` field to Opportunity model
- Removed "All Entities" from dropdowns
- Service filter on Opportunities and Sales Performance pages
- Migration: `0057_opportunity_service_type.py`

---

### Feb 10, 2026 - Entity Filter + PDF Export for Opportunities & Sales Performance

- New SalesExportService for PDF generation
- Export endpoints: `/opportunities/export/pdf/`, `/opportunities/export/sales-performance-pdf/`

---

### Feb 9, 2026 - Opportunities Section Audit & Improvements

- Filter Bar Consistency (flex layout, Sort dropdown)
- OpportunityDetail page (full rewrite from stub)
- Auto-Create Opportunity from Quote
- Sales Performance page (replaced mock data)

---

### Feb 9, 2026 - Zone Management Improvements (Audit-Driven)

- Zone-Ticket Linking (FK + UI)
- ZoneDetail enhancements (Last API Sync, Support Tickets tab)
- ZonesUnified Sync Health stat
- EnhancedZonePicker overlap warning
- Migration: `0056_ticket_zone_fk.py`

---

### Feb 9, 2026 - Tech Support Improvements (Keith's Feedback)

- KB Settings page for categories/tags management
- Support Tab on CompanyDetail (360-degree view)
- Company dropdown fix (page_size: 1000)

---

### Feb 9, 2026 - Filter Bar Consistency (All List Pages)

- Standardized filter bar: Search + filters + Sort dropdown
- Removed date pickers from Contacts, Contracts, Quotes, Invoices
- Added ordering params to backend ViewSets

---

### Feb 7, 2026 - Company List Sorting

- Added Sort dropdown to Companies page (6 options)
- Added `updated_at` to CompanyViewSet ordering_fields

---

### Feb 7, 2026 - Zone Table PDF Improvements

- Use `str(zone)` to strip property prefix from zone names
- Wrap property name in Paragraph for word-wrap

---

### Feb 7, 2026 - Manual Zone Creation for Contracts

- Manual "Add New Zone" for Soundtrack (text input + button)
- "Import from Soundtrack API" bulk-creates preview zones

---

### Feb 7, 2026 - HK Stamp Aspect Ratio Fix

- Auto-detect aspect ratio for non-square stamps (854x772px)
- Adjust height proportionally

---

### Feb 7, 2026 - Differentiate Soundtrack vs Beat Breeze Zones in Contract PDFs

- Added "Service" column to zones table
- Zones grouped by platform with service name merged vertically

---

### Feb 7, 2026 - Company Address Form Consolidation & PDF Address Fix

- Single "Company Address" section (no duplicate fields)
- `format_address_multiline()` function for PDFs
- Filter "Other" country from PDFs

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

## Migration History (as of Feb 13, 2026)
- `0070_contract_draft_sent_status.py` - Contract Draft/Sent statuses, default changed to Draft
- `0069_quote_followup_flags.py` - Quote first_followup_sent/second_followup_sent tracking fields
- `0068_quote_type.py` - Quote quote_type field (new/renewal/addon)
- `0067_avatar_url_textfield.py` - User avatar_url CharField→TextField
- `0066_user_avatar.py` - User avatar_url field
- `0065_invoice_improvements_pom_feedback.py` - Company tax_id/branch, Invoice property_name, InvoiceLineItem product_service/service_periods
- `0064_company_phone_email_contact_mobile.py` - Company phone/email + Contact mobile/preferred_contact_method
- `0063_contract_line_items.py` - ContractLineItem model + Contract quote FK
- `0062_invoice_service_period.py` - Invoice service period dates
- `0061_invoice_payment_terms_fields.py` - Invoice payment terms persistence
- `0060_invoice_line_items.py` - InvoiceLineItem model
- `0059_invoice_optional_contract.py` - Invoice company FK + optional contract
- `0058_task_improvements.py` - Task FKs, types, TaskComment model
- `0057_opportunity_service_type.py` - Opportunity service_type field
- `0056_ticket_zone_fk.py` - Ticket zone FK
- `0055_contracttemplate_pdf_format.py` - ContractTemplate pdf_format field
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
