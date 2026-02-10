# Implementation History - BMAsia CRM

## February 2026

### Feb 10, 2026 - Dashboard Redesign: Business Health Snapshot

**Research**: Audited Dashboard against HubSpot, Pipedrive, Close.io, monday.com, Explo, Breakcold. Found 3 major problems: (1) Kitchen-sink layout — 7 stat cards + 4 widget sections duplicating sidebar list pages, (2) SalesDashboard 100% mocked data (`generateMockKPIs()`, `generateMockActivities()`, fake 800ms setTimeout), ContractWidgets faked renewal rate, QuickActions hardcoded fake Recent Activity, (3) Raw numbers without trend context — no "is this good or bad?"

**Research conclusion**: Dashboard ≠ landing page. Dashboard = "Are we winning?" (strategic health check). Action Center = "What's on fire?" (tactical). They coexist. 5-7 KPIs max with trend context for small teams.

**Backend Enhancement** (`crm_app/views.py`, DashboardViewSet.stats + `crm_app/serializers.py`):
- Added `win_rate`: won/(won+lost)*100
- Added `previous_month_revenue` + `previous_win_rate` for trend indicators
- Added `total_overdue_amount` (sum of overdue invoice amounts)
- Added `pending_renewal_value` (sum of contracts expiring in 60 days)
- Added `pipeline_stages`: dict with count + value per stage (Contacted, Quotation Sent, Contract Sent, Won, Lost)
- Added `revenue_trend`: last 6 months as `[{month, revenue}]`
- Updated `DashboardStatsSerializer` with all new fields

**Frontend Rewrite** (`bmasia-crm-frontend/src/pages/Dashboard.tsx`, ~423 lines):
- KPICard component: icon, large value, subtitle, trend indicator (↑/↓ % vs last month), color-coded left border
- 6 KPI cards: Revenue This Month, Active Pipeline, Win Rate, Pending Renewals, Overdue Invoices, Tasks Overdue
- Color logic: green (healthy), orange (warning), red (critical) — thresholds per card
- Urgency cards (Renewals, Invoices, Tasks) include "View in Today →" link
- Pipeline funnel: Recharts `BarChart` layout="vertical" with per-stage colors + custom tooltip
- Revenue trend: Recharts `LineChart` with currency-formatted Y-axis
- Updated `DashboardStats` TypeScript interface + added `PipelineStage`, `RevenueTrendPoint`

**Default Landing Page** (`App.tsx` line 110):
- Changed `<Navigate to="/dashboard" replace />` → `<Navigate to="/today" replace />`

**Cleanup — 14 deleted components** (net: 432 added, 7,015 deleted):
- `QuickActions.tsx` — shortcut buttons + hardcoded fake activity
- `SalesDashboard.tsx` — 100% mocked data
- `SalesKPICard.tsx`, `SalesActivityFeed.tsx` — only used by SalesDashboard
- `charts/SalesPipelineFunnel.tsx`, `charts/RevenueTrendChart.tsx` — only used by SalesDashboard
- `QuoteWidgets.tsx`, `ContractWidgets.tsx`, `InvoiceWidgets.tsx`, `TaskWidgets.tsx`, `TargetWidgets.tsx` — duplicated list pages
- `QuickTaskCreate.tsx` — only used by QuickActions
- `MarketingDashboard.tsx`, `TechSupportDashboard.tsx` — dead code (imported deleted SalesKPICard, caused build failure)

**Build Fix**: First deploy failed because MarketingDashboard.tsx and TechSupportDashboard.tsx imported deleted SalesKPICard. TypeScript compiles ALL .tsx files, not just those in the app dependency tree. Fixed by deleting both orphaned files.

**Lesson**: When deleting components, grep ALL .tsx files for imports — not just those reachable from App.tsx.

---

### Feb 10, 2026 - "Today" Action Center

**Problem**: QuickActions page was a placeholder with shortcut buttons (redundant with sidebar) and hardcoded fake "Recent Activity" data. No daily task view existed.

**Backend** (`crm_app/views.py`, `ActionCenterViewSet`):
- Endpoint: `GET /api/v1/action-center/` — returns `{ items: [...], summary: {...} }`
- Queries existing models (no new models/migrations): Tasks, Invoices, Opportunities, Contracts
- 3 urgency tiers: Overdue (past due), Today & Tomorrow, Coming Up (next 7 days)
- Item types: overdue_task, overdue_invoice, stale_opportunity (14+ days no activity), task_due, invoice_due, contract_expiring (60 days), opportunity_followup
- Contact context on every item (primary contact fallback: task.related_contact → company.primary_contact → first active contact)
- Role filtering: Sales users see only their assigned tasks + owned opportunities
- Summary chips: `overdue_count`, `today_count`, `upcoming_count`, `total_value`

**Frontend** (`bmasia-crm-frontend/src/pages/ActionCenter.tsx`, ~393 lines):
- Summary chips at top: Overdue (red), Today (orange), Coming Up (blue)
- 3 collapsible urgency sections with item cards
- Each item: type icon, title, subtitle (contact + company), due date, amount, click-to-navigate
- Navigation: items link to their source page (/tasks, /invoices/:id, /opportunities/:id, /contracts/:id)
- Empty state when no items

**Sidebar & Routing** (`Layout.tsx`, `App.tsx`):
- Renamed "Quick Actions" (BoltIcon) → "Today" (TodayIcon)
- Route: `/today` (with redirect from old `/quick-actions`)
- Default landing: `/` → `/today`

---

### Feb 10, 2026 - Tasks Audit & Improvements (5 Phases)

**Research**: Audited Tasks section against HubSpot, Pipedrive, Zoho, Freshsales best practices. Found critical gaps: backend-frontend field mismatch (frontend had fields that didn't exist in Django model), status mismatch (backend: Pending/Completed, frontend: To Do/Done), over-engineered UI (4 Kanban columns, WIP limits, Time Tracking, Subtasks), zero notifications.

**Phase 1 - Backend Model Fix** (`crm_app/models.py`, `0058_task_improvements.py`):
- Added FKs: `related_opportunity`, `related_contract`, `related_contact`
- Added `task_type` (Call, Email, Follow-up, Meeting, Other)
- Created `TaskComment` model
- Fixed status choices: To Do, In Progress, Done, Cancelled, On Hold
- Removed unused: `estimated_hours`, `actual_hours`, `department`, `tags`
- Data migration: Pending→To Do, Completed→Done, Review→Done

**Phase 2 - Email Notifications** (`crm_app/views.py`, TaskViewSet):
- `perform_create()` and `perform_update()` detect `assigned_to` changes
- `_send_assignment_email()` sends HTML email via `django.core.mail.send_mail`
- Uses system email (NOT per-user SMTP EmailService)

**Phase 3 - Daily Digest Cron** (`crm_app/management/commands/send_task_digest.py`):
- Render cron: `crn-d65drn75r7bs73cpu72g` at 02:00 UTC (9 AM Bangkok)
- Email shows: tasks due today, overdue tasks, newly assigned tasks

**Phase 4 - Frontend Simplification**:
- Kanban: 3 columns (To Do, In Progress, Done) — removed Review + WIP limits
- TaskForm: promoted task_type/opportunity/contact to main section, removed Advanced Options
- TaskDetail: removed Subtasks + Time Tracking tabs, wired Comments to API
- Reduced task_type to 5 options (removed Delivery, Support, Research, Development)

**Phase 5 - Opportunity Auto-Task**:
- `OpportunityViewSet.perform_create()` creates "Follow up with {company}" task (3 day due, Follow-up type)
- `QuoteViewSet.perform_create()` also creates task when auto-creating Opportunity
- OpportunityDetail: new "Tasks" tab showing linked tasks with Create Task button

**Build Fix**: Two build failures fixed:
1. `TaskDetail.tsx`: Used `{ api }` named import instead of `ApiService` default import
2. `TaskListView.tsx`: `LinearProgress` import was removed but component still used

---

### Feb 10, 2026 - Opportunities PDF Design Fixes

**Problem**: Thai Baht symbol (฿) rendered as black square (■) in Opportunities PDF — Helvetica font doesn't support U+0E3F. Also, internal `_entity_raw` key was displayed in the PDF header metadata.

**Fix 1** (`crm_app/services/sales_export_service.py`, ENTITY_INFO line 34):
- Changed THB symbol from `'฿'` to `'THB '` — standard for Thai business documents
- Affects both Opportunities PDF and Sales Performance PDF (shared `_format_currency()`)

**Fix 2** (`crm_app/services/sales_export_service.py`, `_add_pdf_header` line 141):
- Skip keys starting with `_` when rendering subtitle metadata: `if v and not k.startswith('_')`
- Convention: prefix internal/private keys with `_` to hide from PDF output

---

### Feb 10, 2026 - Prospect Workflow: Auto-Infer service_type from Quotes

**Problem**: When `QuoteViewSet.perform_create()` auto-creates an Opportunity from a Quote, it did NOT set `service_type`. This left auto-created Opportunities with `NULL` service_type, making them invisible to Soundtrack/Beat Breeze filters. Also, auto-generated names were generic ("Quote Q-0032").

**CRM Best Practice Research**: Industry standard is Opportunity-first (Opportunity → Quote). BMAsia's Quote-first shortcut is pragmatic for a small team — both paths now coexist.

**Fix** (`crm_app/views.py`, QuoteViewSet.perform_create ~line 4241):
1. **Infer `service_type` from Quote line items**: Inspects `product_service` field — if contains "soundtrack" → `service_type = 'soundtrack'`, if "beat breeze" → `'beatbreeze'`, if both/neither → `NULL`
2. **Meaningful Opportunity name**: `f"{company.name} - {service_label}"` where service_label is "Soundtrack", "Beat Breeze", or "New Deal"
3. **Backfill existing**: When linking a Quote to an existing Opportunity that has `service_type = NULL`, backfills the inferred service_type

**Code**:
```python
# Infer service_type from quote line items
items = instance.line_items.all()
has_soundtrack = any('soundtrack' in (i.product_service or '').lower() for i in items)
has_beatbreeze = any('beat breeze' in (i.product_service or '').lower() for i in items)
if has_soundtrack and not has_beatbreeze:
    service_type = 'soundtrack'
elif has_beatbreeze and not has_soundtrack:
    service_type = 'beatbreeze'
```

**No migration needed** — `service_type` field already existed from `0057_opportunity_service_type.py`.

---

### Feb 10, 2026 - Service Type + Multi-Entity Pipeline Enhancement

**Context**: BMAsia manages sales across a 2x2 matrix: 2 entities (Thailand THB / HK USD) x 2 services (Soundtrack / Beat Breeze). Previously tracked on 4 separate Google Sheets. CRM best practice research (Salesforce, HubSpot, Zoho, Pipedrive) confirmed: never mix currencies in pipeline totals; use a "Product/Service Line" field + filter dropdowns.

**Backend — New `service_type` Field** (`crm_app/models.py`):
- Added `SERVICE_TYPE_CHOICES`: `('soundtrack', 'Soundtrack')`, `('beatbreeze', 'Beat Breeze')`
- `service_type = CharField(max_length=20, choices=..., blank=True, null=True)` — nullable for existing records
- Index: `Index(fields=['service_type', 'stage'])`
- Migration: `0057_opportunity_service_type.py`
- Added to `OpportunitySerializer.Meta.fields`, `OpportunityViewSet.filterset_fields`, `OpportunityAdmin` (list_display, list_filter, fieldsets)

**Remove "All Entities"** (Opportunities.tsx, SalesTargets.tsx):
- Removed `'all'` option from entity dropdowns — mixing THB and USD is meaningless
- Default entity: `'BMAsia Limited'` (from shared `DEFAULT_ENTITY` constant)
- Entity param always sent to API (no conditional check)

**Shared Constants** (`bmasia-crm-frontend/src/constants/entities.ts` — NEW):
- `EntityFilter` type (no 'all'), `ServiceFilter` type ('all' | 'soundtrack' | 'beatbreeze')
- `ENTITY_OPTIONS`, `SERVICE_OPTIONS`, `DEFAULT_ENTITY`, `ENTITY_CURRENCY`
- Shared `formatCurrency(value, entity?)` and `getServiceLabel(serviceType)` functions
- Eliminates 5+ duplicated formatCurrency functions across the codebase

**Service Filter** (Opportunities.tsx, SalesTargets.tsx):
- New dropdown: All Services / Soundtrack / Beat Breeze
- Passes `service_type` param to API when not 'all'
- Filter bar order: Search | Stage | Owner | Entity | **Service** | Sort

**Move Filters Above Both Tabs** (Opportunities.tsx):
- Previously filters only rendered inside Table view — Pipeline tab had NO filters
- Moved `renderFilters()` call above `TabPanel` components — shared by List and Pipeline

**Fix Hardcoded USD Currency** (OpportunityPipeline.tsx):
- Removed ALL THREE local `formatCurrency` functions (hardcoded to USD)
- Pipeline cards: use `opportunity.company_billing_entity` for per-card currency
- Pipeline summary/stage totals: use `entityFilter` prop for aggregate currency
- Added `entityFilter?: string` to `OpportunityPipelineProps`

**Service Type on Pipeline Cards** (OpportunityPipeline.tsx):
- Small outlined chip showing "Soundtrack" / "Beat Breeze" below company name

**OpportunityForm** (OpportunityForm.tsx):
- New "Service" dropdown (Soundtrack / Beat Breeze) — required for new opportunities
- Currency formatting now derives from selected company's billing_entity

**OpportunityDetail** (OpportunityDetail.tsx):
- Fixed hardcoded USD formatCurrency (had existing TODO comment) — now uses shared import
- Service type chip in header next to Stage chip
- Service field in Overview tab Basic Information

**Sales Performance** (SalesTargets.tsx):
- Removed "All Entities" + mixed-currency warning Alert
- Added Service dropdown
- All formatCurrency calls use shared import with entityFilter

**PDF Export Updates** (views.py, sales_export_service.py):
- Both export endpoints accept `service_type` filter param
- `generate_sales_performance_pdf()` accepts optional `service_type` kwarg, shows in subtitle
- `generate_opportunities_pdf()` shows service filter in header

**Files Modified** (14 files, 392 insertions, 170 deletions):
- Backend: models.py, serializers.py, views.py, admin.py, sales_export_service.py, migration
- Frontend: Opportunities.tsx, OpportunityPipeline.tsx, OpportunityForm.tsx, OpportunityDetail.tsx, SalesTargets.tsx, types/index.ts, constants/entities.ts (NEW)

---

### Feb 10, 2026 - Entity Filter + PDF Export for Opportunities & Sales Performance

**Context**: BMAsia operates two billing entities — BMAsia (Thailand) Co., Ltd. (THB) and BMAsia Limited (USD). Opportunities list showed all opportunities with no entity filtering, and all values were hardcoded to USD. Owners wanted downloadable reports. CRM best practice research (Salesforce, HubSpot, Zoho) confirmed PDF is the right format for executive summaries.

**Entity Filter on Opportunities List** (`Opportunities.tsx`):
- Added `EntityFilter` type + `ENTITY_CURRENCY` map (same pattern as SalesTargets)
- Entity dropdown in filter bar (between Owner and Sort)
- Passes `company__billing_entity` param to API when entity selected
- Dynamic `formatCurrency(value, entity?)` — THB shows ฿, USD shows $, per-row currency

**Entity Filter on Sales Performance** (`SalesTargets.tsx`):
- Added Entity dropdown (All / BMAsia Ltd USD / BMAsia Thailand THB)
- Dynamic currency formatting based on entity filter
- Mixed currency warning when "All Entities" selected

**Backend: Serializer + ViewSet** (`serializers.py`, `views.py`):
- Added `company_billing_entity` field to OpportunitySerializer (`source='company.billing_entity'`)
- Added `company__billing_entity` to OpportunityViewSet `filterset_fields`
- Added `company_billing_entity` to Opportunity TypeScript interface

**New SalesExportService** (`crm_app/services/sales_export_service.py` — NEW, 447 lines):
- Separate from `FinanceExportService` (different domain, different entity name format)
- Uses full entity names (`'BMAsia Limited'`, `'BMAsia (Thailand) Co., Ltd.'`) matching Company model
- BMAsia branding: orange #FFA500 accents, logo, header/footer
- `generate_opportunities_pdf()` — landscape, summary box + filtered table with per-row currency
- `generate_sales_performance_pdf()` — KPI grid, period breakdown table, top 5 deals

**Export Endpoints** (`crm_app/views.py` — OpportunityViewSet):
- `GET /api/v1/opportunities/export/pdf/` — Opportunities list PDF (respects all filters)
- `GET /api/v1/opportunities/export/sales-performance-pdf/` — Sales Performance summary PDF
- Lightweight data extraction: `.select_related('company', 'owner')` + manual dict (avoids full serializer)

**Frontend PDF Buttons** (`Opportunities.tsx`, `SalesTargets.tsx`):
- "Export PDF" button on Opportunities list (next to "New Opportunity")
- "PDF" button on Sales Performance page (in filter controls)
- Pattern: `fetch()` with auth token → blob → link element download (same as ProfitLoss.tsx)

**Key Design Decisions**:
1. New `SalesExportService` vs extending `FinanceExportService`: New service — different entity name format (full names vs short codes)
2. PDF only, no Excel: PDF right for owner summaries (Excel can be added later)
3. Mixed currency "All Entities" mode: shows each row's own currency, summary notes "values not converted"

---

### Feb 9, 2026 - Opportunities Section Audit & Improvements

**Context**: Full professional audit of the Opportunities section, benchmarked against Salesforce, HubSpot, and Zoho CRM. Overall grade: B-. Six phases implemented.

**Phase 1: Filter Bar Consistency** (`Opportunities.tsx`):
- Removed DatePicker, LocalizationProvider, AdapterDateFns imports
- Removed startDate/endDate state variables
- Replaced Grid layout with flex layout (consistent with other 6 list pages)
- Added Sort dropdown with Sort icon startAdornment (7 options: Newest, Oldest, Highest/Lowest Value, Highest Probability, Close Date, Last Contacted)
- Added `ordering` param to API calls

**Phase 2: Fix Broken List View Actions** (`Opportunities.tsx`):
- Wired up "View Details" action menu item (was no-op `onClick={() => {}}`)
- Added clickable table rows with `stopPropagation` on action button
- Added `useNavigate` and `handleViewOpportunity` handler

**Phase 3: OpportunityDetail Page** (`OpportunityDetail.tsx` — full rewrite from 17-line stub):
- Header: Back button, opportunity name, stage chip (color-coded), clickable company link, owner, Edit/Delete
- KPI Cards: Expected Value, Weighted Value, Probability (%), Days in Stage
- Stage Stepper: Horizontal MUI Stepper (Contacted → Quotation Sent → Contract Sent → Won/Lost)
- 4 Tabs: Overview (two-column), Activities (ActivityTimeline + Log Activity), Quotes (linked via FK), Contracts (linked via FK)
- "Create Quote" button → `/quotes?new=true&opportunity=${id}&company=${opportunity.company}`
- Backend: Added `'opportunity'` to ContractViewSet `filterset_fields` (QuoteViewSet already had it)

**Phase 4: Auto-Create Opportunity from Quote** (`crm_app/views.py`):
- QuoteViewSet.perform_create() override:
  - If quote has no opportunity: check for existing active opp in 'Contacted' or 'Quotation Sent' stage
  - If found: link quote, advance stage to 'Quotation Sent' if still 'Contacted'
  - If not found: create new Opportunity (name="Quote {number}", stage="Quotation Sent", probability=25)
- Quotes.tsx: reads `?new=true&opportunity=&company=` query params, passes to QuoteForm
- QuoteForm: pre-fills company and opportunity from query params in create mode

**Phase 5: Minor Fixes** (`OpportunityForm.tsx`):
- Company Autocomplete page_size: 100 → 1000 with `ordering: 'name'`

**Phase 6: Sales Performance Page** (`SalesTargets.tsx` — full rewrite):
- Replaced 100% mock data page with real Won opportunity metrics
- Loads Won + Lost opportunities from API by selected year
- KPI Cards: Total Won Value, Deals Won, Average Deal Size, Win Rate
- Filters: Year selector + Monthly/Quarterly ToggleButtonGroup
- Period breakdown table (groups Won opps by month/quarter with totals row)
- Top 5 Won Deals sidebar (clickable cards → OpportunityDetail)
- Layout.tsx: Sidebar renamed "Targets" → "Performance"

**Key Audit Findings**:
- OpportunityDetail was a stub (highest severity gap)
- SalesTargets page was 100% mock data
- Quote→Opportunity FKs existed but were never auto-populated
- Filter bar used old Grid+DatePicker pattern (inconsistent)
- "View Details" action menu was a no-op
- Industry standard: Salesforce, HubSpot, Zoho all auto-link quotes to opportunities
- Tasks↔Opportunities: frontend type defines `related_opportunity` but backend doesn't have FK (deferred)

---

### Feb 9, 2026 - Zone Management Improvements (Audit-Driven)

**Context**: Professional audit of Zone management system rated it B+ (solid data architecture, gaps in operational/monitoring layer). Implemented top 4 priorities.

**1. Zone-Ticket Linking**:
- Added optional `zone` FK to Ticket model (`0056_ticket_zone_fk.py`)
- TicketSerializer: added `zone`, `zone_name`, `zone_platform` fields
- TicketViewSet: added `zone` to `filterset_fields` and `select_related`
- TicketForm: "Related Zone" dropdown (filtered by company, disabled until company selected)
- TicketForm: reads `?zone=` query param for pre-fill from ZoneDetail
- TicketDetail: clickable zone display with platform chip (navigates to zone detail)

**2. ZoneDetail Enhancements**:
- Added "Last API Sync" to Important Dates card (relative + absolute time, "Never synced" warning, "N/A" for Beat Breeze)
- Added 3rd tab "Support Tickets" showing tickets linked to this zone
- "New Ticket" button pre-fills both company and zone query params

**3. ZonesUnified Sync Health**:
- Added 7th stat card "Sync Health" showing percentage of Soundtrack zones synced in last 24h
- Fixed Last Sync column to use `last_api_sync` instead of `updated_at`

**4. EnhancedZonePicker Overlap Warning**:
- Debounced (500ms) overlap check via `check-overlaps` endpoint
- Non-blocking warning Alert showing conflicting contract numbers
- Passes `contractId` to exclude current contract in edit mode
- Note about renewals: "This may be expected for renewals. Proceed if intentional."

**Backend Endpoints Added**:
- `GET /api/v1/zones/health-summary/` — aggregate status counts, sync health, companies with offline zones
- `GET /api/v1/zones/check-overlaps/?zone_ids=...&exclude_contract=...` — detect zones on other active contracts

**Soundtrack Account ID Hierarchy** (documented from audit):
- Company.soundtrack_account_id → source of truth, used by zone sync
- Contract.soundtrack_account_id → optional override (rare)
- Zone.soundtrack_account_id → read-only property, inherits from Company

---

### Feb 9, 2026 - Tech Support Improvements (Keith's Feedback)

**Context**: IT team feedback on the Tech Support section — 3 items: KB category/tag management, client support integration with sales, company dropdown only showing ~20 entries.

**1. KB Settings Page** (`KBSettings.tsx`, route: `/knowledge-base/settings`):
- New admin page for managing KB categories and tags (full CRUD)
- Categories: hierarchical (parent/child), name, description, active toggle, article count
- Tags: flat with color picker (8 preset colors), article count
- Delete protection when items have articles
- "Settings" button added to Knowledge Base page header
- API methods added: `createKBCategory`, `updateKBCategory`, `deleteKBCategory`, `createKBTag`, `updateKBTag`, `deleteKBTag`
- Backend already supported full CRUD — only frontend UI was missing

**2. Support Tab on CompanyDetail** (360-degree customer view):
- 6th tab: "Support (N)" showing open ticket count
- Ticket list table: Number, Subject, Status, Priority, Assigned To, Created
- Clickable rows → navigate to TicketDetail
- "New Ticket" button → `/tickets/new?company={id}` (pre-fills company)
- "Create Ticket" added to Quick Actions sidebar
- Loads via `ApiService.getTickets({ company: companyId })`

**3. Bidirectional Navigation**:
- TicketForm reads `?company=` query param → auto-selects company in Autocomplete
- TicketDetail company name clickable → navigates to CompanyDetail
- Flow: CompanyDetail → Create Ticket → TicketDetail → Back to CompanyDetail

**4. Company Dropdown Fix** (TicketForm):
- Was: `ApiService.getCompanies()` (no params, ~20 results)
- Now: `ApiService.getCompanies({ page_size: 1000, ordering: 'name' })`
- Same bug pattern as Invoices page

**Build fix**: KBSettings.tsx initially used `Grid` directly — changed to `GridLegacy as Grid` for MUI v6 compat (same pattern as rest of codebase).

**Files modified**: `KBSettings.tsx` (new), `App.tsx` (route), `KnowledgeBase.tsx` (settings link), `CompanyDetail.tsx` (Support tab), `TicketForm.tsx` (company fix + query param), `TicketDetail.tsx` (company link), `api.ts` (6 KB CRUD methods)

---

### Feb 9, 2026 - Filter Bar Consistency (All List Pages)

**Problem**: Each list page had inconsistent filter bars — date pickers that were clunky and often non-functional (backend didn't support the date range params sent by frontend), no sort dropdowns, and some misleading columns.

**Solution**: Standardized all 5 list pages with the same pattern:

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
| **Invoices** | Start Date, End Date, Clear btn | Sort dropdown (5 options) | Fixed Company filter (`contract__company`), added `payment_method` to filterset_fields |

**Backend** (`crm_app/views.py`): Added `updated_at`, `company__name` to ordering_fields for ContactViewSet, ContractViewSet, QuoteViewSet, and InvoiceViewSet. Also added `contract_number` for ContractViewSet. Fixed InvoiceViewSet: added `payment_method` and `contract__company` to filterset_fields (both dropdown filters were silently broken — Invoice has no direct company FK, only through Contract).

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
- **Invoices**: Newest/Oldest (Issue Date), Due Date Soonest, Highest Amount, Company

**Removed dependencies**: `DatePicker`, `LocalizationProvider`, `AdapterDateFns`, `GridLegacy` from Contacts/Contracts/Quotes/Invoices pages.

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
