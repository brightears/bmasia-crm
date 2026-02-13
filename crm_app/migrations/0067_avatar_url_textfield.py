from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0066_user_avatar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='avatar_url',
            field=models.TextField(blank=True, help_text='URL or base64 data URL for user avatar', null=True),
        ),
    ]
