# BMAsia CRM System

A comprehensive Customer Relationship Management system built for BMAsia with Django REST API backend and React TypeScript frontend, featuring Soundtrack Your Brand and Beat Breeze integrations.

## 🎉 Current Status (v1.0-soundtrack-working)

### ✅ Working Features
- **Soundtrack API Integration**: Full GraphQL integration with account-specific queries
- **Zone Discovery**: Automatically fetches zones for specific account IDs
- **Real-time Status**: Online/offline/no_device status tracking
- **Admin Interface**: Easy zone management and bulk synchronization
- **Debug Endpoint**: `/debug-soundtrack/` for API troubleshooting
- **Authentication**: Temporarily disabled for development phase

### 🔧 Live Deployment
- **Main Site**: https://bmasia-crm.onrender.com
- **Debug URL**: https://bmasia-crm.onrender.com/debug-soundtrack/?test=1&account_id=YOUR_ACCOUNT_ID
- **Admin Access**: No login required during development

### 📍 Restore Point
To restore to this working version:
```bash
git checkout v1.0-soundtrack-working
```

## Project Structure

```
├── bmasia_crm/           # Django project settings
├── crm_app/              # Main Django app with models, views, serializers
│   ├── services/         # Soundtrack API integration
│   └── middleware.py     # Auto-login middleware for development
├── bmasia-crm-frontend/  # React TypeScript frontend
├── requirements.txt      # Python dependencies
├── render.yaml          # Render deployment configuration
├── manage.py            # Django management script
└── db.sqlite3          # SQLite database (development)
```

## Features

### Core CRM Features
- **Role-based Access Control**: Sales, Finance, Tech Support, Music Design, Admin roles
- **Company Management**: Complete company profiles with contacts and notes
- **Sales Funnel**: Lead tracking through opportunity stages
- **Task Management**: Inter-department task assignment and tracking
- **Contract & Invoice Management**: Finance workflow automation
- **Dashboard Analytics**: Role-specific dashboards and reporting
- **Audit Logging**: Complete activity tracking

### Music Integration Features
- **Soundtrack Your Brand Integration**
  - Account-specific zone management
  - Real-time zone status tracking (online/offline/no_device)
  - Device pairing status
  - Bulk zone synchronization
  - GraphQL API integration
- **Beat Breeze Zone Management**
  - Manual zone tracking
  - Subscription management

## Backend Setup (Django)

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment configuration:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Database setup:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Run development server:**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000/api/v1/`

## Frontend Setup (React)

1. **Navigate to frontend directory:**
   ```bash
   cd bmasia-crm-frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Environment configuration:**
   ```bash
   cp .env.example .env
   # Edit .env if needed (default API URL is http://localhost:8000)
   ```

4. **Start development server:**
   ```bash
   npm start
   ```

The frontend will be available at `http://localhost:3000`

## Soundtrack API Integration

### How to Use
1. **Add Company**: Create a company in the admin interface
2. **Add Account ID**: Enter the Soundtrack account ID (e.g., `QWNjb3VudCwsMXN4N242NTZyeTgv` for Hilton Pattaya)
3. **Sync Zones**: 
   - Select companies from the list
   - Choose "Sync Soundtrack zones" from the actions dropdown
   - Click "Go"
4. **View Status**: Zone status updates automatically in the company detail view

### API Configuration
Environment variables (already configured on Render):
```
SOUNDTRACK_API_TOKEN=YVhId2UyTWJVWEhMRWlycUFPaUl3Y2NtOXNGeUoxR0Q6SVRHazZSWDVYV2FTenhiS1ZwNE1sSmhHUUJEVVRDdDZGU0FwVjZqMXNEQU1EMjRBT2pub2hmZ3NQODRRNndQWg==
SOUNDTRACK_CLIENT_ID=VCZz6nGt0pkQ1fBsHuO8cqgR6Ctefv7f
SOUNDTRACK_CLIENT_SECRET=Ht4g6isxxrNXeYgxNkDyfM0TJe508kqJHPdFVihi9KYbOnmfO8v2PipFUCf69zmc
```

## User Roles & Permissions

### Sales
- Full access to companies, contacts, opportunities, and sales activities
- Can create and manage opportunities
- View-only access to contracts and invoices

### Finance
- Full access to contracts and invoices
- Read access to companies and opportunities
- Can manage billing and payment tracking

### Tech Support / Music Design
- Access to companies, contacts, and tasks
- Can create and manage tasks assigned to their department
- Limited access to other modules

### Admin
- Full access to all modules
- User management capabilities
- Audit log access

## API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - User login (currently bypassed)
- `POST /api/v1/auth/logout/` - User logout

### Core Resources
- `/api/v1/companies/` - Company management
- `/api/v1/contacts/` - Contact management
- `/api/v1/opportunities/` - Sales opportunities
- `/api/v1/tasks/` - Task management
- `/api/v1/contracts/` - Contract management
- `/api/v1/invoices/` - Invoice management
- `/api/v1/notes/` - Notes and communications

### Analytics
- `/api/v1/dashboard/stats/` - Dashboard statistics
- `/api/v1/opportunities/pipeline/` - Sales pipeline data

### Soundtrack Integration
- `/debug-soundtrack/` - Debug endpoint for API testing

## Development

### Backend Development
- Models are defined in `crm_app/models.py`
- API views in `crm_app/views.py`
- Serializers in `crm_app/serializers.py`
- Permissions in `crm_app/permissions.py`
- Soundtrack API in `crm_app/services/soundtrack_api.py`

### Frontend Development
- React components in `bmasia-crm-frontend/src/components/`
- Pages in `bmasia-crm-frontend/src/pages/`
- API service layer in `bmasia-crm-frontend/src/services/`
- TypeScript types in `bmasia-crm-frontend/src/types/`

### Testing
```bash
# Backend tests
python manage.py test

# Soundtrack API test
python manage.py test_soundtrack_api

# Frontend tests
cd bmasia-crm-frontend
npm test
```

## Production Deployment

### Current Deployment (Render)
- Automatic deployments from main branch
- Environment variables configured in render.yaml
- SQLite database for development phase
- Static files served directly

### Future Production Setup
1. Set up PostgreSQL database
2. Configure environment variables
3. Use Gunicorn/Uvicorn with NGINX
4. Set up Redis for Celery (background tasks)
5. Re-enable authentication

## Environment Variables

### Backend (.env)
```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=sqlite:///db.sqlite3
CORS_ALLOWED_ORIGINS=http://localhost:3000
SOUNDTRACK_API_TOKEN=your-token
SOUNDTRACK_CLIENT_ID=your-client-id
SOUNDTRACK_CLIENT_SECRET=your-secret
```

### Frontend (.env)
```
REACT_APP_API_URL=https://bmasia-crm.onrender.com
```

## Support

For development questions or issues, refer to:
- Initial design document (`BMAsia_CRM_initial_design.md`)
- Soundtrack API setup (`SOUNDTRACK_API_SETUP.md`)
- Zone tracking guide (`ZONE_TRACKING_GUIDE.md`)

## Recent Changelog

### v1.1-admin-ui-improvements (2025-06-11)
- ✅ **Fixed horizontal overflow** in admin inline sections
- ✅ **Streamlined Contact fields** - removed phone, contact_type, is_primary, is_active
- ✅ **Simplified Notes display** - removed note_type and priority fields
- ✅ **Optimized Subscription Tiers** - reduced field widths, kept billing_period
- ✅ **Removed duplicate Notes section** from Company admin
- ✅ **Enhanced subscription summary** - removed redundant totals, added dates
- ✅ **Improved mobile responsiveness** of admin interface
- ✅ All changes deployed to https://bmasia-crm.onrender.com

### v1.0-soundtrack-working (2025-06-11)
- ✅ Fixed Soundtrack API GraphQL queries
- ✅ Implemented account-specific zone queries
- ✅ Added proper environment variable configuration
- ✅ Disabled authentication for development phase
- ✅ Added zone status display in admin interface
- ✅ Confirmed working with Hilton Pattaya (4 zones)