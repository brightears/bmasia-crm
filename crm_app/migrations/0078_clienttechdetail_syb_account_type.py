from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0077_clienttechdetail_platforms_and_dates'),
    ]

    operations = [
        migrations.AddField(
            model_name='clienttechdetail',
            name='syb_account_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('essential', 'Essential'),
                    ('unlimited', 'Unlimited'),
                ],
                help_text='SYB subscription tier',
                max_length=20,
            ),
        ),
    ]
