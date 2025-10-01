# Enable PostgreSQL pg_trgm extension for trigram text search
# This must run BEFORE 0020_optimize_database_performance

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0019_update_service_types'),
    ]

    operations = [
        # Enable pg_trgm extension for trigram fuzzy text search
        # This is required for GIN indexes with gin_trgm_ops in migration 0020
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;",
            state_operations=[]
        ),
    ]
