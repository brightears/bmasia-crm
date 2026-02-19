import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0072_email_delivery_confirmation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientTechDetail',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('outlet_name', models.CharField(help_text='Outlet or zone name', max_length=255)),
                # Remote Access
                ('anydesk_id', models.CharField(blank=True, max_length=100)),
                ('teamviewer_id', models.CharField(blank=True, max_length=100)),
                ('ultraviewer_id', models.CharField(blank=True, max_length=100)),
                ('other_remote_id', models.CharField(blank=True, help_text='Other remote access ID', max_length=255)),
                # System Configuration
                ('system_type', models.CharField(blank=True, choices=[('single', 'Single'), ('multi', 'Multi')], max_length=10)),
                ('soundcard_channel', models.CharField(blank=True, max_length=100)),
                ('bms_license', models.CharField(blank=True, max_length=255)),
                ('additional_hardware', models.TextField(blank=True, help_text='Additional system hardware details')),
                # PC Specifications
                ('pc_make', models.CharField(blank=True, max_length=100)),
                ('pc_model', models.CharField(blank=True, max_length=100)),
                ('pc_type', models.CharField(blank=True, max_length=100)),
                ('ram', models.CharField(blank=True, help_text='e.g. 8GB, 16GB DDR4', max_length=50)),
                ('cpu_type', models.CharField(blank=True, max_length=100)),
                ('cpu_speed', models.CharField(blank=True, help_text='e.g. 3.4 GHz', max_length=50)),
                ('cpu_cores', models.CharField(blank=True, help_text='Cores and logical processors', max_length=50)),
                ('hdd_c', models.CharField(blank=True, help_text='C: drive capacity/type', max_length=100)),
                ('hdd_d', models.CharField(blank=True, help_text='D: drive capacity/type', max_length=100)),
                ('network_type', models.CharField(blank=True, help_text='e.g. Ethernet, WiFi, LAN', max_length=100)),
                # Audio Equipment
                ('amplifiers', models.TextField(blank=True)),
                ('distribution', models.TextField(blank=True)),
                ('speakers', models.TextField(blank=True)),
                ('other_equipment', models.TextField(blank=True)),
                # Links
                ('music_spec_link', models.URLField(blank=True, help_text='Link to music spec document', max_length=500)),
                ('syb_schedules_link', models.URLField(blank=True, help_text='Link to SYB schedules', max_length=500)),
                # General
                ('comments', models.TextField(blank=True)),
                # Foreign Keys
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tech_details', to='crm_app.company')),
                ('zone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tech_details', to='crm_app.zone')),
            ],
            options={
                'verbose_name': 'Client Tech Detail',
                'verbose_name_plural': 'Client Tech Details',
                'ordering': ['company__name', 'outlet_name'],
            },
        ),
        migrations.AddIndex(
            model_name='clienttechdetail',
            index=models.Index(fields=['company', 'outlet_name'], name='crm_app_cli_company_idx'),
        ),
    ]
