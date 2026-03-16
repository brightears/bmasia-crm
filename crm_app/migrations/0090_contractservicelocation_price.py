from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0089_contractservicelocation_custom_platform'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractservicelocation',
            name='price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Price per zone (overrides contract.price_per_zone if set)',
                max_digits=10,
                null=True,
            ),
        ),
    ]
