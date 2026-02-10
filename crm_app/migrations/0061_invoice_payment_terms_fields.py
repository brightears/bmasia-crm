from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0060_invoice_line_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='payment_terms',
            field=models.CharField(blank=True, default='Net 30', max_length=50),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_terms_text',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
    ]
