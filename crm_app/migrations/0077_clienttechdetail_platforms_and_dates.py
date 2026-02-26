from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0076_clienttechdetail_platform_type'),
    ]

    operations = [
        # Update platform_type choices: add BMS and DM
        migrations.AlterField(
            model_name='clienttechdetail',
            name='platform_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('soundtrack', 'Soundtrack Your Brand'),
                    ('beatbreeze', 'Beat Breeze'),
                    ('bms', 'BMS'),
                    ('dm', 'DM'),
                ],
                help_text='Music platform type',
                max_length=20,
            ),
        ),
        # New operational/timeline fields
        migrations.AddField(
            model_name='clienttechdetail',
            name='install_date',
            field=models.DateField(blank=True, null=True, help_text='Date of installation'),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='commencement_date',
            field=models.DateField(blank=True, null=True, help_text='Service commencement date'),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='activation_date',
            field=models.DateField(blank=True, null=True, help_text='Activation date (SYB)'),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='lim_source',
            field=models.CharField(blank=True, help_text='LIM source reference', max_length=255),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='expiry_date',
            field=models.DateField(blank=True, null=True, help_text='Expiry date'),
        ),
    ]
