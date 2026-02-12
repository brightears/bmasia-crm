from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0064_company_phone_email_contact_mobile'),
    ]

    operations = [
        # Company: Tax ID and Branch for Thai tax compliance
        migrations.AddField(
            model_name='company',
            name='tax_id',
            field=models.CharField(blank=True, help_text='Tax Identification Number', max_length=50),
        ),
        migrations.AddField(
            model_name='company',
            name='branch',
            field=models.CharField(blank=True, help_text='Head Office or Branch name/number', max_length=100),
        ),
        # Invoice: Property name for Bill To
        migrations.AddField(
            model_name='invoice',
            name='property_name',
            field=models.CharField(blank=True, help_text='Property/venue name for Bill To', max_length=200),
        ),
        # InvoiceLineItem: Product/Service field (matching Quote/Contract line items)
        migrations.AddField(
            model_name='invoicelineitem',
            name='product_service',
            field=models.CharField(blank=True, max_length=200),
        ),
        # InvoiceLineItem: Per-line service period
        migrations.AddField(
            model_name='invoicelineitem',
            name='service_period_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoicelineitem',
            name='service_period_end',
            field=models.DateField(blank=True, null=True),
        ),
    ]
