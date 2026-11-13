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
# Creates the admin user only if it is missing. The password must come from
# the ADMIN_INITIAL_PASSWORD environment variable; there is no default, and
# without it the command refuses and admin creation is skipped.
python manage.py createadmin --noinput || echo "Skipping admin creation (ADMIN_INITIAL_PASSWORD not set, or tables do not exist yet)"

# Create email templates (may fail if tables don't exist)
python manage.py create_email_templates 2>/dev/null || echo "Skipping email template creation (tables may not exist yet)"

# Set seasonal trigger dates for variable holidays (idempotent)
python manage.py set_seasonal_dates 2>/dev/null || echo "Skipping seasonal date setup (tables may not exist yet)"
else
    echo "Skipping deploy-time CRM bootstrap (RUN_DEPLOY_BOOTSTRAP is not True)"
fi

echo "Build completed!"
