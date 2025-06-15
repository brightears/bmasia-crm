# Fix all orphaned columns from faked migration 0007

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0016_remove_region_field'),
    ]

    operations = [
        # Make company_size nullable first
        migrations.RunSQL(
            "ALTER TABLE crm_app_company ALTER COLUMN company_size DROP NOT NULL;",
            reverse_sql="ALTER TABLE crm_app_company ALTER COLUMN company_size SET NOT NULL;",
            state_operations=[]
        ),
        # Drop company_size column
        migrations.RunSQL(
            "ALTER TABLE crm_app_company DROP COLUMN IF EXISTS company_size;",
            reverse_sql="ALTER TABLE crm_app_company ADD COLUMN company_size VARCHAR(50);",
            state_operations=[]
        ),
        # Drop is_corporate_account column if it exists
        migrations.RunSQL(
            "ALTER TABLE crm_app_company DROP COLUMN IF EXISTS is_corporate_account;",
            reverse_sql="ALTER TABLE crm_app_company ADD COLUMN is_corporate_account BOOLEAN DEFAULT FALSE;",
            state_operations=[]
        ),
        # Make sure region is really gone
        migrations.RunSQL(
            "ALTER TABLE crm_app_company DROP COLUMN IF EXISTS region;",
            reverse_sql="ALTER TABLE crm_app_company ADD COLUMN region VARCHAR(100);",
            state_operations=[]
        ),
    ]