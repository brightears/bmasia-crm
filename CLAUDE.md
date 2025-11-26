# Claude Code Instructions for BMAsia CRM

## 🚨 CRITICAL: DEPLOYMENT AND TESTING

**THIS PROJECT RUNS ON RENDER.COM - NOT LOCALHOST**

### Deployment Requirements
- **NEVER suggest local testing** (no `python manage.py runserver`, no `npm start`)
- **ALWAYS deploy to Render** using MCP access
- **ALWAYS test on production URLs** after deployment

### Production Infrastructure
- **Platform**: Render.com (cloud hosting)
- **Backend URL**: https://bmasia-crm.onrender.com
- **Frontend URL**: https://bmasia-crm-frontend.onrender.com
- **Admin Panel**: https://bmasia-crm.onrender.com/admin/
- **Database**: PostgreSQL on Render (dpg-d3cbikd6ubrc73el0ke0-a)

### Standard Deployment Workflow
1. Make code changes
2. Commit to Git: `git add . && git commit -m "message"`
3. Push to GitHub: `git push origin main`
4. Deploy backend: `curl -X POST -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services/srv-d13ukt8gjchc73fjat0g/deploys`
5. Deploy frontend: `curl -X POST -H "Authorization: Bearer $RENDER_API_KEY" https://api.render.com/v1/services/srv-d3clctt6ubrc73etb580/deploys`
6. Wait for deployments to complete (check status via Render API)
7. Test on production URLs

### Render Service IDs
- Backend (Django): `srv-d13ukt8gjchc73fjat0g`
- Frontend (React): `srv-d3clctt6ubrc73etb580`
- Email Automation Cron: `crn-d4b9g875r7bs7391al2g`
- PostgreSQL Database: `dpg-d3cbikd6ubrc73el0ke0-a`

### Render API Key
- Use environment variable: `rnd_QAJKR0jggzsxSLOCx3HfovreCzOd`
- Available via MCP access for deployment automation

---

## Project Overview
BMAsia CRM is a comprehensive Customer Relationship Management system built with Django (backend) and React (frontend), designed specifically for BMAsia, a music technology company. The system integrates with Soundtrack Your Brand API and manages customers, zones, contracts, and automated email communications.

## IMPORTANT: Always Use Specialized Sub-Agents

When working on this project, **ALWAYS** use the appropriate specialized sub-agent for the task at hand. This ensures optimal code quality, consistency, and leverages specialized expertise.

### Available Sub-Agents and Their Use Cases

#### 1. **django-admin-expert**
Use this agent when:
- Creating or modifying Django admin interfaces
- Adding bulk operations or custom admin actions
- Implementing CSV/Excel export functionality
- Optimizing admin querysets (select_related, prefetch_related)
- Creating custom admin forms, filters, or displays
- Working with files: `crm_app/admin.py`, `crm_app/admin_views.py`

#### 2. **django-testing-agent**
Use this agent when:
- Writing pytest tests for models, views, or services
- Creating test fixtures with factory_boy
- Testing API endpoints
- Mocking external services (Soundtrack API, email)
- Improving test coverage
- Working with files in: `crm_app/tests/`

#### 3. **react-dashboard-builder**
Use this agent when:
- Building React components for the dashboard
- Creating data visualizations with Recharts
- Implementing authentication flows
- Managing state with Context API or Redux
- Integrating with Django REST APIs
- Working with files in: `bmasia-crm-frontend/`

#### 4. **api-integration-specialist**
Use this agent when:
- Integrating with Soundtrack Your Brand API
- Adding new external API integrations
- Implementing retry logic and error handling
- Working with GraphQL or REST APIs
- Handling authentication (OAuth, JWT, API keys)
- Working with files: `crm_app/services/soundtrack_api.py`, API service files

#### 5. **database-optimizer**
Use this agent when:
- Creating database indexes
- Optimizing Django ORM queries
- Writing complex database migrations
- Implementing caching strategies
- Analyzing query performance
- Working with PostgreSQL-specific features

#### 6. **email-automation-specialist**
Use this agent when:
- Creating or modifying email templates
- Setting up automated email campaigns
- Implementing email scheduling
- Improving email deliverability
- Adding email tracking features
- Working with files: `crm_app/services/email_service.py`, email templates

#### 7. **frontend-auth-specialist**
Use this agent when:
- Implementing JWT token management
- Creating login/logout flows
- Setting up protected routes in React
- Managing authentication state with Context API
- Implementing role-based component rendering
- Adding session management features
- Working with files: `bmasia-crm-frontend/src/contexts/AuthContext.tsx`, auth components

#### 8. **ui-ux-designer**
Use this agent when:
- Creating consistent design systems
- Implementing responsive layouts
- Adding loading states and error handling
- Designing navigation flows
- Implementing accessibility features
- Creating animations and transitions
- Working with files: UI components, styles, layouts in `bmasia-crm-frontend/`

#### 9. **data-visualization-expert**
Use this agent when:
- Building interactive dashboards with Recharts
- Creating sales pipeline visualizations
- Designing KPI cards and metrics displays
- Implementing real-time data updates
- Creating exportable reports with charts
- Building comparison and trend analysis views
- Working with files: Dashboard components, chart components in `bmasia-crm-frontend/`

## Key Features Implemented

### Company Management
- **Legal Entity Names**: Separate field for registered company names (e.g., "Hilton Pattaya" displays as "CPN Pattaya Hotel Co., Ltd." on PDFs)
- **Billing Entities**: Two entities supported:
  - BMAsia Limited (Hong Kong) - for international clients
  - BMAsia (Thailand) Co., Ltd. - for Thailand/Hong Kong clients
- **Smart Defaults**: Auto-selects billing entity based on country:
  - Thailand/Hong Kong → BMAsia (Thailand) Co., Ltd.
  - All other countries → BMAsia Limited
- **Forms**: Three interfaces all with same fields:
  - `CompanyNew.tsx` - Standalone new company page
  - `CompanyEdit.tsx` - Standalone edit page
  - `CompanyForm.tsx` - Modal dialog (used from Companies list)

### PDF Generation (Quotes, Invoices, Contracts)
- **Professional Design**: Modern 2025 layouts with BMAsia orange branding (#FFA500)
- **Entity-Specific**: Shows correct BMAsia entity address, bank details, tax info
- **Tax Labeling**:
  - Thailand entities → "VAT (7.0%): ฿900.00"
  - Hong Kong entities → "Tax (0.0%): $0.00"
- **Discount Display**: Shows percentage + amount: "Discount (10.0%): -฿500.00"
- **Legal Entity Names**: Uses legal_entity_name when available, falls back to name
- **Optimizations**: Single-page quotes for simple items, optimized logo (880x377px)
- **File**: `crm_app/views.py` (lines ~515-1750)

### Quote Line Items
- **Discount %**: Per-item discount percentage (0-100%)
- **Tax Rate**: Per-item tax rate (0-100%, typically 7% for Thailand)
- **Calculations**: Automatic line total, subtotal, discount, tax, and total calculations
- **UI**: Clear percentage display in form with centered text and proper styling
- **File**: `bmasia-crm-frontend/src/components/QuoteForm.tsx`

### Email Campaign Management (November 2025) ✅ COMPLETE

#### Email Sequences (Drip Campaigns)
- **Multi-Step Automation**: Create sequences with unlimited steps, each with customizable delays
- **Conditional Logic**: Steps can include conditions (field, operator, value) to control execution flow
- **Trigger Types**: Manual enrollment or automatic triggers (contract_signed, renewal_30_days, renewal_7_days, payment_overdue)
- **Time Control**: Specify days delay + send time (e.g., "3 days after enrollment at 9:00 AM")
- **Enrollment Tracking**: Full lifecycle tracking (pending → active → completed/paused/cancelled)
- **Email History**: Individual email tracking with status (pending, sent, failed, bounced, opened, clicked)
- **Cron Processing**: Automated execution every 20 minutes via Render cron job
- **Models**: EmailSequence, EmailSequenceStep, SequenceEnrollment, SequenceEmail (`crm_app/models.py` lines 1320-1599)
- **UI Components**: EmailSequences.tsx, EmailSequenceForm.tsx, EmailSequenceStepForm.tsx, SequenceEnrollments.tsx, EnrollSequenceDialog.tsx

#### Automatic Renewal Reminders
- **Smart Timing**: Automatically sends at 30/14/7 days before contract expiration
- **Template Matching**: Uses EmailTemplate with type: renewal_30_days, renewal_14_days, renewal_7_days, renewal_urgent
- **Daily Processing**: Cron job runs at 9 AM Bangkok time daily
- **Duplicate Prevention**: 24-hour block prevents re-sending
- **Variable Support**: {{company_name}}, {{contact_name}}, {{contract_number}}, {{end_date}}, {{days_until_expiry}}, {{monthly_value}}
- **Smart Recipients**: Auto-selects billing contacts (or all contacts if none specified)
- **Zero Configuration**: Just create active template with correct type - system handles the rest

#### Email Template Variable Guide
- **Rich Variable Display**: Shows all available variables with descriptions in tooltips
- **Template-Specific**: Different variables per template type (renewal, invoice, payment, etc.)
- **Common Variables**: Shared variables (company_name, contact_name, current_year, unsubscribe_url) for all templates
- **Insert Functionality**: One-click insertion at cursor position
- **Copy to Clipboard**: Click chip to copy variable
- **Backend Sync**: Frontend matches backend TemplateVariable structure exactly
- **File**: `EmailTemplateForm.tsx` lines 94-616, `types/index.ts` lines 714-736

## Key Project Files and Locations

### Backend (Django)
- **Models**: `crm_app/models.py` (20+ entities including Company, Contact, Contract, Zone, Quote, Email Sequences)
  - Company model (lines 87-170): billing_entity, legal_entity_name fields
  - Quote model (lines 1069-1150): subtotal, tax_amount, discount_amount
  - QuoteLineItem model (lines 1153-1177): discount_percentage, tax_rate
  - EmailSequence model (lines 1320-1389): name, sequence_type, trigger_event, steps
  - EmailSequenceStep model (lines 1392-1465): step_order, days_delay, send_time, conditions
  - SequenceEnrollment model (lines 1468-1539): status, current_step_index, next_send_date
  - SequenceEmail model (lines 1542-1599): tracks individual emails sent in sequences
- **Admin**: `crm_app/admin.py` (comprehensive admin interface)
- **Views/PDFs**: `crm_app/views.py` - PDF generation for Quotes, Invoices, Contracts
- **Services**: `crm_app/services/` (business logic, API integrations)
- **Email System**: `crm_app/services/email_service.py`
- **API Integration**: `crm_app/services/soundtrack_api.py`
- **Settings**: `bmasia_crm/settings.py`
- **Serializers**: `crm_app/serializers.py` - includes legal_entity_name, billing_entity

### Frontend (React + TypeScript + Material-UI)
- **Main App**: `bmasia-crm-frontend/src/App.tsx`
- **Components**:
  - `CompanyForm.tsx` - Modal dialog for create/edit (with legal_entity_name, billing_entity)
  - `QuoteForm.tsx` - Quote creation with line items (discount %, tax %)
  - Company pages: `CompanyNew.tsx`, `CompanyEdit.tsx`, `Companies.tsx`
  - **Email Automation Components** (Unified Nov 26, 2025):
    - `EmailAutomations.tsx` - Unified list with filter tabs (All/Automatic/Manual)
    - `EmailSequenceForm.tsx` - Create/edit sequences with step management
    - `EmailSequenceStepForm.tsx` - Configure individual sequence steps with conditions
    - `SequenceEnrollments.tsx` - View/manage enrollments for a sequence
    - `EnrollSequenceDialog.tsx` - Enroll companies/contacts in sequences
    - `EmailTemplateForm.tsx` - Create/edit templates with variable guide
- **Services**:
  - `api.ts` - API service layer with Axios (includes sequence methods)
  - `authService.ts` - JWT authentication
- **Types**: `types/index.ts` - TypeScript interfaces for all entities (includes EmailSequence, SequenceEnrollment, TemplateVariable)
- **Context**: `AuthContext.tsx` - Authentication state management

### Database
- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Render (dpg-d3cbikd6ubrc73el0ke0-a)
- **Migrations**: `crm_app/migrations/`
  - Latest: `0039_create_default_automations.py` (Creates default system automations)
  - `0038_add_sequence_types_and_enrollment_source.py` (Email automation consolidation)
  - `0025_user_smtp_email_user_smtp_password.py` (Per-user SMTP fields)
  - `0022_emailsequence_emailsequencestep_sequenceenrollment_sequenceemail.py` (Email sequences models)

## Environment Variables (.env)

Key environment variables:
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (True for development)
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`: Gmail SMTP configuration (requires App Password)
- `DEFAULT_FROM_EMAIL`: Default sender email (e.g., "BMAsia Music <norbert@bmasiamusic.com>")
- `ADMIN_EMAIL`, `FINANCE_SENDER_EMAIL`, `SALES_SENDER_EMAIL`, `SUPPORT_SENDER_EMAIL`, `PRODUCTION_EMAIL`: Multi-user sender emails
- `SITE_URL`: Site URL for email links (default: https://bmasia-crm.onrender.com)
- `SOUNDTRACK_API_TOKEN`, `SOUNDTRACK_CLIENT_ID`, `SOUNDTRACK_CLIENT_SECRET`: Soundtrack API
- `RENDER_API_KEY`: Render platform API key

## Development Workflow

### Local Development Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=crm_app

# Run specific test file
pytest crm_app/tests/test_models.py
```

### Frontend Development
```bash
cd bmasia-crm-frontend
npm install
npm start  # Development server
npm run build  # Production build
```

## Production Deployment

- **Platform**: Render.com
- **URL**: https://bmasia-crm.onrender.com
- **Admin**: /admin/ (username: admin, password: bmasia123)
- **Auto-deploy**: Enabled from main branch
- **Database**: PostgreSQL on Render

## Common Tasks and Which Agent to Use

| Task | Recommended Agent |
|------|-------------------|
| Add bulk email sending to admin | django-admin-expert |
| Write tests for new model | django-testing-agent |
| Create sales dashboard | react-dashboard-builder |
| Fix Soundtrack API sync | api-integration-specialist |
| Optimize slow queries | database-optimizer |
| Add email preview feature | email-automation-specialist |
| Export data to Excel | django-admin-expert |
| Add database indexes | database-optimizer |
| Create email templates | email-automation-specialist |
| Build analytics charts | data-visualization-expert |
| Set up user authentication | frontend-auth-specialist |
| Design responsive layouts | ui-ux-designer |
| Create KPI dashboards | data-visualization-expert |
| Implement role-based views | frontend-auth-specialist |

## Best Practices

1. **Always use the appropriate sub-agent** for specialized tasks
2. **Run tests** after making changes: `pytest`
3. **Check linting** before committing: `flake8` (Python), `npm run lint` (React)
4. **Update migrations** after model changes: `python manage.py makemigrations`
5. **Document API changes** in the relevant documentation files
6. **Test locally** before pushing to production
7. **Use environment variables** for sensitive data, never hardcode

## Current Status (November 2025)

### Backend (Django)
- ✅ Core CRM functionality (Companies, Contacts, Contracts, Quotes, Invoices)
- ✅ Soundtrack API integration working
- ✅ Email automation system complete
- ✅ PostgreSQL production database on Render
- ✅ Professional PDF generation (Quotes, Invoices, Contracts) with BMAsia branding
- ✅ Multi-entity support (BMAsia Limited HK + BMAsia Thailand Co., Ltd.)
- ✅ Legal entity name field for registered company names
- ✅ Smart billing entity defaults based on country
- ✅ **Email Sequences (Drip Campaigns)** - Complete with conditional logic and cron automation
- ✅ **Automatic Renewal Reminders** - Daily processing with 30/14/7-day advance notices
- ✅ **Email Template Variable System** - Rich variable guide with descriptions

### Frontend (React + TypeScript)
- ✅ Authentication with JWT tokens (AuthContext)
- ✅ Dashboard with company/opportunity metrics
- ✅ Companies management (list, create, edit, delete with modal forms)
- ✅ Contacts management
- ✅ Opportunities pipeline
- ✅ Quotes creation and management
- ✅ Material-UI components throughout
- ✅ Legal entity name + billing entity in all company forms
- ✅ Email sending UI (EmailSendDialog component integrated in Contracts/Quotes)
- ✅ **Email Sequences UI** - Full CRUD with step configuration and enrollment management
- ✅ **Email Template Variable Guide** - Interactive variable insertion with tooltips

### Recent Improvements (November 2025)
- ✅ **Email Automations Consolidation** - Unified system (Nov 26, 2025)
  - Merged "Email Automation" (Settings) with "Email Sequences" (Marketing)
  - Single "Email Automations" page with filter tabs (All/Automatic/Manual)
  - New sequence_type field: manual, auto_renewal, auto_payment, auto_quarterly
  - AutoEnrollmentService for automatic contact enrollment
  - 3 pre-built system automations (Renewal, Payment, Quarterly)
  - Backward-compatible redirects from old URLs
  - Settings page now shows redirect notice
- ✅ **Email Sequences (Drip Campaigns)** - Complete 4-phase implementation (Nov 19, 2025)
  - Multi-step automation with conditional logic
  - Time-based delays and send scheduling
  - Enrollment tracking with full lifecycle management
  - Email history and status tracking
  - Cron job processing every 20 minutes
- ✅ **Automatic Renewal Reminders** - Zero-configuration automation (Nov 19, 2025)
  - Template type matching (renewal_30_days, renewal_14_days, renewal_7_days, renewal_urgent)
  - Daily cron at 9 AM Bangkok time
  - Smart recipient selection and duplicate prevention
  - Full variable substitution support

### Previous Improvements (October 2025)
- ✅ PDF design overhaul - modern 2025 professional layouts
- ✅ Logo optimization (auto-cropped, proper sizing)
- ✅ Single-page quotes for simple items
- ✅ Discount/tax display shows percentages + amounts
- ✅ VAT labeling for Thailand entities
- ✅ Fixed billing entity race condition bug
- ✅ Delete company functionality with confirmation dialog
- ✅ **Contract currency display fixes** (Oct 11, 2025)
- ✅ **Contract PDF download functionality** (Oct 11, 2025)
- ✅ **Email sending infrastructure complete** (Oct 11-12, 2025)
- ✅ **Per-user SMTP system complete** (Oct 12, 2025) - Full frontend + backend integration
- ✅ **Production deployment fixes** (Oct 12, 2025) - Database & email configuration
- ✅ **Email sending fully tested and operational** (Oct 12, 2025) - Quote Q-2025-1012-818 sent successfully

### Known Issues & Workarounds
- ✅ **ALL CRITICAL ISSUES RESOLVED** (Oct 12, 2025)
  - ✅ Database connectivity fixed (using internal PostgreSQL connection)
  - ✅ Email sending operational (SMTP credentials configured)
  - ✅ Migration deployment working correctly
  - See `DEPLOYMENT_TROUBLESHOOTING.md` for details and solutions

### Email System (October 2025) ✅ FULLY OPERATIONAL

**Backend - COMPLETE** ✅
- ✅ EmailTemplate model with 4 new template types (quote_send, contract_send, invoice_send, renewal_manual)
- ✅ Enhanced admin interface with variable guide and rich text editing
- ✅ Multi-user sender configuration (norbert, pom, nikki.h, keith, production) - Fixed typo: niki.h → nikki.h
- ✅ Email sending methods in email_service.py with PDF attachments
- ✅ ViewSet actions: POST /api/quotes/{id}/send/, /api/contracts/{id}/send/, /api/invoices/{id}/send/
- ✅ 24-hour block for manual renewal reminders
- ✅ Smart recipient selection (billing contacts for invoices, decision makers for renewals)
- ✅ **Gmail App Password configured** (Oct 11, 2025)
- ✅ **Email sending tested with real SMTP** (Oct 12, 2025)
- ✅ **Quote Q-2025-1012-818 sent successfully** to platzer.norbert@gmail.com (Oct 12, 2025)
- ✅ **PDF generation fixed for all document types** (Oct 12, 2025)
- ✅ **Environment variables configured on Render production** (Oct 12, 2025)
  - DATABASE_URL: Internal PostgreSQL connection (dpg-d3cbikd6ubrc73el0ke0-a)
  - EMAIL_HOST_USER: norbert@bmasiamusic.com
  - EMAIL_HOST_PASSWORD: [Gmail App Password]
  - DEFAULT_FROM_EMAIL: BMAsia Music <norbert@bmasiamusic.com>
- ✅ **Default email templates created** (4 professional templates - editable in admin)
- ✅ **Production testing complete** - Email sending working end-to-end

**Per-User SMTP System - COMPLETE** ✅ (Oct 12, 2025)
- ✅ User model extended with smtp_email and smtp_password fields
- ✅ Migration 0025 created and deployed to production
- ✅ Per-user SMTP logic in email_service.py with intelligent fallback
- ✅ Fallback to EMAIL_SENDERS config when user has no SMTP configured
- ✅ Admin interface for SMTP configuration with password widget
- ✅ USER_SMTP_SETUP_GUIDE.md created for team onboarding
- ✅ Deployed to production (commit 1ad460d8)

**Frontend - COMPLETE** ✅ (Oct 12, 2025)
- ✅ EmailSendDialog component with Material-UI design
- ✅ Multi-select recipient checkboxes (auto-selects Primary/Billing contacts)
- ✅ Editable subject and body fields with smart defaults
- ✅ Loading states and error handling
- ✅ API methods: sendContractEmail, sendQuoteEmail, sendInvoiceEmail
- ✅ Integrated into Contracts page (Send Email menu item)
- ✅ Integrated into Quotes page (Send Quote functionality)
- ✅ Success notifications with auto-dismiss
- ✅ BMAsia orange branding (#FFA500)

**How It Works**:
1. Admin configures SMTP credentials via Django admin (https://bmasia-crm.onrender.com/admin/)
2. Each user has optional smtp_email and smtp_password fields
3. When user sends email, system uses their SMTP credentials
4. If user has no SMTP configured, falls back to EMAIL_SENDERS default
5. Emails sent from user's Gmail account, replies go to their inbox
6. See USER_SMTP_SETUP_GUIDE.md for complete setup instructions

**Optional Future Enhancement** 🚧
- 🚧 AI email drafting with OpenAI (Phase 4 - Optional)

### Contract Management (October 2025)
- ✅ Currency display with locale mapping (THB → th-TH, USD → en-US, EUR → de-DE, GBP → en-GB)
- ✅ Fixed double currency symbol issue (removed AttachMoney icon)
- ✅ Dynamic currency symbol in ContractForm ($ / ฿ / € / £)
- ✅ PDF download functionality (downloadContractPDF in api.ts)
- ✅ "Download PDF" menu option (renamed from "Export")

### Areas for Future Development
- 🚧 Test coverage needs improvement
- 🚧 Invoice management UI expansion
- 🚧 Email analytics dashboard (open rates, click tracking)
- 🚧 Soundtrack API sync automation
- 🚧 A/B testing for email sequences
- 🚧 Template versioning and rollback
- 🚧 Advanced audience segmentation
- 🚧 AI email drafting integration (Optional)

## Support and Documentation

- **Initial Design**: `BMAsia_CRM_initial_design.md`
- **Email System**: `EMAIL_SYSTEM_STATUS.md`
- **Database Setup**: `DATABASE_SETUP.md`
- **Soundtrack API**: `SOUNDTRACK_API_SETUP.md`
- **Zone Tracking**: `ZONE_TRACKING_GUIDE.md`
- **Session Checkpoints**: `SESSION_CHECKPOINT_2025-*.md` (detailed session histories)
  - `SESSION_CHECKPOINT_2025-11-19.md` - Email Sequences, Renewal Reminders, Variable Guide (latest)

## Render Platform Access

The project includes Render MCP integration for managing the production infrastructure:
- Check service status
- View logs and metrics
- Manage database
- Deploy updates

Use `RENDER_API_KEY` from .env for API access.

---

**Remember**: When in doubt about which agent to use, refer to the "Available Sub-Agents and Their Use Cases" section above. Using the right agent ensures the best quality code and fastest development.