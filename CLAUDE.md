# Claude Code Instructions for BMAsia CRM

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

## Key Project Files and Locations

### Backend (Django)
- **Models**: `crm_app/models.py` (16+ entities including Company, Contact, Contract, Zone)
- **Admin**: `crm_app/admin.py` (comprehensive admin interface)
- **Services**: `crm_app/services/` (business logic, API integrations)
- **Email System**: `crm_app/services/email_service.py`
- **API Integration**: `crm_app/services/soundtrack_api.py`
- **Settings**: `bmasia_crm/settings.py`

### Frontend (React)
- **Main App**: `bmasia-crm-frontend/src/App.tsx`
- **Components**: `bmasia-crm-frontend/src/components/`
- **Services**: `bmasia-crm-frontend/src/services/`

### Database
- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Render
- **Migrations**: `crm_app/migrations/`

## Environment Variables (.env)

Key environment variables:
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (True for development)
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`: Email configuration
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
| Build analytics charts | react-dashboard-builder |

## Best Practices

1. **Always use the appropriate sub-agent** for specialized tasks
2. **Run tests** after making changes: `pytest`
3. **Check linting** before committing: `flake8` (Python), `npm run lint` (React)
4. **Update migrations** after model changes: `python manage.py makemigrations`
5. **Document API changes** in the relevant documentation files
6. **Test locally** before pushing to production
7. **Use environment variables** for sensitive data, never hardcode

## Current Status (September 2025)

- ✅ Core CRM functionality implemented
- ✅ Soundtrack API integration working
- ✅ Email automation system complete
- ✅ PostgreSQL migration completed
- 🚧 React frontend needs expansion (currently using Django admin)
- 🚧 Test coverage needs improvement
- 📋 Authentication currently disabled for development

## Support and Documentation

- **Initial Design**: `BMAsia_CRM_initial_design.md`
- **Email System**: `EMAIL_SYSTEM_STATUS.md`
- **Database Setup**: `DATABASE_SETUP.md`
- **Soundtrack API**: `SOUNDTRACK_API_SETUP.md`
- **Zone Tracking**: `ZONE_TRACKING_GUIDE.md`

## Render Platform Access

The project includes Render MCP integration for managing the production infrastructure:
- Check service status
- View logs and metrics
- Manage database
- Deploy updates

Use `RENDER_API_KEY` from .env for API access.

---

**Remember**: When in doubt about which agent to use, refer to the "Available Sub-Agents and Their Use Cases" section above. Using the right agent ensures the best quality code and fastest development.