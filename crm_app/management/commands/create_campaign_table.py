"""
Django management command to create campaign table directly.
Usage: python manage.py create_campaign_table
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Create campaign table directly in database'

    def handle(self, *args, **options):
        self.stdout.write("Checking campaign table...")
        
        with connection.cursor() as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'crm_app_email_campaign'
                )
            """)
            exists = cursor.fetchone()[0]
            
            if exists:
                self.stdout.write(self.style.SUCCESS('✓ Table crm_app_email_campaign already exists'))
                
                # Show column count
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = 'crm_app_email_campaign'
                """)
                col_count = cursor.fetchone()[0]
                self.stdout.write(f'  Has {col_count} columns')
                return

            self.stdout.write("Creating crm_app_email_campaign table...")
            
            # Create table
            cursor.execute("""
                CREATE TABLE crm_app_email_campaign (
                    id UUID PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    name VARCHAR(100) NOT NULL,
                    campaign_type VARCHAR(20) NOT NULL,
                    subject VARCHAR(200) DEFAULT '' NOT NULL,
                    target_audience JSONB NULL,
                    audience_count INTEGER DEFAULT 0 NOT NULL,
                    scheduled_send_date TIMESTAMP WITH TIME ZONE NULL,
                    actual_send_date TIMESTAMP WITH TIME ZONE NULL,
                    status VARCHAR(20) DEFAULT 'draft' NOT NULL,
                    send_immediately BOOLEAN DEFAULT FALSE NOT NULL,
                    sender_email VARCHAR(254) DEFAULT '' NOT NULL,
                    reply_to_email VARCHAR(254) NULL,
                    total_sent INTEGER DEFAULT 0 NOT NULL,
                    total_delivered INTEGER DEFAULT 0 NOT NULL,
                    total_bounced INTEGER DEFAULT 0 NOT NULL,
                    total_opened INTEGER DEFAULT 0 NOT NULL,
                    total_clicked INTEGER DEFAULT 0 NOT NULL,
                    total_unsubscribed INTEGER DEFAULT 0 NOT NULL,
                    total_complained INTEGER DEFAULT 0 NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    start_date DATE NULL,
                    end_date DATE NULL,
                    emails_sent INTEGER DEFAULT 0 NOT NULL,
                    last_email_sent TIMESTAMP WITH TIME ZONE NULL,
                    stop_on_reply BOOLEAN DEFAULT TRUE NOT NULL,
                    replied BOOLEAN DEFAULT FALSE NOT NULL,
                    company_id UUID NULL,
                    contract_id UUID NULL,
                    template_id UUID NULL
                )
            """)
            
            # Add foreign keys
            self.stdout.write("Adding foreign keys...")
            cursor.execute("""
                ALTER TABLE crm_app_email_campaign
                ADD CONSTRAINT crm_app_email_campaign_company_id_fkey
                FOREIGN KEY (company_id) REFERENCES crm_app_company(id)
                ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
            """)
            
            cursor.execute("""
                ALTER TABLE crm_app_email_campaign
                ADD CONSTRAINT crm_app_email_campaign_contract_id_fkey
                FOREIGN KEY (contract_id) REFERENCES crm_app_contract(id)
                ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
            """)
            
            cursor.execute("""
                ALTER TABLE crm_app_email_campaign
                ADD CONSTRAINT crm_app_email_campaign_template_id_fkey
                FOREIGN KEY (template_id) REFERENCES crm_app_emailtemplate(id)
                ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
            """)
            
            # Create indexes
            self.stdout.write("Creating indexes...")
            cursor.execute("CREATE INDEX crm_app_ema_status_e2260a_idx ON crm_app_email_campaign (status, created_at DESC)")
            cursor.execute("CREATE INDEX crm_app_ema_campaig_62ea85_idx ON crm_app_email_campaign (campaign_type, status)")
            cursor.execute("CREATE INDEX crm_app_ema_schedul_fd708b_idx ON crm_app_email_campaign (scheduled_send_date, status)")
            cursor.execute("CREATE INDEX crm_app_ema_company_99dbe1_idx ON crm_app_email_campaign (company_id, is_active)")
            
            self.stdout.write(self.style.SUCCESS('✓ Successfully created crm_app_email_campaign table'))
            self.stdout.write('  29 columns + 4 indexes + 3 foreign keys')
