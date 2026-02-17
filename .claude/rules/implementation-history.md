# Implementation History - BMAsia CRM

## February 2026

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
