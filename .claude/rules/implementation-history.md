# Implementation History - BMAsia CRM

## February 2026

### Feb 19, 2026 - QuickBooks IIF Export: 4 Fixes from Pom's Testing

**Context**: Pom imported the IIF file into QuickBooks Pro 2016 and found 4 issues: (1) date format wrong (QB Thailand expects DD/MM/YYYY), (2) old invoices without `product_service` show generic "Service" INVITEM even though description contains product keywords, (3) QNTY shows negative in QB after import, (4) service period dates not exported.

**Fix 1 — Date Format DD/MM/YYYY** (`quickbooks_export_service.py:_format_date`):
- Changed `date_obj.strftime('%m/%d/%Y')` → `date_obj.strftime('%d/%m/%Y')`
- QuickBooks uses Windows locale date format — Thailand uses DD/MM/YYYY
- Affects all DATE fields in IIF: invoice date, due date, service period dates

**Fix 2 — Description-Based Product Fallback** (`quickbooks_export_service.py`):
- `_resolve_income_account(product_service, income_accounts, description=None)`: when `product_service` is empty, falls back to checking `description` for product keywords ("soundtrack" → SYB account, "beatbreeze"/"beat" → BMS account)
- `_get_item_name(product_service, description=None)`: same fallback — when `product_service` is empty, checks description for keywords. Returns mapped QB item name (e.g., "Soundtrack Music Service"), NOT the raw description text
- `_write_line_item()`: passes `item.description` to both methods as fallback parameter
- Handles old invoices where product info is in the description field rather than the `product_service` dropdown

**Fix 3 — QNTY Sign for SPL Rows** (`quickbooks_export_service.py:_write_line_item`):
- Changed `self._format_amount(item.quantity)` → `self._format_amount(-item.quantity)`
- SPL rows have negative AMOUNT (credit to income). QB may calculate display qty from AMOUNT/PRICE — if AMOUNT=-28000, QNTY=2, PRICE=14000, QB shows qty=-2
- With QNTY=-2: AMOUNT=-28000, QNTY=-2, PRICE=14000 → QB displays qty=2 on the invoice
- Only affects line item SPL rows (VAT and discount SPL rows already had QNTY=0)

**Fix 4 — Service Period in MEMO** (`quickbooks_export_service.py:_write_line_item`):
- Appends service period dates to the MEMO (description) field when `service_period_start`/`service_period_end` are set
- Format: `(Period: DD/MM/YYYY - DD/MM/YYYY)` after the line item description
- Uses same `_format_date()` (now DD/MM/YYYY) for consistency
- Handles partial periods: `(From: DD/MM/YYYY)` or `(To: DD/MM/YYYY)` when only one date is set

**Files Modified** (1 file):
- `crm_app/services/quickbooks_export_service.py` — All 4 fixes

**No frontend changes. No migrations. No model changes.**

**Commit**: `d908d95b`

---

### Feb 19, 2026 - QuickBooks Export: Per-Product Income Accounts & Per-Currency AR

**Context**: Pom tested the QB export and shared her actual chart of accounts. Two issues: (1) all line items credited the same income account, but Soundtrack (SYB) and Beat Breeze (BMS) need separate revenue accounts; (2) all invoices debited the same AR account, but BMAT needs currency-specific AR (THB local vs USD overseas).

**Backend — Per-Product Income Resolution** (`quickbooks_export_service.py`):
- Replaced `income_account` (string) with `income_accounts` (dict): `{'syb': '...', 'bms': '...', 'default': '...'}`
- New `_resolve_income_account(product_service, income_accounts)` method:
  - Normalizes product_service to lowercase, strips spaces
  - 'soundtrack' → `income_accounts['syb']`
  - 'beatbreeze' or 'beat' → `income_accounts['bms']`
  - Fallback → `income_accounts['default']`
- `_write_line_item()` now calls `_resolve_income_account()` per line item for the ACCNT field

**Backend — Per-Currency AR Resolution** (`quickbooks_export_service.py`):
- Replaced `ar_account` (string) with `ar_accounts` (dict): `{'THB': '...', 'USD': '...'}`
- New `_resolve_ar_account(invoice, ar_accounts)` method:
  - Looks up `invoice.currency` in `ar_accounts` dict
  - Falls back to USD, then 'Accounts Receivable'
- `_write_invoice()` calls `_resolve_ar_account()` for the TRNS ACCNT field

**Backend Endpoint** (`views.py`, lines 4108-4140):
- Replaced 3 params (`ar_account`, `income_account`, `tax_account`) with 6 named params:
  - `ar_account_thb`, `ar_account_usd`
  - `income_account_syb`, `income_account_bms`, `income_account_default`
  - `tax_account` (unchanged)
- Builds `ar_accounts` and `income_accounts` dicts from query params

**Frontend Dialog** (`Invoices.tsx`):
- 6 state variables replace 3: `qbArAccountThb`, `qbArAccountUsd`, `qbIncomeAccountSyb`, `qbIncomeAccountBms`, `qbIncomeAccountDefault`, `qbTaxAccount`
- `QB_ENTITY_DEFAULTS` now contains Pom's actual QB account names:
  - BMAT: `1005 น LOCAL ACCOUNTS RECEIVABLE` (THB), `1005.1 น OVERSEAS ACCOUNTS RECEIVABLE` (USD), `4006.1 น SYB RESELLER`, `4006.2 น BMS MUSIC`, `2030.7 น TAX`
  - BMAL: `1005 น ACCOUNTS RECEIVABLE` (USD only), same SYB/BMS revenue accounts
- Dialog grouped into 3 sections: "Accounts Receivable (by currency)", "Revenue Accounts (by product)", "Tax" (BMAT only)
- AR THB field only shown for Thailand entity

**Frontend API** (`api.ts`):
- Updated `exportQuickBooks` params type with new param names

**Files Modified** (4 files):
- `crm_app/services/quickbooks_export_service.py` — `_resolve_ar_account()`, `_resolve_income_account()`, dict params throughout
- `crm_app/views.py` — 6 named query params → dicts
- `bmasia-crm-frontend/src/services/api.ts` — param type update
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — 6 state vars, entity defaults, grouped dialog fields

**Note**: Pom also listed HKD/GBP/EUR/SGD/CNY AR accounts for BMAL, but the CRM Invoice model only supports USD and THB currencies. Multi-currency expansion is a future task.

**Commit**: `f9f6330a`

---

### Feb 19, 2026 - Client Tech Details: PC Name, Operating System, OS Type

**Context**: Keith requested 3 additional fields he forgot to include in the original Client Tech Details spec: Operating System, OS Type (32/64-bit), PC Name.

**Backend Changes**:
- **Model** (`crm_app/models.py`): Added 3 fields to ClientTechDetail in PC Specifications section:
  - `pc_name` — CharField(100), computer/hostname
  - `operating_system` — CharField(100), e.g. Windows 10, Windows 11
  - `os_type` — CharField(20), 32-bit or 64-bit
- **Migration**: `0074_clienttechdetail_os_pcname.py` (manual — no local Django)
- **Serializer** (`crm_app/serializers.py`): Added `pc_name`, `operating_system`, `os_type` to ClientTechDetailSerializer Meta.fields
- **Admin** (`crm_app/admin.py`): Added to PC Specifications fieldset (before pc_make)
- **PDF** (`crm_app/views.py`): Added 3 rows at top of PC Specifications section in tech detail PDF download

**Frontend Changes**:
- **Types** (`types/index.ts`): Added `pc_name`, `operating_system`, `os_type` to ClientTechDetail interface
- **Form** (`ClientTechDetailForm.tsx`):
  - FormState interface + emptyForm constant
  - loadFormData (edit mode) + handleSave payload
  - JSX: New Row 1 in PC Specs section — PC Name (text), Operating System (text), OS Type (select dropdown: 32-bit/64-bit)
  - Existing PC Make/Model/Type moved to Row 2
- **Detail View** (`ClientTechDetails.tsx`): 3 new DetailRow entries at top of PC Specifications section

**Files Modified** (8 files):
- `crm_app/models.py`, `crm_app/serializers.py`, `crm_app/admin.py`, `crm_app/views.py`
- `crm_app/migrations/0074_clienttechdetail_os_pcname.py` (NEW)
- `bmasia-crm-frontend/src/types/index.ts`
- `bmasia-crm-frontend/src/components/ClientTechDetailForm.tsx`
- `bmasia-crm-frontend/src/pages/ClientTechDetails.tsx`

**Commit**: `cad684b0`

---

### Feb 19, 2026 - QuickBooks Export: VAT 7%, Account Mapping, Entity Separation

**Context**: Khun Pom tested the QuickBooks IIF export and provided follow-up feedback: (1) VAT 7% must be a separate line so QuickBooks can track VAT Payable, (2) account name fields need to be visible (not hidden), (3) BMAL and BMAT must export as separate files for separate QB company files.

**Item 1 — VAT as Separate SPL Row** (`quickbooks_export_service.py`):
- Line item SPL rows now use **pre-tax amounts** (`qty * unit_price`) instead of `line_total` (which includes tax)
- New VAT SPL row: accumulates tax from all line items, writes single SPL crediting `tax_account` with `-total_tax`
- Only generated when `total_tax > 0` (Thailand 7%) — BMAL (0% VAT) unchanged
- Discount SPL row added when `invoice.discount_amount > 0` (positive amount = debit)
- Math: `TRNS (+total) + SPL revenue (-pre_tax each) + SPL VAT (-tax) + SPL discount (+disc) = 0`
- Added `tax_account` parameter to `generate_iif()` and `_write_invoice()` (default: 'VAT Payable')
- Fallback path (no line items) also splits into pre-tax + VAT SPL

**Item 2 — Prominent Account Fields** (`Invoices.tsx`):
- Removed collapsible `<Collapse>` toggle — account fields always visible in gray box
- Added "VAT Payable Account" TextField (shown only when Thailand entity selected)
- `QB_ENTITY_DEFAULTS` constant maps entity → `{ ar, income, tax }` defaults
- `handleQbEntityChange()` auto-fills all 3 account fields when entity changes
- Removed `qbShowSettings` state, added `qbTaxAccount` state
- Removed unused `Collapse` import

**Item 3 — Entity Separation**:
- Removed `<MenuItem value="">All Entities</MenuItem>` from entity dropdown
- Entity selection now **required** — export button disabled without it
- Backend returns 400 if `billing_entity` missing
- Entity-specific filenames: `invoices-BMAT-YYYYMMDD.iif` / `invoices-BMAL-YYYYMMDD.iif`
- Both frontend (`link.download`) and backend (`Content-Disposition`) use same naming

**Backend Endpoint Update** (`views.py`):
- Added `tax_account` query param (default: 'VAT Payable')
- Made `billing_entity` required (400 error if missing)
- Passes `tax_account` to `generate_iif()`
- Entity abbreviation in filename: `'BMAT' if 'Thailand' in billing_entity else 'BMAL'`

**Frontend API** (`api.ts`):
- Added `tax_account?: string` to `exportQuickBooks()` params type

**Files Modified**:
- `crm_app/services/quickbooks_export_service.py` — VAT SPL row, pre-tax amounts, tax_account param, discount SPL
- `crm_app/views.py` — tax_account param, required billing_entity, entity filename
- `bmasia-crm-frontend/src/services/api.ts` — tax_account param type
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — Required entity, visible accounts, VAT field, entity defaults

**No migrations. No model changes. No new dependencies.**

**Commit**: `fbdef09b`

---

### Feb 19, 2026 - Pom's Finance Feedback: Branch Field, Address Save, QuickBooks Export

**Context**: Finance manager (Khun Pom) raised three issues: (1) Branch field is a dropdown — needs free text for values like "Branch 00001", (2) Company address edits won't save, (3) Invoices must export to QuickBooks Pro 2016 to avoid double data entry.

**Item 1 — Branch Field: Dropdown → Free Text** (`CompanyForm.tsx`):
- **Problem**: Branch was a `<Select>` dropdown with 3 hardcoded `<MenuItem>` options: "None", "สำนักงานใหญ่ (Head Office)", "Branch"
- **Backend**: `branch = CharField(max_length=100, blank=True)` — already supports any text. **No backend change needed**
- **Fix**: Replaced `<FormControl>` + `<Select>` + 3 `<MenuItem>` with simple `<TextField>` with `placeholder="e.g., Branch 00001"` and `helperText`
- Also added `tax_id` and `branch` fields to `CompanyEdit.tsx` (full-page edit form was missing them entirely)

**Item 2 — Address Editing Won't Save** (`api.ts`, `CompanyEdit.tsx`):
- **Root Cause**: `updateCompany()` in api.ts line 108 used **PUT** instead of **PATCH** — same bug pattern as the invoice fix (commit `f49b7a63`). PUT requires ALL model fields; the form sets optional fields to `undefined` which Axios strips → DRF rejects with 400
- **Fix 1**: Changed `authApi.put` → `authApi.patch` in `updateCompany()`
- **Fix 2**: Moved `city` field from "Basic Information" section to "Address Information" section in CompanyEdit.tsx (was in wrong section)

**Item 3 — QuickBooks Pro 2016 IIF Export**:

*Research*: QuickBooks Pro 2016 uses **IIF (Intuit Interchange Format)** — tab-delimited text format. Only native import format for invoices in QB Desktop.

*Backend — `QuickBooksExportService`* (`crm_app/services/quickbooks_export_service.py` — NEW):
- `generate_iif(invoices, ar_account, income_account)` → returns StringIO with IIF content
- IIF structure per invoice: `!TRNS` header → `TRNS` row (positive AR debit) → `!SPL` header → `SPL` rows (negative income credits) → `ENDTRNS`
- `_sanitize_text()`: strips semicolons (QB stops reading), replaces newlines/tabs with spaces, replaces non-ASCII with `?`, truncates to 255 chars
- `_get_item_name()`: maps CRM `product_service` to QB item names (e.g., "soundtrack" → "Soundtrack Music Service")
- `PRODUCT_SERVICE_TO_QB_ITEM` dict: soundtrack, beatbreeze, hardware, installation, support
- Dates formatted as MM/DD/YYYY (QB requirement)
- Per-invoice error handling with logging (skips failed invoices, continues export)

*Backend — Export Endpoint* (`crm_app/views.py`):
- `@action(detail=False, methods=['get'], url_path='export-quickbooks')` on `InvoiceViewSet`
- Query params: `billing_entity`, `status` (comma-separated, default: Sent), `date_from`, `date_to`, `ar_account`, `income_account`
- Returns `HttpResponse` with `Content-Disposition: attachment; filename="invoices_export_YYYYMMDD.iif"`, `content_type='text/plain; charset=utf-8'`

*Frontend — API Method* (`api.ts`):
- `exportQuickBooks(params)` → `authApi.get('/invoices/export-quickbooks/', { params, responseType: 'blob' })`

*Frontend — Export Dialog* (`Invoices.tsx`):
- "Export to QuickBooks" button next to "New Invoice" (outlined, orange, `<GetApp />` icon)
- Dialog fields: Billing Entity dropdown, Invoice Status dropdown (Sent/Paid/All, default: Sent), Date From/To pickers
- Collapsible "QuickBooks Account Settings": AR Account Name + Income Account Name TextFields (default: "Accounts Receivable" / "Service Revenue")
- Info Alert: "Customer names in CRM must match QuickBooks exactly"
- Export handler: blob download → saves as `.iif` file. 404 = no matching invoices alert

**Files Modified**:
- `bmasia-crm-frontend/src/components/CompanyForm.tsx` — Branch Select → TextField
- `bmasia-crm-frontend/src/pages/CompanyEdit.tsx` — Added tax_id/branch fields, moved City to address section
- `bmasia-crm-frontend/src/services/api.ts` — `updateCompany()` PUT→PATCH + `exportQuickBooks()` method
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — QB export button + dialog
- `crm_app/services/quickbooks_export_service.py` — **NEW** — IIF generation service
- `crm_app/views.py` — `export_quickbooks` action on InvoiceViewSet

**No migrations. No model changes. No new dependencies.**

**Commit**: `1e49746a`

---

### Feb 19, 2026 - Client Tech Details Module

**Context**: Keith (tech support) needed a centralized place to record detailed technical specifications for each client outlet — PC specs, remote access IDs, audio equipment, network info, etc. Previously tracked in spreadsheets and personal notes.

**New Model: `ClientTechDetail`** (`crm_app/models.py`):
- Single flat model — one record per outlet (25+ fields, always queried together)
- `company` FK(Company, CASCADE, related_name='tech_details') **required**
- `zone` FK(Zone, SET_NULL, null/blank, related_name='tech_details') **optional**
- `outlet_name` CharField(255) **required**
- Remote Access: `anydesk_id`, `teamviewer_id`, `ultraviewer_id`, `other_remote_id`
- System Config: `system_type` (single/multi choices), `soundcard_channel`, `bms_license`, `additional_hardware`
- PC Specs: `pc_make`, `pc_model`, `pc_type`, `ram`, `cpu_type`, `cpu_speed`, `cpu_cores`, `hdd_c`, `hdd_d`, `network_type`
- Audio Equipment: `amplifiers`, `distribution`, `speakers`, `other_equipment` (all TextField)
- Links: `music_spec_link`, `syb_schedules_link` (URLField max_length=500)
- `comments` TextField
- Composite index on `['company', 'outlet_name']`
- Migration: `0073_client_tech_detail.py`

**Backend** (`serializers.py`, `views.py`, `urls.py`, `admin.py`):
- `ClientTechDetailSerializer` with computed `company_name`, `zone_name` (read-only)
- `ClientTechDetailViewSet(ModelViewSet)` with `select_related('company', 'zone')`
- Filters: `company`, `zone`, `system_type`
- Search: `outlet_name`, `company__name`, `anydesk_id`, `teamviewer_id`, `comments`
- Custom action: `@action by_company(company_id)` — unpaginated results for a company
- URL: `router.register(r'client-tech-details', ...)` → `/api/v1/client-tech-details/`
- Admin: fieldsets grouped by 6 sections, `autocomplete_fields = ['company', 'zone']`

**Frontend Types + API** (`types/index.ts`, `api.ts`):
- `ClientTechDetail` interface (35 fields)
- 7 API methods: `getClientTechDetails`, `getClientTechDetail`, `createClientTechDetail`, `updateClientTechDetail` (PATCH), `deleteClientTechDetail`, `getClientTechDetailsByCompany`

**Frontend Form** (`components/ClientTechDetailForm.tsx`):
- Dialog-based form with 6 Paper card sections: Client & Location, Remote Access (2x2 grid), System Config, PC Specs (3-col grid), Audio Equipment (2x2 multiline), Links & Notes
- Company Autocomplete (`page_size: 1000, ordering: 'name'`)
- Zone Select loads dynamically on company change
- Outlet name auto-fills from zone selection
- Create/edit modes with error/success handling

**Frontend List Page** (`pages/ClientTechDetails.tsx`):
- Company Autocomplete filter + text search
- Paginated table: Client | Outlet | AnyDesk | TeamViewer | System Type | PC Make/Model | Actions
- Clickable rows open detail dialog (6 sections matching form layout)
- 3-dot menu: View, Edit, Delete with confirmation dialog

**Navigation**:
- Sidebar (`Layout.tsx`): `ComputerIcon` → `/tech-details` in Tech Support section (after Zones)
- Route (`App.tsx`): `/tech-details` with `requiredModule="tickets"`

**Files Modified**:
- `crm_app/models.py` — ClientTechDetail model
- `crm_app/serializers.py` — ClientTechDetailSerializer
- `crm_app/views.py` — ClientTechDetailViewSet
- `crm_app/urls.py` — Router registration
- `crm_app/admin.py` — ClientTechDetailAdmin
- `crm_app/migrations/0073_client_tech_detail.py` — New migration
- `bmasia-crm-frontend/src/types/index.ts` — ClientTechDetail interface
- `bmasia-crm-frontend/src/services/api.ts` — 7 CRUD methods
- `bmasia-crm-frontend/src/components/ClientTechDetailForm.tsx` — NEW form component
- `bmasia-crm-frontend/src/pages/ClientTechDetails.tsx` — NEW list page
- `bmasia-crm-frontend/src/components/Layout.tsx` — Sidebar nav item
- `bmasia-crm-frontend/src/App.tsx` — Route

**Commits**: `57afcfd2` (backend), `515373e0` (frontend)

---

### Feb 19, 2026 - KB White Screen Fix + Category Count Fix

**Problem 1 — White Screen on Knowledge Base page**: After KB article save fix, articles appeared in the listing but `KBArticleCard` crashed with `TypeError: Cannot read properties of undefined (reading 'slice')`. Three crash sources:
- `article.tags.slice(0, 3)` — `tags` not included in list serializer response
- `article.category.name` — list serializer returned `category_detail`, not `category`
- `article.content.replace(...)` — `content` not in list serializer response

**Fix 1 — Backend** (`crm_app/serializers.py`):
- `KBArticleListSerializer`: renamed `category_detail` → `category` (field name in `Meta.fields`)
- Added `tags` to `Meta.fields` list

**Fix 1 — Frontend** (`KBArticleCard.tsx`, `KBFeaturedArticles.tsx`):
- `article.tags.slice(0, 3)` → `(article.tags || []).slice(0, 3)`
- `article.category.name` → `article.category?.name || 'Uncategorized'`
- `article.content.replace(...)` → `(article.content || '').replace(...)`

**Problem 2 — Category counts all showing (0)**: User saw 4 articles but all categories showed "(0)". Root cause: `KBCategory.article_count` property filtered `status='published'` — all test articles were drafts.

**Fix 2** (`crm_app/models.py`):
- `KBCategory.article_count`: `self.articles.filter(status='published').count()` → `self.articles.count()`
- `KBTag.article_count`: same change

**Files Modified**:
- `crm_app/serializers.py` — KBArticleListSerializer field name fix + tags added
- `crm_app/models.py` — KBCategory/KBTag article_count properties
- `bmasia-crm-frontend/src/components/KBArticleCard.tsx` — Null safety
- `bmasia-crm-frontend/src/components/KBFeaturedArticles.tsx` — Null safety

**Commits**: `de765be7` (white screen fix), `c5044f3d` (category count fix)

---

### Feb 19, 2026 - Tech Support PDF Downloads (KB Articles + Client Tech Details)

**Context**: Sales/marketing side already had PDF download for Quotes, Contracts, and Invoices. Keith's tech support team needed the same capability for Knowledge Base articles and Client Tech Details — lets them share technical documentation and client specs externally without requiring CRM access.

**Client Tech Detail PDF** (`crm_app/views.py` — `ClientTechDetailViewSet.pdf`):
- `@action(detail=True, methods=['get'])` endpoint at `/api/v1/client-tech-details/{id}/pdf/`
- Single-page branded PDF with BMAsia logo + orange accent line
- Title: "CLIENT TECHNICAL DETAILS" — 20pt DejaVuSans-Bold
- Metadata bar: Orange-header table with Company Name | Outlet Name | Zone
- 6 sections via `build_section()` helper (orange section headings, alternating row backgrounds):
  - Remote Access (AnyDesk, TeamViewer, UltraViewer, Other Remote — monospace font)
  - System Configuration (System Type, Soundcard Channel, BMS License, Additional Hardware)
  - PC Specifications (Make, Model, Type, RAM, CPU, Speed, Cores, HDD C:, HDD D:, Network)
  - Audio Equipment (Amplifiers, Distribution, Speakers, Other Equipment)
  - Links (Music Spec, SYB Schedules — blue monospace links)
  - Notes (Comments field)
- Empty fields show "-", label column 160pt, value column flexible
- Footer: "BMAsia — Generated [date]" centered
- Filename: `TechDetail_{company}_{outlet}.pdf` (sanitized)

**KB Article PDF** (`crm_app/views.py` — `KBArticleViewSet.pdf`):
- `@action(detail=True, methods=['get'])` endpoint at `/api/v1/kb/articles/{id}/pdf/`
- Multi-page PDF with page footer callback (article number + page numbers)
- **HTML-to-ReportLab converter**: `HTMLToFlowables(HTMLParser)` class using Python stdlib `html.parser` — no new dependencies
  - Maps ReactQuill HTML tags to ReportLab flowables:
    - `<p>` → Paragraph with body style
    - `<h1>`/`<h2>`/`<h3>` → Paragraph with heading styles (16/14/12pt bold)
    - `<strong>`/`<em>`/`<u>`/`<s>` → ReportLab inline markup (`<b>`, `<i>`, `<u>`, `<strike>`)
    - `<a href>` → `<a href="..." color="blue">` inline markup
    - `<br>` → `<br/>` in current paragraph
    - `<ul>/<ol>` + `<li>` → Indented paragraphs with bullet/number prefix
    - `<blockquote>` → Indented paragraph with gray background
    - `<pre>`/`<code>` → Courier font with gray background
    - `<img src="data:...">` → Base64 decode → ReportLab Image (max 5" wide)
    - `<hr>` → HRFlowable with orange color
    - `<p><br></p>` (Quill empty line) → Spacer
  - Fallback: if parsing fails, strips HTML tags and renders plain text
- PDF layout: logo + orange accent, title, metadata box (article#, category, author, published, status, tags), orange divider, article body, attachments table (if any), article info section
- Filename: `KB_{article_number}.pdf` (sanitized)

**Frontend — Client Tech Details** (`ClientTechDetails.tsx`):
- Added "Download PDF" MenuItem in 3-dot action menu (between "View Details" and "Edit")
- Added "Download PDF" Button in detail dialog DialogActions (before Edit button, orange color)
- `handleDownloadPDF(detail)` handler with blob→createElement('a')→click→cleanup pattern

**Frontend — KB Article** (`KnowledgeBaseArticle.tsx`):
- Added "Download PDF" outlined button next to "Edit Article" in `<Box display="flex" gap={1}>`
- PDF button visible to ALL authenticated users (not gated behind `canEdit`)
- `handleDownloadPDF()` handler with same blob download pattern
- Filename: `{article_number}_{slug}.pdf`

**Frontend API** (`api.ts`):
- `downloadClientTechDetailPDF(id)` — `authApi.get('/client-tech-details/${id}/pdf/', { responseType: 'blob' })`
- `downloadKBArticlePDF(id)` — `authApi.get('/kb/articles/${id}/pdf/', { responseType: 'blob' })`

**Files Modified**:
- `crm_app/views.py` — `pdf` action on `ClientTechDetailViewSet` + `KBArticleViewSet`, `HTMLToFlowables` class
- `bmasia-crm-frontend/src/services/api.ts` — `downloadClientTechDetailPDF()` + `downloadKBArticlePDF()`
- `bmasia-crm-frontend/src/pages/ClientTechDetails.tsx` — PDF button in detail dialog + 3-dot menu
- `bmasia-crm-frontend/src/pages/KnowledgeBaseArticle.tsx` — PDF button next to Edit Article

**No new files. No migrations. No model changes. No new dependencies.**

**Commit**: `cfa03025` — "Add PDF download for Client Tech Details and KB Articles"

---

### Feb 17, 2026 - KB Article Save Fix

**Problem**: Keith reported "I am having trouble saving articles in the Knowledge Base in the CRM, pretty sure I am filling required fields then when I click save it fails." Every save attempt returned 400 Bad Request.

**Root Cause — Field Name Mismatch** (`KBArticleForm.tsx` vs `KBArticleSerializer`):
- Frontend `handleSubmit()` and `handleAutoSave()` sent `category` and `tags`
- Backend `KBArticleSerializer` defines write-only fields with different names:
  ```python
  category_id = serializers.UUIDField(write_only=True, source='category')
  tag_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True)
  ```
- DRF rejected the payload because `category` (the read-only nested serializer field) cannot be written to, and `category_id` (the required write field) was missing

**Fix** (`KBArticleForm.tsx`):
- Changed `category: formData.category` → `category_id: formData.category` in both `handleSubmit()` and `handleAutoSave()`
- Changed `tags: formData.tags` → `tag_ids: formData.tags` in both methods
- Added frontend content validation: checks 100-char minimum after HTML strip (matches backend `validate_content()`)
- Improved error display: DRF field-level validation errors now shown in the Alert instead of generic "Failed to save article"

**Files Modified**:
- `bmasia-crm-frontend/src/components/KBArticleForm.tsx` — Fixed field names, added content validation, better error display

**Commit**: `10aa5578`

---

### Feb 17, 2026 - Email Delivery Confirmation Bug Fixes

**Bug 1 — 500 on Quote Send** (`NameError: name 'EmailLog' is not defined`):
- The enhanced send response code in `QuoteViewSet.send()` references `EmailLog` to return `email_details`
- `EmailLog` was not in the `from .models import (...)` block in views.py
- **Fix**: Added `EmailLog` to model imports at line 46
- **Lesson**: When adding code to views.py that references a model, always verify it's in the imports block

**Bug 2 — 404 on Email-Logs API** (doubled URL `/api/v1/api/v1/email-logs/`):
- `getEmailLogs()` in api.ts used absolute path `/api/v1/email-logs/`
- Axios baseURL is already `https://bmasia-crm.onrender.com/api/v1` — so the request went to `/api/v1/api/v1/email-logs/`
- **Fix**: Changed to relative path `/email-logs/`
- **Lesson**: All api.ts endpoints MUST use relative paths (e.g. `/email-logs/`, not `/api/v1/email-logs/`)

**Files Modified**:
- `crm_app/views.py` — Added `EmailLog` to model imports
- `bmasia-crm-frontend/src/services/api.ts` — Fixed `getEmailLogs()` URL path

**Commit**: `27271fe7`

---

### Feb 17, 2026 - Email Delivery Confirmation System (Phases 1 + 2)

**Problem**: When users send quotes, invoices, or contracts from the CRM, they get a basic "Sent successfully" toast but have no way to verify the email was actually delivered or opened. The `EmailLog` model existed with `opened_at`, `clicked_at`, and `bounced` fields — but they were **never populated**. No API endpoint for EmailLog. Missing `quote` FK. Incomplete `email_type` choices.

**Phase 1 — Visibility: Surface Existing EmailLog Data**

**Model Changes** (`crm_app/models.py` ~line 1697):
- Added `quote` ForeignKey (SET_NULL, nullable) to EmailLog — matches existing `contract`/`invoice` FKs
- Added `tracking_token` CharField(64, unique, nullable) — auto-generated via `secrets.token_urlsafe(32)` in `save()` override
- Expanded `EMAIL_TYPE_CHOICES`: added `invoice_send`, `quote_send`, `quote_followup`, `contract_send`
- Migration: `0072_email_delivery_confirmation.py`

**Email Type Fixes** (`crm_app/services/email_service.py`):
- `send_quote_email()`: `'manual'` → `'quote_send'` + set `quote=quote` on EmailLog
- `send_invoice_email()`: `'manual'` → `'invoice_send'`
- `send_contract_email()`: `'manual'` → `'contract_send'`
- Restructured all 3 methods: create EmailLog BEFORE send (status='pending'), inject pixel, send, mark sent/failed

**API Endpoint** (`crm_app/serializers.py`, `crm_app/views.py`, `crm_app/urls.py`):
- New `EmailLogSerializer` with computed fields (`company_name`, `contact_name`, `email_type_display`, `status_display`)
- New `EmailLogViewSet(ReadOnlyModelViewSet)` — filters: company, contact, contract, invoice, quote, status, email_type
- Registered at `r'email-logs'` → `/api/v1/email-logs/`

**Enhanced Send Responses** (`crm_app/views.py`):
- Quote send endpoint: returns `email_details` array with per-recipient info (to_email, from_email, status, sent_at, email_log_id)
- Invoice send endpoint: same enhancement

**Frontend** (`types/index.ts`, `api.ts`, `QuoteDetail.tsx`, `InvoiceDetail.tsx`, `ContractDetail.tsx`):
- `EmailLogEntry` interface + `getEmailLogs()` API method
- Email History section on all 3 detail pages: timeline of sent emails with status icons (green=sent, blue=opened, red=failed, gray=pending)
- Enhanced send confirmation messages with recipient details

**Phase 2 — Open Tracking via Tracking Pixel**

**Tracking Pixel Endpoint** (`crm_app/views.py`, `bmasia_crm/urls.py`):
- `email_tracking_pixel(request, token)` — unauthenticated, returns 1x1 transparent GIF (43 bytes)
- On hit: sets `opened_at=now()`, `status='opened'` if not already opened
- URL: `/t/<str:token>/` (short, outside `/api/`)
- `Cache-Control: no-store, no-cache` to prevent false positives from CDN caching

**Pixel Injection** (`crm_app/services/email_service.py`):
- `_inject_tracking_pixel(body_html, tracking_token)` — inserts `<img>` before `</body>` or appends
- Called in `send_email()` + all document-specific send methods
- Pixel URL: `{SITE_URL}/t/{tracking_token}/`

**Expected Reliability**:
| Client | Works? | Notes |
|--------|--------|-------|
| Gmail (web) | Yes | Proxies images; first open reliable |
| Outlook | Yes | Loads images on open |
| Apple Mail | Unreliable | Privacy Protection pre-fetches |
| Images blocked | No | Some corporate clients block |

~60-80% open detection for BMAsia's B2B audience (industry standard).

**Files Modified**:
- `crm_app/models.py` — EmailLog: quote FK, tracking_token, email_type choices, save() override
- `crm_app/services/email_service.py` — _inject_tracking_pixel(), restructured send methods, email_type fixes
- `crm_app/serializers.py` — EmailLogSerializer
- `crm_app/views.py` — EmailLogViewSet, email_tracking_pixel(), enhanced send responses
- `crm_app/urls.py` — email-logs route
- `bmasia_crm/urls.py` — /t/<token>/ tracking route
- `crm_app/migrations/0072_email_delivery_confirmation.py` — New migration
- `bmasia-crm-frontend/src/types/index.ts` — EmailLogEntry interface
- `bmasia-crm-frontend/src/services/api.ts` — getEmailLogs() method
- `bmasia-crm-frontend/src/components/QuoteDetail.tsx` — Email History + enhanced send confirmation
- `bmasia-crm-frontend/src/components/InvoiceDetail.tsx` — Email History + enhanced send confirmation
- `bmasia-crm-frontend/src/components/ContractDetail.tsx` — Email History section

**Commit**: `1e8b6ff1`

---

### Feb 17, 2026 - Quote PDF Preview Button

**Problem**: ContractDetail and InvoiceDetail both had "Preview" buttons that open the PDF in a new browser tab, but QuoteDetail only had "PDF" (download) and "Print" — no preview.

**Fix**: Added Preview button to QuoteDetail using the same pattern as ContractDetail/InvoiceDetail:
- `handlePreviewPDF()`: calls `ApiService.downloadQuotePDF()` → `createObjectURL(blob)` → `window.open(url, '_blank')`
- Button placed before existing "PDF" download button with `Visibility` icon
- No backend changes — `downloadQuotePDF()` and `GET /quotes/{id}/pdf/` already existed

**Button order**: Send Quote | Convert to Contract | Create Invoice | **Preview** | PDF | Print

**Files Modified**:
- `bmasia-crm-frontend/src/components/QuoteDetail.tsx` — Added Visibility import, handlePreviewPDF handler, Preview button

**Commit**: `79c74f00`

---

### Feb 17, 2026 - Link Service Locations to Line Items (Auto-Sync)

**Problem**: Service locations and line items in ContractForm were completely independent — no validation, no sync. A user could have a "Soundtrack" line item with qty=5 and a single "Beat Breeze" service location without any error. Each service location should represent 1 unit of a music line item's quantity, and the platform must match.

**Solution — Auto-sync via `syncLocationsFromLineItems()`** (`ContractForm.tsx`):

Core sync function that calculates required location counts per platform from line items (using `PRODUCT_OPTIONS.platform` mapping), then adjusts existing locations:
- If current count < required → add blank rows
- If current count > required → remove excess (unnamed/blank first, then named from end)
- Returns `droppedNamedCount` for UI warning

**`useEffect` on `lineItems`**:
- Fires `syncLocationsFromLineItems()` whenever line items change
- Guarded by `isFormInitialized` ref — prevents sync on initial form load (edit mode) or `resetForm()`
- `isFormInitialized.current = true` set via `setTimeout` at end of `populateForm()` and `resetForm()`

**Removed manual controls**:
- `addServiceLocation()` function — removed (no "Add Location" button)
- `removeServiceLocation()` function — removed (no delete buttons per row)
- Platform `<Select>` dropdown → read-only `<Typography>` (platform derived from line item)
- Manual location generation in `handleQuoteChange()` → replaced by comment (useEffect handles it)

**Updated Service Locations UI**:
- Helper text: "Auto-generated from music line items above. Adjust line item quantities to add or remove locations."
- Empty state: "Add a music service line item (Soundtrack Your Brand or Beat Breeze) to generate service locations."
- Table columns: `#` (row number) | Location Name (editable TextField) | Platform (read-only text)
- Warning `<Alert>` with `locationsTrimmedWarning` state — shown when named locations dropped by qty decrease

**Submit validation**:
- Checks all service locations have `location_name` filled in
- Shows error: "Please fill in all N service location name(s)"

**Edge Cases Handled**:
| Scenario | Behavior |
|----------|----------|
| Edit mode load | `isFormInitialized` guard prevents sync — existing locations load normally |
| Qty increase (3→5) | 2 blank rows added for that platform |
| Qty decrease (5→3), named locations | Blank rows removed first; named preserved; warning if named dropped |
| Product change (Soundtrack → Beat Breeze) | Old platform locations removed, new platform rows created |
| Product change (Soundtrack → Hardware) | Soundtrack locations removed, no new ones |
| Multiple same-platform line items | Quantities summed (3+2 = 5 locations) |
| Quote auto-fill | `handleQuoteChange` sets lineItems → useEffect derives locations |

**Files Modified**:
- `bmasia-crm-frontend/src/components/ContractForm.tsx` — All changes (sync function, useEffect, UI, validation)

**Commit**: `544114e9` — "Link service locations to line items: auto-sync + validation"

---

### Feb 16-17, 2026 - Contract Service Locations + PDF Preview

**Problem 1 — Complex Zone Picker**: ContractForm used EnhancedZonePicker showing Soundtrack account IDs, device statuses, API sync info — all tech-support concerns. Sales just needs to enter a zone name (e.g., "Lobby") and pick a platform type (Soundtrack or Beat Breeze).

**Problem 2 — No PDF Preview**: ContractDetail lacked a PDF preview button (had to download every time), unlike InvoiceDetail.

**Solution — New ContractServiceLocation Model** (`crm_app/models.py`):
- Simple model: `contract` FK, `location_name` (CharField), `platform` (soundtrack/beatbreeze), `sort_order` (int)
- No device info, no API sync, no status — just what the contract PDF needs
- `related_name='service_locations'` on Contract FK
- Ordering: `['sort_order', 'platform', 'location_name']`
- Migration: `0071_contract_service_location.py`

**Backend — Serializer** (`crm_app/serializers.py`):
- New `ContractServiceLocationSerializer` (id, location_name, platform, sort_order)
- Added `service_locations` as nested writable field on `ContractSerializer`
- `create()`/`update()`: delete-recreate pattern (same as `line_items`)
- `get_active_zone_count()`/`get_total_zone_count()`: prefers service_locations count, falls back to contract_zones

**Backend — PDF Dual-Source Fallback** (`crm_app/views.py`):
- `_build_zones_table()`: checks `contract.service_locations.all()` first
- If service_locations exist → delegates to new `_build_service_locations_table()`
- If no service_locations → falls back to `contract.get_active_zones()` (legacy)
- Returns `None` if no data at all — all 5 call sites null-check the result
- `_substitute_template_variables()`: also dual-source for `{{venue_names}}` and `{{number_of_zones}}`

**Frontend — ContractForm Refactor** (`ContractForm.tsx`):
- **Removed**: EnhancedZonePicker import/usage, `selectedZones` state, `loadContractZones()`, `soundtrackAccountId`/`previewZones`/`previewLoading`/`previewError` states, Soundtrack Account Configuration section, Music Zones section, `updateContractZones()` in handleSubmit
- **Added**: `ServiceLocationEntry` interface, `serviceLocations` state, add/remove/update handlers
- **UI**: Simple table — Location Name (TextField) + Platform (Select) + Delete button + "Add Location" button
- **handleQuoteChange()**: auto-creates service location rows from quote line items (maps product_service to platform, uses quantity for row count, skips hardware)
- **handleSubmit()**: includes `service_locations` in payload (filtered non-blank, mapped with sort_order)
- **Edit mode**: reads `contract.service_locations` first, falls back to `contract.contract_zones` for legacy

**Frontend — ContractDetail Updates** (`ContractDetail.tsx`):
- Replaced zone card grid with simple "Service Locations" table (Location + Platform chip)
- Fallback to contractZones display for legacy contracts
- Added "Preview PDF" button (Visibility icon) — blob→createObjectURL→window.open
- Added "Download PDF" button (PictureAsPdf icon) — blob→download link

**TypeScript Types** (`types/index.ts`):
- New `ServiceLocation` interface (id, location_name, platform, sort_order, timestamps)
- Added `service_locations?: ServiceLocation[]` to Contract interface

**Backward Compatibility**:
- Old contracts with ContractZone data: PDF falls back to legacy zone path automatically
- No data migration — gradual migration when contracts are edited
- EnhancedZonePicker.tsx file stays (not deleted) — just no longer imported
- Zone/ContractZone system unchanged for CompanyDetail → Zones tab

**Files Modified**:
- `crm_app/models.py` — ContractServiceLocation model
- `crm_app/serializers.py` — ContractServiceLocationSerializer + ContractSerializer updates
- `crm_app/views.py` — `_build_service_locations_table()` + dual-source fallback
- `crm_app/migrations/0071_contract_service_location.py` — New migration
- `bmasia-crm-frontend/src/components/ContractForm.tsx` — Replaced zone picker with service locations
- `bmasia-crm-frontend/src/components/ContractDetail.tsx` — Service locations display + PDF preview/download
- `bmasia-crm-frontend/src/types/index.ts` — ServiceLocation interface

**Commit**: `2c30de1f` — "Simplify contract service locations + add PDF preview"

---

### Feb 16, 2026 - Task Digest Cron Fix

**Problem**: Task digest cron (`crn-d65drn75r7bs73cpu72g`) failing to deploy with `ModuleNotFoundError: No module named 'crm_project'` and Python 3.13 in build path.

**Root Cause**: Two incorrect environment variables:
- `DJANGO_SETTINGS_MODULE` was `crm_project.settings` (should be `bmasia_crm.settings`)
- No `PYTHON_VERSION` env var — defaulted to Python 3.13 instead of pinned 3.12.8

**Fix**: Updated environment variables via Render MCP:
- `DJANGO_SETTINGS_MODULE=bmasia_crm.settings`
- `PYTHON_VERSION=3.12.8`

**Lesson**: Render crons have their own environment variables separate from the web service. When creating new crons, always verify `DJANGO_SETTINGS_MODULE` and `PYTHON_VERSION` match the web service settings.

---

### Feb 13, 2026 - Contract Draft/Sent Status Workflow

**Problem**: All new contracts were created with status `Active`, which made no sense — a freshly created contract hasn't been sent or signed yet. Users had to mentally track contract lifecycle outside the CRM.

**New Status Lifecycle**: `Draft` → `Sent` → `Active` → `Renewed` / `Expired` / `Cancelled`

**Backend — New Statuses** (`crm_app/models.py`):
- Added `'Draft'` and `'Sent'` to `CONTRACT_STATUS_CHOICES`
- Changed default from `'Active'` to `'Draft'`
- Full choices: Draft, Sent, Active, Renewed, Expired, Cancelled
- Migration: `0070_contract_draft_sent_status.py`

**Frontend — Status Buttons** (`ContractDetail.tsx`):
- "Mark as Sent" button: visible when `status='Draft'`, sets `status='Sent'` via `updateContract()`
- "Mark as Signed" button: visible when `status='Sent'`, sets `status='Active'` via `updateContract()`
- Buttons in header action area next to Edit/Delete/PDF buttons

**Frontend — Type & Filter Updates**:
- `Contract.status` type union updated: `'Draft' | 'Sent' | 'Active' | 'Renewed' | 'Expired' | 'Cancelled'`
- Contracts list page (`Contracts.tsx`): Added Draft (gray chip) and Sent (orange chip) to status filter dropdown
- Status color map: Draft=gray, Sent=orange, Active=green, Renewed=blue, Expired=red, Cancelled=gray

**Files Modified**:
- `crm_app/models.py` — CONTRACT_STATUS_CHOICES + default change
- `crm_app/migrations/0070_contract_draft_sent_status.py` — New migration
- `bmasia-crm-frontend/src/types/index.ts` — Contract.status type union
- `bmasia-crm-frontend/src/pages/Contracts.tsx` — Status filter options + chip colors
- `bmasia-crm-frontend/src/components/ContractDetail.tsx` — Mark as Sent/Signed buttons

---

### Feb 13, 2026 - Convert to Contract Fix (Quote→Contract Flow)

**Problem**: QuoteDetail had a "Convert to Contract" button that called `POST /quotes/{id}/convert_to_contract/` — endpoint never existed (404 error). Users couldn't easily create a contract from an accepted quote.

**Solution**: Changed to use the same pre-fill pattern as Create Invoice flow:
- **QuoteDetail.tsx**: Changed button to navigate `to={`/contracts?new=true&company=${quote.company_id}&quote=${quote.id}`}` instead of calling non-existent API
- **Contracts.tsx**: Added `useSearchParams()` logic to detect `?new=true&company=X&quote=Y` and auto-open ContractForm with pre-fill
- **ContractForm.tsx**: Added `initialCompanyId` and `initialQuoteId` props for pre-fill
  - `initialCompanyId`: pre-selects company in dropdown (no re-fetch)
  - `initialQuoteId`: auto-triggers `handleQuoteChange()` which imports line items + currency + payment terms from source quote
- **Existing `handleQuoteChange()` logic**: Does all the heavy lifting (discount folded into unit_price, line items copied, currency inherited from quote)

**Removed**: Non-existent `ApiService.convertQuoteToContract()` method + related unused imports in QuoteDetail.tsx

**Pattern**: Quote→Contract now matches Invoice flow (navigation + query params + form pre-fill) instead of backend conversion endpoints. All three conversions use same pattern:
- Quote→Invoice: `/invoices?new=true&company=X&contract=Y`
- Quote→Opportunity: `/opportunities?new=true&company=X&quote=Y`
- Quote→Contract: `/contracts?new=true&company=X&quote=Y`

**Files Modified**:
- `bmasia-crm-frontend/src/components/QuoteDetail.tsx` — Navigate instead of API call
- `bmasia-crm-frontend/src/pages/Contracts.tsx` — Read query params + auto-open form
- `bmasia-crm-frontend/src/components/ContractForm.tsx` — Added `initialCompanyId` and `initialQuoteId` props

---

### Feb 13, 2026 - Quote Follow-Up Emails, Status Buttons, Form Fixes & Contract Presets

**OpportunityForm $ Icon Removed** (`OpportunityForm.tsx`):
- Expected Value field had a hardcoded `<MoneyIcon />` (AttachMoney) as `startAdornment`
- Currency is already handled dynamically by `formatCurrency()` — icon was redundant and wrong for THB
- Removed: `InputAdornment` wrapper, `MoneyIcon` icon, cleaned up unused imports
- Same pattern as the Feb 12 fix for list pages — never put currency icons next to `formatCurrency()` output

**BMAsia Signatory Preset on ContractForm** (`ContractForm.tsx`):
- Pre-filled `bmasia_signatory_name: 'Chris Andrews'` and `bmasia_signatory_title: 'Director'` as defaults
- Applies to: new contracts (initial state), legacy contracts with empty signatory fields (edit mode)
- Both fields remain fully editable — just saves manual typing on every contract
- Logic: `useState` default is `'Chris Andrews'`/`'Director'`; edit mode only overrides if `contract.bmasia_signatory_name` is truthy

**Quote Type Field for Opportunity Control** (`models.py`, `serializers.py`, `views.py`, `QuoteForm.tsx`):
- New `quote_type` CharField on Quote model with choices: `'new'` (New Business), `'renewal'` (Renewal), `'addon'` (Add-on)
- Default: `'new'` (backward compatible — existing quotes treated as new business)
- **Renewal quotes skip opportunity auto-creation**: `QuoteViewSet.perform_create()` checks `quote_type != 'renewal'` before auto-creating/linking Opportunity
- **Frontend UX**:
  - Quote Type dropdown at top of QuoteForm (before Company)
  - Renewal: Opportunity dropdown hidden entirely (renewals don't need new opportunities)
  - New Business / Add-on: Opportunity dropdown shown with helper text "Leave empty to auto-create new"
- Migration: `0068_quote_type.py`

**Thai Text Removed from Invoice PDF** (`views.py`):
- Changed `"สำนักงานใหญ่ (Head Office)"` to just `"Head Office"` in invoice FROM section
- Thai characters rendered as black squares despite DejaVu Sans font — the specific Thai glyphs in this string weren't rendering correctly
- Invoice PDF only — contract PDFs use templates where Thai text is handled differently

**Quote Notes Label Clarified** (`QuoteForm.tsx`):
- Changed label from `"Notes"` to `"Notes (shown on PDF)"`
- Added `helperText: "These notes will appear on the generated PDF quote"`
- The notes field already rendered on the quote PDF — users just didn't know it would appear there

**Quick Status Buttons on Detail Views**:
- **ContractDetail** (`ContractDetail.tsx`):
  - "Mark as Sent" button: visible when status='Draft', sets status='Sent' via `updateContract()`
  - "Mark as Signed" button: visible when status='Sent', sets status='Active' via `updateContract()`
  - Buttons appear in the header action area next to existing Edit/Delete/PDF buttons
  - Uses existing `ApiService.updateContract()` — no new backend endpoint needed
- **InvoiceDetail** (`InvoiceDetail.tsx`):
  - "Mark as Paid" button: visible when status='Sent' or status='Overdue'
  - Uses existing `ApiService.markInvoicePaid()` endpoint (already existed, just wasn't exposed in detail view)
  - Refreshes invoice data after status change
- **QuoteDetail**: Already had Accept/Reject/Send buttons — no changes needed
- Pattern: status transitions that happen frequently should be one-click, not buried in edit forms

**Automated Quote Follow-Up Emails** (`email_service.py`, `models.py`, `views.py`):
- New `send_quote_followups()` method in EmailService
- **Schedule**: 1st follow-up at 3 days after `sent_date`, 2nd follow-up at 7 days
- **Target**: Only quotes with `status='Sent'` — automatically stops when quote is Accepted/Rejected/Expired
- **Tracking flags on Quote model**: `first_followup_sent` (BooleanField, default=False), `second_followup_sent` (BooleanField, default=False)
- **Email content**: Professional HTML email reminding client about pending quote, includes quote number, company name, total amount
- **Integration**: Added to daily email cron via `send_emails --type all` command — runs alongside renewal reminders, overdue notices, and seasonal emails
- **Idempotent**: Checks tracking flags before sending — safe to re-run
- Migration: `0069_quote_followup_flags.py`

**Files Modified**:
- `crm_app/models.py` — Quote `quote_type`, `first_followup_sent`, `second_followup_sent` fields
- `crm_app/serializers.py` — Added new Quote fields to serializer
- `crm_app/views.py` — Renewal quote skip logic in `QuoteViewSet.perform_create()`, Thai text fix in invoice PDF
- `crm_app/services/email_service.py` — `send_quote_followups()` method
- `crm_app/migrations/0068_quote_type.py` — Quote type field
- `crm_app/migrations/0069_quote_followup_flags.py` — Follow-up tracking flags
- `bmasia-crm-frontend/src/components/OpportunityForm.tsx` — Removed $ icon
- `bmasia-crm-frontend/src/components/ContractForm.tsx` — BMAsia signatory defaults
- `bmasia-crm-frontend/src/components/QuoteForm.tsx` — Quote type dropdown, notes label
- `bmasia-crm-frontend/src/components/ContractDetail.tsx` — Mark as Sent/Signed buttons
- `bmasia-crm-frontend/src/components/InvoiceDetail.tsx` — Mark as Paid button

---

### Feb 13, 2026 - Invoice Status Update Fix: PUT → PATCH

**Problem**: "Mark as Sent" button on invoice detail pages returned 400 error. Root cause: `updateInvoice()` in `api.ts` used `PUT` which requires ALL required fields from the model, but the button only sent `{ status: 'Sent' }`.

**Fix**: Changed HTTP method from `PUT` to `PATCH` in `updateInvoice()` method (line 378 of `bmasia-crm-frontend/src/services/api.ts`):
```typescript
// Before: authApi.put(`/api/v1/invoices/${id}/`, data)
// After: authApi.patch(`/api/v1/invoices/${id}/`, data)
```

**Lesson**: Django REST Framework requires:
- `PUT` — all required fields must be present (full resource replacement)
- `PATCH` — only provided fields are updated (partial update)

For status changes (common operation), always use `PATCH`. Applied same principle to any future partial updates.

**Commit**: `f49b7a63`

**Files Modified**:
- `bmasia-crm-frontend/src/services/api.ts` — `updateInvoice()` method

---

### Feb 13, 2026 - Dashboard & Header Cleanup (5 fixes)

**Avatar Upload Fix** (`api.ts`, `views.py`, `models.py`):
- Bug 1: Axios `Content-Type: 'multipart/form-data'` omitted boundary → Django couldn't parse. Fix: `Content-Type: undefined`
- Bug 2: `avatar_url` CharField(500) too small for base64 (~10-30KB). Fix: changed to TextField
- Bug 3: Silent failure — only `console.error()`. Fix: added `alert()` for user feedback
- Migration: `0067_avatar_url_textfield.py`

**Dashboard Task Visibility** (`views.py:my_tasks`, `Dashboard.tsx`):
- `my_tasks` endpoint was `assigned_to=request.user` — Admin users with no assigned tasks saw "No active tasks"
- Fix: Admin/Manager see all active tasks, Sales users see only their assigned tasks
- Status filter (`To Do`, `In Progress`) moved server-side — removed redundant client-side filter

**Fake Notification Bell Removed** (`Layout.tsx`):
- Bell icon had hardcoded `badgeContent={3}` and 3 static MenuItems ("New opportunity created — 2 minutes ago", etc.)
- No API, no real data, no click handlers — pure placeholder
- Removed: icon button, Badge, Menu with 3 items, state/handlers, NotificationsIcon import (~80 lines)
- Dashboard greeting + Today page already surface real urgent items

**Music Quotes: Random Rotation** (`constants/quotes.ts`):
- Was `dayOfYear % quotes.length` — same quote all day for everyone
- Changed to `Math.random() * quotes.length` — new quote on each page load

**Dashboard Greeting Bar Clickable** (`Dashboard.tsx`):
- Entire greeting Paper now has `onClick={() => navigate('/tasks')}` + `cursor: pointer` + hover opacity
- "View Tasks" link kept for discoverability

**Remember Me Default** (`Login.tsx`):
- `remember_me` was `false` by default → tokens stored in `sessionStorage` (cleared on every refresh)
- Changed to `true` → tokens stored in `localStorage` (persists across refreshes and browser restarts)
- Auth storage keys: `bmasia_access_token`, `bmasia_refresh_token`, `bmasia_user`, `bmasia_remember_me`
- Users can still uncheck "Remember me" on shared/public computers

---

### Feb 13, 2026 - Visual Refresh: Dark Sidebar, KPI Polish, Greeting, User Avatars

**Dark Sidebar** (`Layout.tsx`):
- Background: `#1e293b` (dark slate) with slate-100 logo header area
- BMAsia logo centered in slate-100 header (`public/bmasia-logo.png` — white background, no CSS filter)
- Logo header: `height: 120`, `py: 2`, `backgroundColor: '#f1f5f9'` (slate-100), `justifyContent: 'center'`, logo `height: 42`
- Collapse chevron: positioned absolutely `right: 8, top: 8` with `color: '#94a3b8'` (doesn't push logo off-center)
- No "BMAsia CRM" text — logo already contains the brand name
- Active nav items: `#FF8C00` orange text + `rgba(255,140,0,0.15)` background + orange left border
- Nav text `#cbd5e1`, section headings `#94a3b8`, dividers `rgba(255,255,255,0.08)`
- Department badge: orange-tinted chip instead of department color

**Music Quotes in Header Bar** (`Layout.tsx`, `constants/quotes.ts`):
- Fills the empty AppBar space left by global search removal
- 40 music-focused quotes (Tolstoy, Bob Marley, Beethoven, Stevie Wonder, Lady Gaga, etc.)
- Daily rotation: `getDailyQuote()` uses `dayOfYear % quotes.length` — same for everyone all day
- No icons/emoji — just clean italic text + author attribution
- Style: italic `text.secondary` quote + `text.disabled` author, `noWrap` with overflow hidden
- Hidden on mobile (`display: { xs: 'none', md: 'flex' }`)
- No backend/API needed — hardcoded in frontend constants file
- **Reverted from news ticker**: Tried MBW RSS feed proxy (feedparser + Django endpoint) but reverted — added backend complexity and caused login timeout during deploy. Cosmetic header features should NEVER depend on backend/network requests

**Theme Polish** (`ThemeContext.tsx`):
- Background: `#f8fafc` (warmer than `#f5f5f5`)
- Card shadows: softer layered shadows (`0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)`)
- Card borders: `rgba(0,0,0,0.06)` instead of `#e0e0e0`
- Card hover: `translateY(-1px)` lift + shadow increase with 0.2s transition

**KPI Card Upgrade** (`Dashboard.tsx`):
- Icons now sit on colored circular backgrounds: `alpha(iconColor, 0.1)` with `borderRadius: '12px'`, 44x44px

**Personalized Greeting** (`Dashboard.tsx`):
- Time-based: "Good morning/afternoon/evening, [first_name]!" using browser local time
- Task summary: fetches `getMyTasks()`, filters active (To Do/In Progress), shows overdue count in red
- "View Tasks" link navigates to `/tasks`
- Warm gradient Paper card (`#fff7ed` → `#ffffff`)

**User Avatar System**:
- Backend: `avatar_url` **TextField** on User model — stores base64 data URL in DB (originally CharField(500), too small for base64)
- Endpoint: `POST /api/v1/users/upload-avatar/` — accepts multipart file, resizes to 150x150 via Pillow, saves as JPEG base64
- Uses `PILImage` alias to avoid conflict with ReportLab's `Image`
- Frontend: `avatar_url` on User type, `uploadAvatar()` in ApiService
- MUI Avatar `src={user?.avatar_url}` with initials fallback
- "Change Avatar" menu item in user dropdown (hidden file input)
- Migrations: `0066_user_avatar.py` (added field), `0067_avatar_url_textfield.py` (CharField→TextField)

**Avatar Upload Bug Fix** (Feb 13):
- **Bug 1 — Missing multipart boundary**: `uploadAvatar()` in api.ts set `Content-Type: 'multipart/form-data'` explicitly, which prevented Axios from adding the boundary parameter. Django's `MultiPartParser` couldn't parse the body → `request.FILES` empty → 400. Fix: set `Content-Type: undefined` to let Axios auto-detect from FormData
- **Bug 2 — Field too small**: `avatar_url` was `CharField(max_length=500)` but a 150x150 JPEG base64 string is ~10-30KB. Fix: changed to `TextField` (migration `0067`)
- **Bug 3 — Silent failure**: catch block only did `console.error()`. Fix: added `alert()` for user feedback
- **Lesson**: Never set `Content-Type: 'multipart/form-data'` on Axios — always use `undefined` for FormData uploads

**Logo gotchas**:
- `bmasia-logo.png` is now a **transparent-background RGBA PNG** (1187x531, from `BMAsia_LOGO_clean.png`) — blends seamlessly into slate-100 header
- Previous version had WHITE opaque background causing a white rectangle on non-white surfaces

---

### Feb 13, 2026 - Invoice Status-Conditional Action Buttons & ContractForm Status Dropdown Fix

**Problem 1 — Invoice Actions Ignoring Status**: Invoice list page 3-dot menu showed "Send" and "Mark as Paid" for ALL invoices regardless of status. Same on InvoiceDetail. Semantically wrong — can't send an already-paid invoice, can't mark a draft as paid.

**Problem 2 — ContractForm Status Dropdown Missing Values**: ContractForm.tsx `contractStatuses` array was hardcoded to `['Active', 'Renewed', 'Expired', 'Cancelled']` — missing `'Draft'` and `'Sent'`. Edit dialogs showed an incomplete status dropdown after the new Draft→Sent→Active lifecycle was added. Commit e2000e09.

**Fix 1 — Status-Conditional Action Buttons** (`Invoices.tsx`, `InvoiceDetail.tsx`):
- "Send via Email" button: visible ONLY for `status='Draft'` — sends email + updates status to Sent
- "Mark as Sent" button: visible ONLY for `status='Draft'` — just updates status (for manually sent invoices)
- "Mark as Paid" button: visible for `status='Sent'` OR `status='Overdue'` — updates status to Paid
- No action buttons for Paid, Cancelled, or Refunded invoices
- Both locations (list page 3-dot menu and detail view) have identical conditional logic
- Added `handleMarkAsSent()` function to both files — calls `ApiService.updateInvoice(id, { status: 'Sent' })`

**Fix 2 — Add Missing Draft & Sent to contractStatuses Array** (`ContractForm.tsx`):
- Changed: `const contractStatuses = ['Active', 'Renewed', 'Expired', 'Cancelled']`
- To: `const contractStatuses = ['Draft', 'Sent', 'Active', 'Renewed', 'Expired', 'Cancelled']`
- Now shows all 6 statuses when editing contracts

**Files Modified**:
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — Status-conditional "Send via Email"/"Mark as Sent"/"Mark as Paid" in 3-dot menu
- `bmasia-crm-frontend/src/components/InvoiceDetail.tsx` — Same status-conditional buttons in DialogActions
- `bmasia-crm-frontend/src/components/ContractForm.tsx` — Added Draft/Sent to contractStatuses array

**Commits**: `73e95a14` (Invoices), `ece13f9e` (InvoiceDetail + ContractForm)

---

### Feb 13, 2026 - Audit Response: $NaN Fix + Global Search Removal

**$NaN in OpportunityPipeline.tsx**:
- `weighted_value` from backend can be null — caused `$NaN` display in pipeline stage headers and opportunity detail dialog
- Fix: Added `|| 0` fallback at line 390 (stage reduce) and line 134 (detail dialog display)

**Global Search Bar Removed from Layout.tsx**:
- Search bar in top nav was a placeholder — captured user input via `setSearchQuery()` but never called any API
- Removed: search bar JSX, `searchQuery` state, 3 styled components (`Search`, `SearchIconWrapper`, `StyledInputBase`), unused imports (`InputBase`, `SearchIcon`, `styled`)
- Each list page retains its own working search field — no functionality lost

---

### Feb 12, 2026 - Email System Fix: Cron Crashes, Python Pinning & Seasonal Dates

**Problem**: All 3 email/cron jobs had been crashing since ~Feb 5, 2026. No automated emails (renewal reminders, payment follow-ups, quarterly check-ins, seasonal greetings) were being sent. Two separate root causes discovered.

**Root Cause 1 — pkg_resources ImportError**:
- `djangorestframework-simplejwt 5.3.0` imports `pkg_resources` (deprecated)
- Render's default Python 3.13 ships with `setuptools 82+` which removed `pkg_resources`
- Fix: upgraded simplejwt `5.3.0 → 5.3.1` (which uses `importlib.metadata` instead)

**Root Cause 2 — psycopg2 ABI Crash**:
- After fixing simplejwt, crons crashed with `undefined symbol: _PyLong_IsNonNegativeCompact`
- `psycopg2-binary 2.9.9` compiled for Python 3.12 CPython ABI — incompatible with 3.13
- Render crons defaulted to Python 3.13 while the web service used 3.12
- Fix: pinned Python 3.12.8 via `.python-version` file + `runtime.txt`

**Email Sequences Cron Created**:
- New cron: `crn-d66mhcbnv86c73d6e4kg` (every 20 minutes)
- Command: `python manage.py process_email_sequences`
- Previously missing — sequence steps were never being processed

**Email Automation Cron Schedule Fixed**:
- Was: `0 17 * * *` (5 PM Bangkok = outside business hours)
- Now: `0 3 * * *` (3 AM UTC = 10 AM Bangkok = business hours)

**2026 Seasonal Trigger Dates Set**:
- Created `crm_app/management/commands/set_seasonal_dates.py` (idempotent, `update_or_create`)
- Added to `build.sh` for auto-run on every deploy
- 6 variable holidays set: CNY (Feb 3→17), Ramadan (Feb 4→18), Eid al-Fitr (Mar 6→20), Mid-Autumn (Sep 11→25), Diwali (Oct 25→Nov 8), Loy Krathong (Nov 10→24)
- Note: CNY and Ramadan 2026 triggers already passed (system was broken)

**SOUNDTRACK_API_TOKEN Warning Removed**:
- Email crons logged noisy `SOUNDTRACK_API_TOKEN not configured` warning
- Removed from `settings.py` — email crons don't use Soundtrack API

**Verification**:
- Sequences cron: sent 1 email on first run (clearing backlog)
- Soundtrack sync: synced 58 zones, discovered 2 new zones
- All 3 crons confirmed working with multiple successful executions

**Files Modified**:
- `.python-version` (NEW) — `3.12.8`
- `runtime.txt` — `python-3.12.8`
- `requirements.txt` — simplejwt `>=5.3.1`
- `crm_app/management/commands/set_seasonal_dates.py` (NEW)
- `build.sh` — added `set_seasonal_dates` call
- `bmasia_crm/settings.py` — removed SOUNDTRACK_API_TOKEN warning

**Commits**:
- `7a3a3688` — "Pin Python 3.12.8 for Render cron compatibility"
- `153d7c0c` — "Add 2026 seasonal trigger dates + remove noisy SOUNDTRACK warning"

---

### Feb 12, 2026 - Invoice Improvements from Pom's Feedback (5 Phases, 12 Items)

**Context**: Finance team member (Khun Pom) provided 12 feedback items for the Invoice section. Implemented in 5 phases across frontend and backend.

**Phase 1 — Currency, Search & Preview**:
- **Fixed hardcoded USD currency**: Invoice form currency now derives from company's billing entity (THB for Thailand, USD for international) — same pattern as QuoteForm
- **Company Autocomplete search**: Changed company dropdown from basic Select to MUI Autocomplete with `page_size: 1000` and `ordering: 'name'`
- **PDF preview in new tab**: Already existed via View Details → Preview button (no changes needed)

**Phase 2 — Thai Tax Compliance** (`CompanyForm.tsx`, `views.py`):
- **Company `tax_id` and `branch` fields**: New model fields for Thai ใบกำกับภาษี (tax invoice) compliance
- **Thai invoice PDF FROM section**: Added "สำนักงานใหญ่ (Head Office)" label for BMAsia Thailand entity
- **Compact entity address**: Uses `entity_address` directly (no more comma-split pattern)
- **Tax ID display**: Shows on both FROM and BILL TO sections of invoice PDF
- **BILL TO section**: Shows company branch, property_name, tax_id, and formatted address

**Phase 3 — Invoice Line Items Enhancement** (`InvoiceForm.tsx`, `views.py`):
- **Product/Service dropdown per line item**: PRODUCT_OPTIONS constant (5 products matching QuoteForm + Custom)
- **Per-line service period date pickers**: `service_period_start` and `service_period_end` on each InvoiceLineItem
- **Invoice PDF Product/Service column**: Only shows when any line item has product_service data (backward compatible)
- **PDF per-line service periods**: Shows below description when dates are set

**Phase 4 — Entity-Based Invoice Numbering** (`views.py`, `InvoiceForm.tsx`, `api.ts`):
- **Backend `next_number` endpoint**: `GET /api/v1/invoices/next-number/?entity=...` returns sequential number
- **Format**: `INV-TH-YYYY-NNNN` (Thailand) / `INV-HK-YYYY-NNNN` (International)
- **Sequential**: Queries existing invoices with matching prefix, increments last sequence number
- **Frontend**: `generateInvoiceNumber()` calls backend API, with client-side fallback on error
- **Auto-regenerate**: Number regenerated when company changes (in create mode only)

**Phase 5 — Create Invoice Buttons + Property Name** (`ContractDetail.tsx`, `QuoteDetail.tsx`, `Invoices.tsx`, `InvoiceForm.tsx`):
- **ContractDetail "Create Invoice" button**: Navigates to `/invoices?new=true&company=X&contract=Y` (replaced console.log placeholder)
- **QuoteDetail "Create Invoice" button**: Shows for Accepted quotes, navigates similarly
- **Invoices page query param handling**: `useSearchParams` reads `?new=true&company=X&contract=Y`, auto-opens InvoiceForm with pre-fill
- **InvoiceForm `initialCompanyId`/`initialContractId` props**: Pre-fill company and contract from URL params
- **Property Name field**: Auto-fills from contract zones (`Array.from(new Set(zones.map(...)))`)

**Build Fixes**:
1. **TS2802**: `[...new Set()]` fails in CRA build → `Array.from(new Set()) as string[]`
2. **TS2367**: `'product_code'` not in `keyof InvoiceLineItem` → union type `keyof InvoiceLineItem | 'product_code'`

**Files Modified**:
- `crm_app/views.py` — Invoice PDF FROM/BILL TO sections, Product/Service column, per-line service periods, `next_number` endpoint
- `crm_app/models.py` — Company tax_id/branch, Invoice property_name, InvoiceLineItem product_service/service_period fields
- `crm_app/serializers.py` — New fields on Company, Invoice, InvoiceLineItem serializers
- `crm_app/migrations/0065_invoice_improvements_pom_feedback.py` — All model changes
- `bmasia-crm-frontend/src/components/InvoiceForm.tsx` — PRODUCT_OPTIONS, per-line dates, property name, entity numbering, initial props
- `bmasia-crm-frontend/src/components/CompanyForm.tsx` — Tax ID + Branch fields
- `bmasia-crm-frontend/src/components/ContractDetail.tsx` — Create Invoice button
- `bmasia-crm-frontend/src/components/QuoteDetail.tsx` — Create Invoice button
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — Query param handling for auto-open
- `bmasia-crm-frontend/src/services/api.ts` — `getNextInvoiceNumber()` method
- `bmasia-crm-frontend/src/types/index.ts` — Updated Company, Invoice, InvoiceLineItem interfaces

---

### Feb 12, 2026 - Clickable Table Rows on All List Pages

**Problem**: Users had to click the 3-dot action menu → "View Details" to see item details. No way to click directly on a table row. Opportunities already had this pattern.

**Fix**: Added `onClick` + `cursor: pointer` to `<TableRow>` on 5 pages, reusing existing `handleView` functions. Added `e.stopPropagation()` to all action buttons/menus to prevent double-triggering.

| Page | Detail View Type | Handler |
|------|-----------------|---------|
| Companies | Navigation → `/companies/{id}` | `handleViewCompany(company.id)` |
| Contacts | Dialog (ContactDetail) | `handleViewContact(contact)` |
| Quotes | Dialog (QuoteDetail) | `handleViewQuote(quote)` |
| Contracts | Dialog (ContractDetail) | `handleViewContract(contract)` |
| Invoices | Dialog (InvoiceDetail) | `handleViewInvoice(invoice)` |

**Files Modified**: `Companies.tsx`, `Contacts.tsx`, `Quotes.tsx`, `Contracts.tsx`, `Invoices.tsx`

---

### Feb 12, 2026 - Unicode Font Fix for All PDFs + Address Deduplication

**Problem 1 — Non-Latin characters render as black boxes**: Vietnamese diacritics (ễ, ỉ, Đ), Thai text (สำนักงานใหญ่), and other Unicode characters rendered as ■ in all PDFs. ReportLab's Helvetica font only supports ASCII/Latin-1 (U+0000–U+00FF).

**Problem 2 — Address duplication in BILL TO**: When `address_line1` contained a full address (e.g. "No. 8A Nguyễn Bỉnh Khiêm, Đa Kao, District 1, Ho Chi Minh City 70000, Vietnam"), `format_address_multiline()` appended city, state, postal_code, country again from individual fields.

**Fix 1 — DejaVu Sans fonts** (all 4 PDF-generating files):
- Registered `DejaVuSans` and `DejaVuSans-Bold` (TrueType, ships with ReportLab — no extra dependencies)
- Replaced ALL `Helvetica` → `DejaVuSans` and `Helvetica-Bold` → `DejaVuSans-Bold` (~90 instances across 4 files)
- Restored Thai "สำนักงานใหญ่ (Head Office)" text on invoice FROM section (now renders correctly)

**Fix 2 — Address deduplication** (`format_address_multiline()` in `views.py`):
- Before adding city/state/postal/country, checks if value already appears in address_line1/address_line2
- Uses case-insensitive substring matching to skip duplicates

**Files Modified**:
- `crm_app/views.py` — font registration + all Helvetica→DejaVuSans + address dedup + Thai text restored
- `crm_app/services/finance_export_service.py` — font registration + Helvetica→DejaVuSans
- `crm_app/services/sales_export_service.py` — font registration + Helvetica→DejaVuSans
- `crm_app/services/email_service.py` — Helvetica-Bold→DejaVuSans-Bold

---

### Feb 12, 2026 - Double Currency Symbol Fix on List Pages

**Problem**: Value/Amount columns on Invoices, Contracts, and Opportunities list pages showed `$ ฿55,000` for THB and `$ $1,740` for USD — double currency symbols.

**Root Cause**: `<AttachMoney />` MUI icon rendered a hardcoded `$` before `formatCurrency()` output, which already includes the correct currency symbol (`฿` for THB, `$` for USD).

**Fix**: Removed `<AttachMoney />` icon and wrapping `<Box>` from the value/amount table cells on all three pages. Cleaned up unused `AttachMoney` imports.

**Files Modified**:
- `Invoices.tsx` — removed icon from Amount column + cleaned up unused import
- `Contracts.tsx` — removed icon from Value column + cleaned up unused import
- `Opportunities.tsx` — removed icon from Value column + cleaned up unused import

**Lesson**: `formatCurrency()` already includes the symbol — never add currency icons next to it on list pages.

---

### Feb 12, 2026 - Audit & Bug Fixes (6 Bugs from 32+ Audit Findings)

**Context**: Ran comprehensive professional audit of Customer Management & Sales Operations using 3 parallel agents covering Companies, Contacts, Opportunities, Quotes, Contracts, and Invoices. Audit identified 32+ issues. Fixed 6 high-priority bugs.

**Bug 1 — N+1 Query Fixes** (`crm_app/views.py`):
- **ContactViewSet**: Added `select_related('company')` to `get_queryset()` — was hitting DB for every contact's company
- **OpportunityViewSet**: Added `select_related('company', 'owner').prefetch_related('activities')` — was making separate queries for company, owner, and activities on every opportunity
- **ContractViewSet**: Added full optimization:
  ```python
  .select_related('company', 'opportunity', 'quote', 'master_contract', 'renewed_from',
                  'preamble_template', 'payment_template', 'activation_template')
  .prefetch_related('line_items', 'contract_zones', 'invoices', 'service_items', 'contract_documents')
  ```
- **InvoiceViewSet**: Added `select_related('company', 'contract')` (already had `prefetch_related('line_items')`)

**Bug 2 — Restored Deleted Logo** (`crm_app/static/crm_app/images/bmasia_logo.png`):
- **Problem**: Logo was deleted from static files (unstaged), causing ALL PDFs (contracts, quotes, invoices) to fall back to text "BM ASIA"
- **Fix**: Restored from git history commit `ee4073a4` (93KB PNG)
- **Impact**: Logo now renders properly in all PDF headers

**Bug 3 — Company Phone/Email Fields Missing** (`crm_app/models.py`, `crm_app/serializers.py`):
- **Problem**: CompanyForm collected `phone` and `email` but Company model didn't have these fields — data was silently dropped by DRF
- **Fix**: Added to Company model:
  ```python
  phone = models.CharField(max_length=50, blank=True)
  email = models.EmailField(blank=True)
  ```
- **Fix**: Added to CompanySerializer `Meta.fields`
- **Migration**: `0064_company_phone_email_contact_mobile.py`

**Bug 4 — Contact Mobile/Preferred Contact Method Missing** (`crm_app/models.py`, `crm_app/serializers.py`, `ContactForm.tsx`):
- **Problem**: ContactForm had `mobile` and `preferred_contact_method` fields with comments "Not in backend yet" — form showed them but didn't persist
- **Fix**: Added to Contact model:
  ```python
  mobile = models.CharField(max_length=50, blank=True)
  preferred_contact_method = models.CharField(max_length=20, choices=CONTACT_METHOD_CHOICES, blank=True)
  ```
- **Fix**: Added to ContactSerializer `Meta.fields`
- **Fix**: Updated ContactForm to populate from `contact.mobile` and `contact.preferred_contact_method` in edit mode
- **Fix**: ContactForm submit now sends `mobile` and `preferred_contact_method` in payload
- **Migration**: `0064_company_phone_email_contact_mobile.py` (same migration as Bug 3)

**Bug 5 — Invalid Invoice 'Pending' Status** (`types/index.ts`, `Invoices.tsx`, `InvoiceDetail.tsx`):
- **Problem**: Frontend `InvoiceStatus` type included `'Pending'` which doesn't exist in backend Invoice model choices
- **Backend valid statuses**: Draft, Sent, Paid, Overdue, Cancelled, Refunded (no Pending)
- **Fix**: Removed `'Pending'` from InvoiceStatus type, Invoices.tsx filter list, InvoiceDetail.tsx status color map
- **Fix**: Cleaned up unused `Pending` icon import

**Bug 6 — Beat Breeze Service Type Matching** (`crm_app/views.py`, QuoteViewSet.perform_create):
- **Problem**: Quote→Opportunity auto-creation searched for `'beat breeze'` (with space) in product_service, but some line items might have `'beatbreeze'` (no space) — failed to infer service_type
- **Fix**: Added fallback matching:
  ```python
  has_beatbreeze = any('beat breeze' in (i.product_service or '').lower() for i in items)
  # Fallback: also check without space
  if not has_beatbreeze:
      has_beatbreeze = any('beatbreeze' in (i.product_service or '').replace(' ', '').lower() for i in items)
  ```

**Files Modified**:
- `crm_app/views.py` — N+1 fixes on 4 ViewSets + Beat Breeze matching fix
- `crm_app/models.py` — Company phone/email + Contact mobile/preferred_contact_method
- `crm_app/serializers.py` — Added new fields to Company and Contact serializers
- `crm_app/migrations/0064_company_phone_email_contact_mobile.py` — New migration
- `crm_app/static/crm_app/images/bmasia_logo.png` — Restored from git
- `bmasia-crm-frontend/src/types/index.ts` — Removed Invoice 'Pending', updated Contact type
- `bmasia-crm-frontend/src/components/ContactForm.tsx` — Now persists mobile/preferred_contact_method
- `bmasia-crm-frontend/src/pages/Invoices.tsx` — Removed Pending filter option
- `bmasia-crm-frontend/src/components/InvoiceDetail.tsx` — Removed Pending from color map

**Known Audit Items (Not Fixed — Lower Priority)**:
- Contact `contact_type` dropdown — form only exposes "Decision Maker" via checkbox, not full type list
- Contact name split logic — fails for multi-part international names (e.g., "María José García López")
- Company `location_count`/`music_zone_count` — not exposed in CompanyForm
- Company `current_plan` field — unused, could be removed
- No circular reference validation on Company `parent_company`
- Quote status transitions — no validation preventing invalid transitions (e.g., Accepted→Draft)
- Invoice number generated client-side (clock skew/collision risk)
- InvoiceLineItem missing `product_service` field (only has `description`)
- Contract end_date > start_date not validated on backend
- File size limits not enforced on document uploads

---


---

> **Note**: For implementation history before Feb 12, 2026, see `docs/IMPLEMENTATION_ARCHIVE.md`
