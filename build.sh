#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Try to run migrations
echo "Running migrations..."
python manage.py migrate || {
    echo "Initial migration failed, trying with reset..."
    python reset_migrations.py
}

# Create superuser if it doesn't exist
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@bmasiamusic.com', 'BMAsia2024!')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Create email templates
python manage.py create_email_templates || echo "Email templates already exist"