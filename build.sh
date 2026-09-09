#!/usr/bin/env bash
# Exit on error for critical steps
set -e

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Note: Migrations are now handled in start.sh where DATABASE_URL is available

# Historical bootstrap operations can rewrite CRM data. Keep them available for
# an explicitly authorized maintenance run, but never execute them as a side
# effect of an ordinary application build.
if [ "${RUN_DEPLOY_BOOTSTRAP:-False}" = "True" ]; then
python manage.py shell << EOF 2>/dev/null || echo "Skipping superuser creation (tables may not exist yet)"
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@bmasiamusic.com', 'bmasia123')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Create email templates (may fail if tables don't exist)
python manage.py create_email_templates 2>/dev/null || echo "Skipping email template creation (tables may not exist yet)"

# Set seasonal trigger dates for variable holidays (idempotent)
python manage.py set_seasonal_dates 2>/dev/null || echo "Skipping seasonal date setup (tables may not exist yet)"
else
    echo "Skipping deploy-time CRM bootstrap (RUN_DEPLOY_BOOTSTRAP is not True)"
fi

echo "Build completed!"
