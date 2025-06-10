# BMAsia CRM System

A comprehensive Customer Relationship Management system built for BMAsia with Django REST API backend and React TypeScript frontend.

## Project Structure

```
├── bmasia_crm/           # Django project settings
├── crm_app/              # Main Django app with models, views, serializers
├── bmasia-crm-frontend/  # React TypeScript frontend
├── requirements.txt      # Python dependencies
├── manage.py            # Django management script
└── db.sqlite3          # SQLite database (development)
```

## Features

- **Role-based Access Control**: Sales, Finance, Tech Support, Music Design, Admin roles
- **Company Management**: Complete company profiles with contacts and notes
- **Sales Funnel**: Lead tracking through opportunity stages
- **Task Management**: Inter-department task assignment and tracking
- **Contract & Invoice Management**: Finance workflow automation
- **Dashboard Analytics**: Role-specific dashboards and reporting
- **Audit Logging**: Complete activity tracking

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
- `POST /api/v1/auth/login/` - User login
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

## Development

### Backend Development
- Models are defined in `crm_app/models.py`
- API views in `crm_app/views.py`
- Serializers in `crm_app/serializers.py`
- Permissions in `crm_app/permissions.py`

### Frontend Development
- React components in `bmasia-crm-frontend/src/components/`
- Pages in `bmasia-crm-frontend/src/pages/`
- API service layer in `bmasia-crm-frontend/src/services/`
- TypeScript types in `bmasia-crm-frontend/src/types/`

### Testing
```bash
# Backend tests
python manage.py test

# Frontend tests
cd bmasia-crm-frontend
npm test
```

## Production Deployment

### Backend
1. Set up PostgreSQL database
2. Configure environment variables
3. Use Gunicorn/Uvicorn with NGINX
4. Set up Redis for Celery (background tasks)

### Frontend
1. Build production assets: `npm run build`
2. Serve static files or deploy to CDN
3. Configure CORS settings for production domain

## Environment Variables

### Backend (.env)
```
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=postgresql://user:pass@localhost/bmasia_crm
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
REDIS_URL=redis://localhost:6379/0
```

### Frontend (.env)
```
REACT_APP_API_URL=https://api.your-domain.com
```

## Support

For development questions or issues, refer to the initial design document (`BMAsia_CRM_initial_design.md`) or contact the development team.