import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0085_invoice_receipt_fields'),
    ]

    operations = [
        # Add deferred_revenue field to BalanceSheetSnapshot
        migrations.AddField(
            model_name='balancesheetsnapshot',
            name='deferred_revenue',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Override: Advance received / deferred revenue (calculated from revenue recognition schedules)',
                max_digits=15,
                null=True,
            ),
        ),

        # Create RevenueRecognitionSchedule
        migrations.CreateModel(
            name='RevenueRecognitionSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invoice_number', models.CharField(db_index=True, max_length=50)),
                ('invoice_date', models.DateField()),
                ('client_name', models.CharField(max_length=255)),
                ('memo', models.CharField(blank=True, max_length=500)),
                ('billing_entity', models.CharField(
                    choices=[('bmasia_th', 'BMAsia (Thailand) Co., Ltd.'), ('bmasia_hk', 'BMAsia Limited')],
                    max_length=20,
                )),
                ('currency', models.CharField(default='THB', max_length=3)),
                ('product', models.CharField(
                    choices=[('SYB', 'SYB (Soundtrack Your Brand)'), ('LIM', 'LIM (Licence Inclusive Music)'), ('SONOS', 'SONOS'), ('OTHER', 'Other')],
                    default='SYB',
                    max_length=10,
                )),
                ('revenue_class', models.CharField(
                    choices=[('New', 'New'), ('Renew', 'Renew'), ('Add Outlet', 'Add Outlet'), ('Upgrade', 'Upgrade'), ('Other', 'Other')],
                    default='New',
                    max_length=20,
                )),
                ('amount', models.DecimalField(
                    decimal_places=2,
                    help_text='Pre-tax invoice amount to recognize over the service period',
                    max_digits=15,
                )),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('sales_price', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    help_text='Unit price (for display — amount = qty × price)',
                    max_digits=15,
                    null=True,
                )),
                ('service_period_start', models.DateField()),
                ('service_period_end', models.DateField()),
                ('duration_months', models.DecimalField(
                    decimal_places=2,
                    help_text='Duration in months (can be fractional)',
                    max_digits=6,
                )),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('cancelled', 'Cancelled'), ('modified', 'Modified')],
                    default='active',
                    max_length=20,
                )),
                ('is_imported', models.BooleanField(default=False, help_text='True if created from Excel import')),
                ('invoice', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recognition_schedules',
                    to='crm_app.invoice',
                )),
                ('invoice_line_item', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recognition_schedules',
                    to='crm_app.invoicelineitem',
                )),
            ],
            options={
                'verbose_name': 'Revenue Recognition Schedule',
                'verbose_name_plural': 'Revenue Recognition Schedules',
                'ordering': ['invoice_date', 'client_name'],
                'indexes': [
                    models.Index(fields=['billing_entity', 'status'], name='crm_app_rev_billing_idx'),
                    models.Index(fields=['invoice_date'], name='crm_app_rev_invdate_idx'),
                    models.Index(fields=['product'], name='crm_app_rev_product_idx'),
                    models.Index(fields=['service_period_start', 'service_period_end'], name='crm_app_rev_svcprd_idx'),
                ],
            },
        ),

        # Create RevenueRecognitionEntry
        migrations.CreateModel(
            name='RevenueRecognitionEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('year', models.IntegerField()),
                ('quarter', models.IntegerField(help_text='1-4')),
                ('recognized_amount', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Revenue recognized in this quarter',
                    max_digits=15,
                )),
                ('balance', models.DecimalField(
                    decimal_places=2,
                    default=0,
                    help_text='Remaining deferred revenue after this quarter',
                    max_digits=15,
                )),
                ('is_manually_overridden', models.BooleanField(default=False)),
                ('override_reason', models.CharField(blank=True, max_length=255)),
                ('schedule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entries',
                    to='crm_app.revenuerecognitionschedule',
                )),
            ],
            options={
                'verbose_name': 'Revenue Recognition Entry',
                'verbose_name_plural': 'Revenue Recognition Entries',
                'ordering': ['year', 'quarter'],
                'unique_together': {('schedule', 'year', 'quarter')},
                'indexes': [
                    models.Index(fields=['year', 'quarter'], name='crm_app_reventry_yrqtr_idx'),
                ],
            },
        ),
    ]
