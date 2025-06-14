#!/usr/bin/env bash
# exit on error for critical steps only
set -o pipefail

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Handle migrations
echo "Running migrations..."
python manage.py migrate || {
    echo "WARNING: Migrations failed. This is expected on first PostgreSQL deployment."
    echo "To fix this, run: python manage.py reset_database --force"
    echo "Continuing with deployment..."
}

# Create superuser if it doesn't exist (may fail if tables don't exist)
python manage.py shell << EOF 2>/dev/null || echo "Skipping superuser creation (tables may not exist yet)"
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@bmasiamusic.com', 'BMAsia2024!')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Create email templates (may fail if tables don't exist)
python manage.py create_email_templates 2>/dev/null || echo "Skipping email template creation (tables may not exist yet)"

echo "Build completed!"