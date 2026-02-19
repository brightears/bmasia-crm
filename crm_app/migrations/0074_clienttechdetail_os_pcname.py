from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0073_client_tech_detail'),
    ]

    operations = [
        migrations.AddField(
            model_name='clienttechdetail',
            name='pc_name',
            field=models.CharField(blank=True, help_text='Computer/hostname', max_length=100),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='operating_system',
            field=models.CharField(blank=True, help_text='e.g. Windows 10, Windows 11', max_length=100),
        ),
        migrations.AddField(
            model_name='clienttechdetail',
            name='os_type',
            field=models.CharField(blank=True, help_text='32-bit or 64-bit', max_length=20),
        ),
    ]
