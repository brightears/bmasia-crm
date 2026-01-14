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

## Pending Features

### PDF/Excel Export (Not Yet Implemented)
All finance reports should have export functionality:
- **PDF Export**: Professional formatted reports with BMAsia branding
- **Excel Export**: Data tables for further analysis

Reports needing export:
- [ ] Revenue Dashboard
- [ ] AR Aging Report
- [ ] AP Aging Report
- [ ] Profit & Loss Statement
- [ ] Cash Flow Statement
- [ ] Balance Sheet

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
- Backend Services: `crm_app/services/profit_loss_service.py`, `cash_flow_service.py`
- Frontend Pages: `ProfitLoss.tsx`, `CashFlow.tsx`, `AccountsReceivable.tsx`, `AccountsPayable.tsx`
- Plan file: `.claude/plans/memoized-churning-bird.md`

## Multi-Entity Support
- BMAsia (Thailand) Co., Ltd. - THB
- BMAsia Limited (Hong Kong) - USD
- All reports filter by billing_entity and currency
