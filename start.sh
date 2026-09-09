#!/usr/bin/env bash
# Temporarily disable set -e to see what's failing
# set -e

echo "======================================================"
echo "Starting BMAsia CRM..."
echo "Python version: $(python --version)"
echo "Date: $(date)"
echo "======================================================"

# SECURITY 2026-07-02: removed the boot-time RESET_DB branch — a single env var could wipe the
# production database on deploy, with the confirmation auto-piped. DB resets, if ever needed, run
# manually via the reset_db management command with explicit interactive confirmation.

# Legacy repair hooks alter database schema and, through column defaults, can
# affect CRM records. They are reserved for an explicitly authorized one-shot
# maintenance run. Ordinary deploys are migration-free and fail closed when
# the production database is not already current.
if [ "${RUN_LEGACY_DEPLOY_REPAIRS:-False}" = "True" ]; then
    echo "Running explicitly enabled legacy deployment repairs..."
    python create_campaign_table_direct.py || echo "Direct table creation failed, continuing anyway..."
    python fix_smtp_columns.py || echo "SMTP column fix failed, continuing anyway..."
    python fix_zone_migration.py || echo "Zone migration fix failed, continuing anyway..."
    python manage.py migrate --noinput
    python manage.py apply_migration_0025 || echo "Migration 0025 command not found or already applied"
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
else
    echo "Checking that no database migrations are pending..."
    python manage.py migrate --check || {
        echo "Deployment stopped: pending migrations require an explicit maintenance run."
        python manage.py showmigrations crm_app 2>&1 | tail -20
        exit 1
    }
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "collectstatic failed, continuing..."

# Re-enable strict mode for the actual server start
set -e

# Start the web server
echo "======================================================"
echo "Starting Gunicorn on port $PORT..."
echo "======================================================"
exec gunicorn bmasia_crm.wsgi:application --bind 0.0.0.0:$PORT
