# Manual migration to ensure campaign table exists before 0027
from django.db import migrations, connection
import uuid


def create_campaign_table_if_missing(apps, schema_editor):
    """
    Create the campaign table if it doesn't exist.
    This runs before migration 0027 which tries to alter it.
    """
    with connection.cursor() as cursor:
        # Check if any campaign table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('crm_app_email_campaign', 'crm_app_emailcampaign')
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("✓ Campaign table already exists")
            return
        
        print("Creating crm_app_emailcampaign table (will be renamed by migration 0027)...")
        
        # Create table with old name - migration 0027 will rename and add fields
        cursor.execute("""
            CREATE TABLE crm_app_emailcampaign (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                name VARCHAR(100) NOT NULL,
                campaign_type VARCHAR(20) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                start_date DATE NULL,
                end_date DATE NULL,
                emails_sent INTEGER DEFAULT 0 NOT NULL,
                last_email_sent TIMESTAMP WITH TIME ZONE NULL,
                stop_on_reply BOOLEAN DEFAULT TRUE NOT NULL,
                replied BOOLEAN DEFAULT FALSE NOT NULL,
                company_id UUID NULL,
                contract_id UUID NULL,
                CONSTRAINT crm_app_emailcampaign_company_id_fkey
                    FOREIGN KEY (company_id)
                    REFERENCES crm_app_company(id)
                    ON DELETE CASCADE,
                CONSTRAINT crm_app_emailcampaign_contract_id_fkey
                    FOREIGN KEY (contract_id)
                    REFERENCES crm_app_contract(id)
                    ON DELETE SET NULL
            )
        """)
        
        # Create initial index (will be modified by 0027)
        cursor.execute("""
            CREATE INDEX crm_app_ema_company_c5ff78_idx
            ON crm_app_emailcampaign (company_id)
        """)
        
        print("✓ Base campaign table created")


class Migration(migrations.Migration):
    
    dependencies = [
        ('crm_app', '0026_merge_20251114_1416'),
    ]
    
    operations = [
        migrations.RunPython(create_campaign_table_if_missing, reverse_code=migrations.RunPython.noop),
    ]
