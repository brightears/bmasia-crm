from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0097_rene_phase2_contract_boundary')]

    operations = [
        migrations.AddField(
            model_name=model_name,
            name='billing_entity',
            field=models.CharField(
                blank=True, default='', max_length=50,
                choices=[
                    ('BMAsia Limited', 'BMAsia Limited (Hong Kong)'),
                    ('BMAsia (Thailand) Co., Ltd.', 'BMAsia (Thailand) Co., Ltd.'),
                ],
                help_text="Issuer override for this document only. Blank uses the company's billing entity; independent of currency and customer country.",
            ),
        )
        for model_name in ('quote', 'contract', 'invoice')
    ] + [
        migrations.AddField(
            model_name='contract', name='payment_schedule',
            field=models.TextField(
                blank=True, default='',
                help_text="Explicit customer-facing payment schedule, preserved independently from legal payment terms.",
            ),
        ),
    ]
