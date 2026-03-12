from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0088_fix_ascott_template_notices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contractservicelocation',
            name='platform',
            field=models.CharField(
                choices=[('soundtrack', 'Soundtrack Your Brand'), ('beatbreeze', 'Beat Breeze'), ('custom', 'Custom')],
                default='soundtrack',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='contractservicelocation',
            name='custom_service_name',
            field=models.CharField(blank=True, default='', help_text="Display name for custom products (e.g., 'MP3')", max_length=200),
        ),
    ]
