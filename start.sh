#!/usr/bin/env bash
set -e

echo "Starting BMAsia CRM..."

# Try to run reset_db.py if RESET_DB is set
if [ "$RESET_DB" = "true" ]; then
    echo "RESET_DB is set, resetting database..."
    python reset_db.py <<< "yes"
fi

# Create campaign tables directly via SQL (bypasses migration issues)
echo "Creating campaign tables via direct SQL..."
python create_campaign_table_direct.py || echo "Direct table creation failed, continuing anyway..."

# Run database migrations first
echo "Running database migrations..."
python manage.py migrate --noinput

# Apply migration 0025 manually if needed (fixes production issue)
echo "Applying migration 0025 if needed..."
python manage.py apply_migration_0025 || echo "Migration 0025 command not found or already applied"

# Only run force_add_billing_entity if tables already exist (migration 0024 specific fix)
# This script is only needed for existing databases, not fresh ones
echo "Checking if billing_entity column fix is needed..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bmasia_crm.settings')
import django
django.setup()
from crm_app.models import Company
try:
    # Try to check if billing_entity exists
    Company.objects.filter(billing_entity__isnull=True).exists()
    print('billing_entity column exists, skipping fix')
except Exception as e:
    if 'billing_entity' in str(e):
        print('billing_entity column missing, running fix...')
        import subprocess
        subprocess.run(['python', 'force_add_billing_entity.py'])
    else:
        print(f'Unexpected error: {e}')
" || echo "Column check skipped (likely fresh database)"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the web server
echo "Starting Gunicorn..."
exec gunicorn bmasia_crm.wsgi:application --bind 0.0.0.0:$PORT