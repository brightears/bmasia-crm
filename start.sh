#!/usr/bin/env bash

echo "Starting BMAsia CRM..."

# Try to run reset_db.py if RESET_DB is set
if [ "$RESET_DB" = "true" ]; then
    echo "RESET_DB is set, resetting database..."
    python reset_db.py <<< "yes"
fi

# Start the web server regardless of migration status
echo "Starting Gunicorn..."
exec gunicorn bmasia_crm.wsgi:application --bind 0.0.0.0:$PORT