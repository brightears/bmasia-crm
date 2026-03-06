# Finance & Accounting Module

## Overview
Comprehensive financial reporting module for BMAsia CRM. Replaces manual spreadsheet work with integrated CRM-based reporting.

## Implementation Status (January 2026)

| Phase | Feature | Status | Route |
|-------|---------|--------|-------|
| 1 | Revenue Dashboard | ✅ Complete | `/revenue` |
| 2 | AR Aging | ✅ Complete | `/finance/ar` |
| 3 | Expense Module + AP Aging | ✅ Complete | `/finance/ap` |
| 4 | Profit & Loss | ✅ Complete | `/finance/pl` |
| 5 | Cash Flow | ✅ Complete | `/finance/cash-flow` |
| 6 | Balance Sheet | ✅ Complete | `/finance/balance-sheet` |
| 8 | Revenue Accrual / Recognition | ✅ Complete | `/finance/revenue-accrual` |

## Revenue Accrual / Recognition (Phase 8) - COMPLETE

Accrual-based revenue recognition matching Pom's spreadsheet format.
- **Models**: `RevenueRecognitionSchedule`, `RevenueRecognitionEntry`
- **Service**: `revenue_recognition_service.py` — recognition engine, Excel import, quarterly summaries
- **Formula**: `daily_rate = amount / total_service_days; quarterly_income = daily_rate × quarter_days`
- **Balance Sheet**: `deferred_revenue` field on `BalanceSheetSnapshot`, auto-calculated from entries
- **API**: `/api/v1/revenue-recognition/` (summary, schedules, import, generate, regenerate, cancel, deferred-revenue, export)
- **Frontend**: KPI cards, stacked bar chart, Pom-format quarterly table, Excel import dialog, info banner when 0% recognized
- **Import**: Supports both HK (day-based) and TH (month/day-based) Excel formats. Uses parallel list for quarterly data (NOT object attributes — bulk_create loses them)
- **Auto-generation**: `generate_schedule_from_invoice()` creates recognition schedules from invoice line items when service period dates are set. Hooked into invoice creation flow.
- **Migration**: `0086_revenue_recognition_module.py`
- **Key fix**: Import quarterly data stored in parallel list (not object attrs). Cumulative balance pre-calculates from prior years. Commit `21333cdc`

## PDF/Excel Export (Phase 7) - COMPLETE

### FinanceExportService (`crm_app/services/finance_export_service.py`)
Generates professional PDF and Excel exports for finance reports.

#### API Endpoints
| Report | PDF Export | Excel Export |
|--------|------------|--------------|
| Profit & Loss | `GET /api/v1/profit-loss/export/pdf/` | `GET /api/v1/profit-loss/export/excel/` |
| Cash Flow | `GET /api/v1/cash-flow/export/pdf/` | `GET /api/v1/cash-flow/export/excel/` |
| Balance Sheet | `GET /api/v1/balance-sheet/export/pdf/` | `GET /api/v1/balance-sheet/export/excel/` |

#### Query Parameters
- **P&L / Cash Flow**: `year`, `month` (or `through_month` for YTD), `billing_entity`, `currency`
- **Balance Sheet**: `year`, `quarter`, `billing_entity`, `currency`

#### Features
- BMAsia branding with orange (#FFA500) accents
- Professional table formatting with alternating row colors
- Currency formatting based on selected currency
- Header with logo, period, entity info
- Footer with generation timestamp
- Excel: Auto-fit columns, proper number formatting

### Pending Export Features
- [ ] Revenue Dashboard export
- [ ] AR Aging Report export
- [ ] AP Aging Report export

## Phase 1: Revenue Dashboard
- **Models**: MonthlyRevenueSnapshot, MonthlyRevenueTarget, ContractRevenueEvent
- **Fields**: Contract.lifecycle_type (new/renewal/addon/churn)
- **API**: `/api/v1/revenue/`

## Phase 2: AR Aging Report
- **Service**: AR Aging with 30/60/90+ day buckets
- **API**: `/api/v1/ar-aging/`

## Phase 3: Expense Module + AP Aging
- **Models**: Vendor, ExpenseCategory, RecurringExpense, ExpenseEntry
- **Migration**: `0049_expense_module.py`
- **API**: `/api/v1/expenses/`, `/api/v1/ap-aging/`

## Phase 4: Profit & Loss Report
- **Service**: ProfitLossService (monthly, YTD, comparative, trend)
- **Structure**: Revenue → COGS → Gross Profit → OpEx (G&A, S&M) → Net Profit
- **API**: `/api/v1/profit-loss/monthly/`, `/ytd/`, `/comparative/`, `/trend/`

## Phase 5: Cash Flow Statement
- **Model**: CashFlowSnapshot (manual overrides supported)
- **Service**: CashFlowService (Operating, Investing, Financing activities)
- **Data Sources**: Invoice.paid_date, ExpenseEntry.payment_date
- **Migration**: `0050_cash_flow_module.py`
- **API**: `/api/v1/cash-flow/monthly/`, `/ytd/`, `/trend/`

## Phase 6: Balance Sheet (Quarterly) ✅ COMPLETE
- **Model**: BalanceSheetSnapshot (quarterly snapshots with manual overrides)
- **Service**: BalanceSheetService (quarterly and trend calculations)
- **Data Sources**:
  - Cash & Bank: from CashFlowSnapshot closing balance
  - AR: from Invoice where status in ['Sent', 'Overdue']
  - Fixed Assets: from ExpenseEntry where category_type='capex'
  - AP: from ExpenseEntry where status in ['pending', 'approved']
  - Retained Earnings: from cumulative P&L net profit
- **Depreciation**: Country-specific rates (Computer: 33.33%/3yr, Office: 20%/5yr)
- **Migration**: `0051_balance_sheet_module.py`
- **API**: `/api/v1/balance-sheet/quarterly/`, `/trend/`

## Key Files
- Backend Services:
  - `crm_app/services/profit_loss_service.py`
  - `crm_app/services/cash_flow_service.py`
  - `crm_app/services/balance_sheet_service.py`
  - `crm_app/services/finance_export_service.py` (PDF/Excel export)
- Frontend Pages: `ProfitLoss.tsx`, `CashFlow.tsx`, `AccountsReceivable.tsx`, `AccountsPayable.tsx`, `BalanceSheet.tsx`
- Views: `crm_app/views.py` (ProfitLossViewSet, CashFlowViewSet, BalanceSheetViewSet)
- Plan file: `.claude/plans/memoized-churning-bird.md`

## Multi-Entity Support
- BMAsia (Thailand) Co., Ltd. - THB
- BMAsia Limited (Hong Kong) - USD
- All reports filter by billing_entity and currency
