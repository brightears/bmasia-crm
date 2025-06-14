# Database Setup for Production

## Current Issue
When deploying to Render, all data is lost because SQLite database is stored in the container, which gets replaced on each deployment.

## Solution: PostgreSQL Database

### Option 1: Render PostgreSQL (Recommended)
1. Go to your Render dashboard
2. Click "New +" → "PostgreSQL"
3. Choose:
   - Name: `bmasia-crm-db`
   - Database: Leave default
   - User: Leave default  
   - Region: Same as your web service (Singapore)
   - Plan: Free (or Starter for $7/month for better performance)
4. Click "Create Database"
5. Wait for database to be created
6. Copy the "Internal Database URL" (starts with `postgres://`)
7. In your web service settings, add environment variable:
   - Key: `DATABASE_URL`
   - Value: [paste the Internal Database URL]
8. Deploy your service

### Option 2: External PostgreSQL (Free alternatives)
- **Supabase**: https://supabase.com (Free tier: 500MB)
- **Neon**: https://neon.tech (Free tier: 3GB)
- **Aiven**: https://aiven.io (Free trial: 1 month)

Steps:
1. Sign up for service
2. Create a new PostgreSQL database
3. Copy the connection string
4. Add to Render environment variables as `DATABASE_URL`

### Migrating Existing Data (if needed)

1. Export current SQLite data:
```bash
python manage.py dumpdata > backup.json
```

2. After connecting PostgreSQL:
```bash
python manage.py migrate
python manage.py loaddata backup.json
```

### Important Notes
- First deployment with PostgreSQL will run migrations automatically
- All future deployments will preserve your data
- Make regular backups of production data
- PostgreSQL is more suitable for production (handles concurrent users better)

### Environment Variables on Render
Make sure you have these set:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Django secret key
- `EMAIL_HOST_USER` - Gmail address
- `EMAIL_HOST_PASSWORD` - Gmail app password
- `SOUNDTRACK_API_KEY` - If using Soundtrack integration