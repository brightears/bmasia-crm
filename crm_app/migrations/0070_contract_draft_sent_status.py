from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0069_quote_followup_flags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('Draft', 'Draft'),
                    ('Sent', 'Sent'),
                    ('Active', 'Active'),
                    ('Renewed', 'Renewed'),
                    ('Expired', 'Expired'),
                    ('Cancelled', 'Cancelled'),
                ],
                default='Draft',
                max_length=20,
            ),
        ),
    ]
