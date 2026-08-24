from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0097_rene_phase2_contract_boundary'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='renepreparedcontract',
            constraint=models.UniqueConstraint(
                fields=('source_contract',),
                name='unique_rene_preparation_per_source',
            ),
        ),
    ]
