#!/usr/bin/env bash
# Exit on error - migrations are critical
set -e

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations - MUST succeed or deployment fails
echo "Running migrations..."
python manage.py migrate --noinput

# Verify critical migration ran
echo "Verifying billing_entity column exists..."
python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='crm_app_company' AND column_name='billing_entity'\")
result = cursor.fetchone()
if not result:
    print('ERROR: billing_entity column not found!')
    exit(1)
print('✓ billing_entity column verified')
"

# Create superuser if it doesn't exist (may fail if tables don't exist)
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

echo "Build completed!"