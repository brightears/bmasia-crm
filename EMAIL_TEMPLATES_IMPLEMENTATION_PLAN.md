# Email Templates Implementation Plan
**Date:** November 18, 2025
**Status:** APPROVED - Ready for Implementation
**Timeline:** 1-2 weeks (Normal priority)

## Executive Summary

Implement user-friendly Email Templates management UI to replace the current placeholder page. Templates already exist in backend but are only accessible via Django admin. This feature enables:
- Reusable email content for automated business processes
- Multi-language support (EN/TH)
- Template variables that auto-fill customer data
- Integration with campaign creation
- Professional, consistent messaging across all customer communications

## Current State (From Investigation)

### Backend ✅ FULLY IMPLEMENTED
- **EmailTemplate Model**: Complete (lines 840-932 in models.py)
  - 19 template types (renewal, invoice, seasonal, support, etc.)
  - Multi-language support (en/th)
  - Subject, body_text, body_html fields
  - Variable support via Django template engine
  - Active/inactive status

- **Admin Interface**: Fully functional
  - CRUD operations working
  - Preview, send test email, duplicate actions
  - Variable guide in admin

- **Email Service Integration**: Production-tested
  - `email_service.send_template_email()` working
  - Templates actively used for Quote/Contract/Invoice sending
  - Tested successfully Oct 12, 2025

### Backend ❌ MISSING
- **NO REST API**: No serializer, viewset, or endpoints
  - Cannot fetch templates via `/api/v1/email-templates/`
  - Frontend has no way to access templates

### Frontend ❌ MISSING
- Placeholder page only: "This page is coming soon!"
- No TypeScript interface for EmailTemplate
- No API methods
- No UI components

## Value Proposition

### What Users Can Do With Templates

**1. Automated Business Processes**
- Renewal reminders (30/14/7 days before expiry) → Auto-send
- Invoice notifications → Auto-send when invoice created
- Payment reminders → Auto-send for overdue invoices
- Seasonal campaigns → Pre-written content ready to send

**2. Reusable Professional Content**
- Write once, use many times
- Consistent branding and messaging
- No typos or forgotten details
- Legal/compliance text always correct

**3. Multi-Language Support**
- Same template in English and Thai
- System picks language based on customer preference
- Consistent message across languages

**4. Smart Variables**
Templates auto-fill with customer data:
```
Subject: Contract Renewal - {{company_name}}

Dear {{contact_name}},

Your contract #{{contract_number}} expires in {{days_until_expiry}} days.
Monthly value: {{monthly_value}}
```

**5. Campaign Integration**
- Select template when creating campaign
- Template pre-fills subject/body
- Can customize before sending
- Faster campaign creation

### Real-World Workflow

**Without Templates (Manual)**:
1. Contract expires → Manual alert
2. Open email client
3. Write email manually with customer details
4. Send individually
5. Repeat for 50 customers 😰

**With Templates (Automated)**:
1. System detects contract expiring
2. Fetches "renewal_30_days" template
3. Auto-fills {{company_name}}, {{contact_name}}, {{end_date}}
4. Sends automatically
5. All 50 customers get perfect emails ✅

## Implementation Plan

### User Preferences (From Q&A)
- **Scope**: Full implementation (all phases)
- **UI Pattern**: Modal dialog (like CompanyForm.tsx)
- **Preview**: Yes - include in first version
- **Timeline**: Normal (1-2 weeks)

### Phase 1: Core CRUD + Preview (MVP) - 10-12 hours

#### Backend Tasks (Use django-admin-expert)
1. **Create EmailTemplateSerializer** (2 hours)
   - Location: `crm_app/serializers.py`
   - Fields: id, name, template_type, language, subject, body_text, body_html, is_active, department, notes, timestamps
   - Computed field: `variable_list` (returns available variables for this template type)
   - Validation: Unique name, unique template_type per language

2. **Create EmailTemplateViewSet** (3 hours)
   - Location: `crm_app/views.py`
   - Inherits: `BaseModelViewSet`
   - Standard CRUD operations (list, retrieve, create, update, destroy)
   - Custom actions:
     - `@action(detail=True, methods=['get']) def preview()` - Renders with sample data
     - `@action(detail=True, methods=['post']) def send_test()` - Sends test email
     - `@action(detail=False, methods=['get']) def variables()` - Returns variables by type
   - Permissions: IsAuthenticated
   - Ordering: name, template_type, language

3. **Register Router** (15 min)
   - Location: `crm_app/urls.py`
   - Add: `router.register(r'email-templates', views.EmailTemplateViewSet, basename='emailtemplate')`
   - Creates endpoint: `/api/v1/email-templates/`

4. **Test API** (30 min)
   - GET /api/v1/email-templates/ (list with pagination)
   - POST /api/v1/email-templates/ (create)
   - GET /api/v1/email-templates/{id}/ (retrieve)
   - PUT /api/v1/email-templates/{id}/ (update)
   - DELETE /api/v1/email-templates/{id}/ (delete)
   - GET /api/v1/email-templates/{id}/preview/ (preview)
   - GET /api/v1/email-templates/variables/?template_type=renewal_30_days

#### Frontend Tasks (Use react-dashboard-builder)
1. **Add TypeScript Interface** (30 min)
   - Location: `bmasia-crm-frontend/src/types/index.ts`
   ```typescript
   export interface EmailTemplate {
     id: string;
     name: string;
     template_type: string;
     template_type_display?: string;
     language: 'en' | 'th';
     subject: string;
     body_text: string;
     body_html?: string;
     is_active: boolean;
     department?: string;
     notes?: string;
     created_at: string;
     updated_at: string;
     variable_list?: string[];
   }
   ```

2. **Add API Methods** (1 hour)
   - Location: `bmasia-crm-frontend/src/services/api.ts`
   ```typescript
   async getEmailTemplates(params?: any): Promise<ApiResponse<EmailTemplate>>
   async getEmailTemplate(id: string): Promise<EmailTemplate>
   async createEmailTemplate(data: Partial<EmailTemplate>): Promise<EmailTemplate>
   async updateEmailTemplate(id: string, data: Partial<EmailTemplate>): Promise<EmailTemplate>
   async deleteEmailTemplate(id: string): Promise<void>
   async previewEmailTemplate(id: string, contactId?: string): Promise<any>
   async getTemplateVariables(templateType: string): Promise<string[]>
   ```

3. **Create EmailTemplates List Page** (3 hours)
   - Location: `bmasia-crm-frontend/src/pages/EmailTemplates.tsx`
   - Copy pattern from `Campaigns.tsx`
   - Table columns: Name, Type, Language, Department, Active status
   - Search bar (name, subject)
   - Filters: template_type, language, department, is_active
   - Row actions: Edit (opens modal), Duplicate, Delete
   - "New Template" button → opens EmailTemplateForm modal
   - Pagination

4. **Create EmailTemplateForm Modal** (2 hours)
   - Location: `bmasia-crm-frontend/src/components/EmailTemplateForm.tsx`
   - Material-UI Dialog component
   - Form fields:
     - Name (required, text)
     - Template Type (required, select with 19 options)
     - Language (required, select en/th)
     - Department (optional, select)
     - Subject (required, text)
     - Body Text (required, multiline 10 rows)
     - Advanced section (collapsible):
       - Body HTML (optional, multiline 10 rows)
       - Notes (optional, multiline 3 rows)
     - Active toggle (default true)
   - Save/Cancel buttons
   - Form validation

5. **Create Preview Dialog** (1.5 hours)
   - Location: `bmasia-crm-frontend/src/components/EmailTemplatePreview.tsx`
   - Material-UI Dialog component
   - Renders HTML in iframe for safety
   - Shows subject and body
   - Toggle HTML/Text view
   - "Send Test Email" button
   - Close button

6. **Create Variable Guide Component** (1 hour)
   - Location: `bmasia-crm-frontend/src/components/TemplateVariableGuide.tsx`
   - Displays available variables for selected template_type
   - Click to copy variable to clipboard
   - Tooltip explaining each variable
   - Collapsible sidebar or section

7. **Update App Routing** (15 min)
   - Location: `bmasia-crm-frontend/src/App.tsx`
   - Replace: `<Route path="/email-templates" element={<PlaceholderPage title="Email Templates" />} />`
   - With: `<Route path="/email-templates" element={<EmailTemplates />} />`

### Phase 2: Integration + Enhanced UX - 4-6 hours

#### Backend Tasks (Use django-admin-expert)
1. **Add Usage Analytics** (2 hours)
   - Add `campaigns_using` computed field to serializer
   - Shows count of campaigns using this template
   - Add filter: `has_campaigns` (true/false)

#### Frontend Tasks (Use react-dashboard-builder)
1. **Campaign Template Integration** (2 hours)
   - Update `CampaignCreate.tsx` to load template options
   - Add template selector dropdown
   - When template selected, auto-fill subject/body
   - User can still customize after selection

2. **Bulk Actions** (1 hour)
   - Checkbox selection on EmailTemplates list
   - Bulk activate/deactivate
   - Bulk delete with confirmation

3. **Template Duplication** (1 hour)
   - "Duplicate" button in row actions
   - Opens form with template data + "(Copy)" suffix
   - User can modify before saving

### Phase 3: Advanced Features - 4-6 hours

#### Backend Tasks (Use django-admin-expert)
1. **Version History** (3 hours)
   - Create EmailTemplateVersion model
   - Save snapshot on each update
   - API endpoint to list versions
   - API endpoint to restore version

#### Frontend Tasks (Use ui-ux-designer)
1. **Rich Text Editor** (2 hours)
   - Integrate TinyMCE or React-Quill
   - Use for body_html field only
   - Keep body_text as plain textarea
   - Toggle between editors

2. **Version History UI** (1 hour)
   - Timeline view of template changes
   - Diff view between versions
   - Restore button

## Template Types Available (19 Types)

### Sales (4)
- `renewal_30_days` - 30 days before contract expires
- `renewal_14_days` - 14 days before contract expires
- `renewal_7_days` - 7 days before contract expires
- `renewal_urgent` - Urgent renewal (< 7 days)

### Finance (4)
- `invoice_new` - New invoice notification
- `payment_reminder_7_days` - 7 days after due date
- `payment_reminder_14_days` - 14 days after due date
- `payment_overdue` - Overdue payment alert

### Music Design (5)
- `quarterly_checkin` - Quarterly customer check-in
- `seasonal_christmas` - Christmas season campaign
- `seasonal_newyear` - New Year campaign
- `seasonal_songkran` - Songkran (Thai New Year) campaign
- `seasonal_ramadan` - Ramadan season campaign

### Tech Support (2)
- `zone_offline_48h` - Zone offline for 48 hours
- `zone_offline_7d` - Zone offline for 7 days

### General (4)
- `welcome` - Welcome new customer
- `contract_signed` - Contract signing confirmation
- `quote_send` - Send quote to customer
- `contract_send` - Send contract to customer
- `invoice_send` - Send invoice to customer
- `renewal_manual` - Manual renewal email

## Template Variables

Variables available per template type:

### Common Variables (All Templates)
- `{{company_name}}` - Customer company name
- `{{contact_name}}` - Contact person name
- `{{current_year}}` - Current year (for footer)
- `{{unsubscribe_url}}` - Unsubscribe link

### Renewal Templates
- `{{contract_number}}` - Contract ID
- `{{end_date}}` - Contract expiry date
- `{{days_until_expiry}}` - Days remaining
- `{{monthly_value}}` - Monthly contract value

### Invoice Templates
- `{{invoice_number}}` - Invoice ID
- `{{due_date}}` - Payment due date
- `{{total_amount}}` - Total invoice amount
- `{{payment_url}}` - Payment link

### Zone Offline Templates
- `{{zone_name}}` - Music zone name
- `{{offline_duration}}` - How long offline
- `{{support_email}}` - Tech support email

## Technical Architecture

### Template Rendering Flow
1. User creates template with variables: `Dear {{contact_name}}`
2. System event triggers email (e.g., contract expiring)
3. Backend fetches template: `EmailTemplate.objects.get(template_type='renewal_30_days', language='en')`
4. Backend prepares context: `{'contact_name': 'John Doe', 'company_name': 'ACME Corp', ...}`
5. Backend renders: `template.render(context)` → `Dear John Doe`
6. Backend sends via `email_service.send_email()`
7. Backend logs in EmailLog model

### API Endpoints Created
- `GET /api/v1/email-templates/` - List all templates
- `POST /api/v1/email-templates/` - Create template
- `GET /api/v1/email-templates/{id}/` - Get template
- `PUT /api/v1/email-templates/{id}/` - Update template
- `DELETE /api/v1/email-templates/{id}/` - Delete template
- `GET /api/v1/email-templates/{id}/preview/` - Preview with sample data
- `POST /api/v1/email-templates/{id}/send_test/` - Send test email
- `GET /api/v1/email-templates/variables/` - Get variables for template type

### Frontend Components Created
- `EmailTemplates.tsx` - Main list page
- `EmailTemplateForm.tsx` - Create/edit modal dialog
- `EmailTemplatePreview.tsx` - Preview dialog
- `TemplateVariableGuide.tsx` - Variable reference sidebar

## Sub-Agent Usage Plan

### Backend Implementation
- **django-admin-expert**: Create serializer, viewset, routing, tests
- **database-optimizer**: If performance issues with template queries

### Frontend Implementation
- **react-dashboard-builder**: Build list page, form, API integration
- **ui-ux-designer**: Design preview dialog, variable guide, rich text editor
- **frontend-auth-specialist**: If permissions/roles needed (future)

## Testing Checklist

### Backend Testing
- [ ] Can list templates via API
- [ ] Can create template via API
- [ ] Can update template via API
- [ ] Can delete template via API
- [ ] Preview renders correctly with sample data
- [ ] Variables endpoint returns correct variables
- [ ] Template type uniqueness enforced
- [ ] Multi-language works (EN/TH)

### Frontend Testing
- [ ] Email Templates page loads
- [ ] Can see list of templates
- [ ] Can search templates
- [ ] Can filter by type/language/department
- [ ] Can create new template
- [ ] Can edit existing template
- [ ] Can delete template with confirmation
- [ ] Preview shows rendered template
- [ ] Variable guide shows correct variables
- [ ] Campaign form loads template options
- [ ] Selecting template auto-fills campaign

### Integration Testing
- [ ] Create template in UI → Visible in admin
- [ ] Template used in campaign → Sends correctly
- [ ] Automated renewal email uses template
- [ ] Multi-language template selection works

## Deployment Strategy

### Backend Deployment
1. Commit serializer, viewset, routing changes
2. Push to GitHub
3. Render auto-deploys backend
4. Run migrations if any (unlikely for this feature)
5. Verify API endpoints work

### Frontend Deployment
1. Commit TypeScript types, API methods, components
2. Push to GitHub
3. Render auto-deploys frontend
4. Verify UI loads and works

### Rollback Plan
- If issues: Revert commits, redeploy
- Backend changes are additive (no breaking changes)
- Frontend changes replace placeholder (low risk)

## Success Criteria

### MVP (Phase 1)
- ✅ Email Templates page shows list of templates
- ✅ Can create new template with all fields
- ✅ Can edit existing template
- ✅ Can delete template
- ✅ Can preview template with sample data
- ✅ Variable guide helps users understand variables

### Full Implementation (Phase 1 + 2 + 3)
- ✅ Campaign creation can select template
- ✅ Bulk actions work
- ✅ Template duplication works
- ✅ Rich text editor for HTML
- ✅ Version history tracking

## Timeline Estimate

| Phase | Tasks | Hours | Sub-Agent |
|-------|-------|-------|-----------|
| Phase 1 Backend | Serializer, ViewSet, URLs | 5-6 | django-admin-expert |
| Phase 1 Frontend | Types, API, UI Components | 5-6 | react-dashboard-builder |
| Phase 2 Backend | Usage analytics | 2 | django-admin-expert |
| Phase 2 Frontend | Integration, bulk actions | 2-4 | react-dashboard-builder |
| Phase 3 Backend | Version history | 3 | django-admin-expert |
| Phase 3 Frontend | Rich editor, history UI | 3 | ui-ux-designer |
| **TOTAL** | **All phases** | **20-25 hours** | - |

**Delivery**: 1-2 weeks (Normal priority, proper testing)

## Risk Assessment

### Low Risk ✅
- Backend API: Pattern proven in 10+ other ViewSets
- Frontend List Page: Direct copy of Campaigns.tsx
- Database: Model already exists and production-tested
- Email sending: Already working with templates

### Medium Risk ⚠️
- Preview functionality: Need to handle HTML safely (use iframe)
- Variable validation: Need to warn about typos in variable names
- Template uniqueness: Enforce at API level

### High Risk ❌
- None identified

## Notes for Implementation

1. **Use Sub-Agents**: django-admin-expert for backend, react-dashboard-builder for frontend
2. **Copy Patterns**: Use Campaigns.tsx as reference for UI patterns
3. **Test Incrementally**: Test backend API before building frontend
4. **Document Variables**: Create comprehensive variable guide
5. **Security**: Sanitize HTML in templates (Django template engine handles this)
6. **Performance**: Templates are small, no pagination issues expected

## Current Production Data

According to EMAIL_SYSTEM_STATUS.md:
- Default templates already exist (created via management command)
- Templates actively used for Quote/Contract/Invoice sending
- Production-tested on Oct 12, 2025

**Action**: Before building UI, check what templates exist:
```bash
python manage.py shell
>>> from crm_app.models import EmailTemplate
>>> EmailTemplate.objects.all().values('id', 'name', 'template_type')
```

## Post-Implementation

### User Training Needed
- How to create templates
- How to use variables
- How to preview before using
- How to select template in campaigns

### Future Enhancements (Backlog)
- AI-powered template suggestions
- A/B testing for templates
- Template marketplace
- Advanced analytics (open rates by template)
- Template scheduling (activate/deactivate by date)

---

**Status**: Ready for implementation after auto-compact
**Next Step**: Use sub-agents to build Phase 1 MVP
**Expected Completion**: 1-2 weeks
