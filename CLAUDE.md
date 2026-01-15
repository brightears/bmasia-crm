# Claude Code Instructions for BMAsia CRM

## 🚨 CRITICAL RULES

1. **NEVER suggest local testing** - This project runs on Render.com, not localhost
2. **ALWAYS deploy to Render** and test on production URLs
3. **ALWAYS use sub-agents** for specialized tasks (see `.claude/rules/subagents.md`)
4. **Keep documentation updated** in `.claude/rules/` files

## Quick Reference

| Documentation | Location |
|--------------|----------|
| Deployment workflow | `.claude/rules/deployment.md` |
| Sub-agent usage | `.claude/rules/subagents.md` |
| Finance module | `.claude/rules/finance-module.md` |
| Implementation history | `.claude/rules/implementation-history.md` |
| Finance plan | `.claude/plans/memoized-churning-bird.md` |

## Production URLs

- **Backend**: https://bmasia-crm.onrender.com
- **Frontend**: https://bmasia-crm-frontend.onrender.com
- **Admin**: https://bmasia-crm.onrender.com/admin/

## Project Overview

BMAsia CRM is a comprehensive Customer Relationship Management system:
- **Backend**: Django + Django REST Framework
- **Frontend**: React + TypeScript + Material-UI
- **Database**: PostgreSQL on Render
- **Integrations**: Soundtrack Your Brand API, Gmail SMTP

## Key Features

- ✅ Company/Contact/Contract/Quote/Invoice management
- ✅ Soundtrack API integration for zone management
- ✅ Email automation with sequences and triggers
- ✅ Professional PDF generation (Quotes, Invoices, Contracts)
- ✅ Finance module (Revenue, AR, AP, P&L, Cash Flow, Balance Sheet) - ALL 6 PHASES COMPLETE

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/deploy-backend` | Deploy Django to Render |
| `/deploy-frontend` | Deploy React to Render |
| `/deploy-all` | Deploy both services |
| `/test-api` | Test API endpoints |
| `/commit-push` | Git commit and push |
| `/save-checkpoint` | Create session checkpoint |

## Current Work (January 2026)

### Finance & Accounting Module
| Phase | Status | Route |
|-------|--------|-------|
| 1. Revenue Dashboard | ✅ | `/revenue` |
| 2. AR Aging | ✅ | `/finance/ar` |
| 3. Expense + AP Aging | ✅ | `/finance/ap` |
| 4. Profit & Loss | ✅ | `/finance/pl` |
| 5. Cash Flow | ✅ | `/finance/cash-flow` |
| 6. Balance Sheet | ✅ | `/finance/balance-sheet` |

### Contract Templates (Jan 15, 2026)
- **Management Page**: `/contract-templates` - Full CRUD for contract templates
- **ContractForm Dropdown**: Select template when creating/editing contracts
- **Files**: `ContractTemplates.tsx`, `ContractTemplateForm.tsx`
- **Navigation**: Administration → Contract Templates
- **Variables**: `{{company_name}}`, `{{contract_number}}`, `{{start_date}}`, `{{end_date}}`, `{{value}}`, `{{currency}}`

## Key Project Files

### Backend (Django)
- Models: `crm_app/models.py`
- Views: `crm_app/views.py`
- Services: `crm_app/services/`
- Admin: `crm_app/admin.py`

### Frontend (React)
- Pages: `bmasia-crm-frontend/src/pages/`
- Components: `bmasia-crm-frontend/src/components/`
- API: `bmasia-crm-frontend/src/services/api.ts`
- Types: `bmasia-crm-frontend/src/types/index.ts`

## Environment Variables

Key variables in `.env`:
- `DATABASE_URL` - PostgreSQL connection
- `EMAIL_HOST_USER/PASSWORD` - Gmail SMTP
- `RENDER_API_KEY` - Render deployment API
- `SOUNDTRACK_API_TOKEN` - Soundtrack API

## Best Practices

1. **Use sub-agents** for specialized tasks
2. **Deploy and test** on Render after changes
3. **Update `.claude/rules/`** when making architectural changes
4. **Save checkpoints** before context limit with `/save-checkpoint`

## Multi-Entity Support

| Entity | Currency | For |
|--------|----------|-----|
| BMAsia (Thailand) Co., Ltd. | THB | Thailand/HK clients |
| BMAsia Limited | USD | International clients |

---

**For detailed documentation, see the `.claude/rules/` directory.**
