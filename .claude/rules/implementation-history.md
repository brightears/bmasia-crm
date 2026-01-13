# Implementation History - BMAsia CRM

## January 2026

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
- `0050_cash_flow_module.py` - CashFlowSnapshot model
- `0049_expense_module.py` - Expense tracking
- `0047_zone_management_improvements.py` - Zone improvements
- `0046_soundtrack_offline_alerts.py` - Offline alerts
- `0045_contract_send_renewal_reminders.py` - Multi-year support
- `0044_contact_email_preferences.py` - Email preferences
- `0043_seasonal_automation_system.py` - Seasonal campaigns
