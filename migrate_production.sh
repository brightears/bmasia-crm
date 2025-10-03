#!/bin/bash
# Simple script to run migrations on production
# Can be executed via Render shell

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Migrations complete!"