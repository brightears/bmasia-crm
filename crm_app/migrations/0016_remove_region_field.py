# Remove the region field that's causing issues

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0015_fix_region_field'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE crm_app_company DROP COLUMN IF EXISTS region;",
            reverse_sql="ALTER TABLE crm_app_company ADD COLUMN region VARCHAR(100);"
        ),
    ]