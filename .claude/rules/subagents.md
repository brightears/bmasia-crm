# Sub-Agent Usage Guide for BMAsia CRM

**ALWAYS** use the appropriate specialized sub-agent for the task at hand.

## Available Sub-Agents

### 1. django-admin-expert
Use when:
- Creating/modifying Django admin interfaces
- Adding bulk operations or custom admin actions
- Implementing CSV/Excel export functionality
- Optimizing admin querysets (select_related, prefetch_related)
- Files: `crm_app/admin.py`, `crm_app/admin_views.py`

### 2. django-testing-agent
Use when:
- Writing pytest tests for models, views, or services
- Creating test fixtures with factory_boy
- Testing API endpoints
- Mocking external services
- Files in: `crm_app/tests/`

### 3. react-dashboard-builder
Use when:
- Building React components for the dashboard
- Creating data visualizations with Recharts
- Implementing authentication flows
- Managing state with Context API
- Integrating with Django REST APIs
- Files in: `bmasia-crm-frontend/`

### 4. api-integration-specialist
Use when:
- Integrating with Soundtrack Your Brand API
- Adding new external API integrations
- Implementing retry logic and error handling
- Working with GraphQL or REST APIs
- Files: `crm_app/services/soundtrack_api.py`

### 5. database-optimizer
Use when:
- Creating database indexes
- Optimizing Django ORM queries
- Writing complex database migrations
- Implementing caching strategies

### 6. email-automation-specialist
Use when:
- Creating/modifying email templates
- Setting up automated email campaigns
- Implementing email scheduling
- Files: `crm_app/services/email_service.py`

### 7. frontend-auth-specialist
Use when:
- Implementing JWT token management
- Creating login/logout flows
- Setting up protected routes in React
- Files: `AuthContext.tsx`

### 8. ui-ux-designer
Use when:
- Creating consistent design systems
- Implementing responsive layouts
- Adding loading states and error handling
- Implementing accessibility features

### 9. data-visualization-expert
Use when:
- Building interactive dashboards with Recharts
- Creating sales pipeline visualizations
- Designing KPI cards and metrics displays

## Quick Reference Table

| Task | Agent |
|------|-------|
| Add bulk email to admin | django-admin-expert |
| Write tests | django-testing-agent |
| Create dashboard | react-dashboard-builder |
| Fix Soundtrack API | api-integration-specialist |
| Optimize queries | database-optimizer |
| Email templates | email-automation-specialist |
| Authentication | frontend-auth-specialist |
| UI components | ui-ux-designer |
| Charts/KPIs | data-visualization-expert |
