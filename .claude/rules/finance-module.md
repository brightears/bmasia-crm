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
| 6 | Balance Sheet | 🚧 Pending | `/finance/balance-sheet` |

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

## Phase 6: Balance Sheet (Quarterly) - PLANNED
- **Components**: Assets (Cash, AR, Fixed Assets), Liabilities (AP), Equity (Retained Earnings)
- **AR Integration**: Uses Invoice aging data
- **AP Integration**: Uses ExpenseEntry aging data
- **CapEx**: From ExpenseEntry where category_type='capex'
- **Depreciation**: Country-specific rules (Thailand: 3-5 years, HK: 3-5 years)

## Key Files
- Backend Services: `crm_app/services/profit_loss_service.py`, `cash_flow_service.py`
- Frontend Pages: `ProfitLoss.tsx`, `CashFlow.tsx`, `AccountsReceivable.tsx`, `AccountsPayable.tsx`
- Plan file: `.claude/plans/memoized-churning-bird.md`

## Multi-Entity Support
- BMAsia (Thailand) Co., Ltd. - THB
- BMAsia Limited (Hong Kong) - USD
- All reports filter by billing_entity and currency
