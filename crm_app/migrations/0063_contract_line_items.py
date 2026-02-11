import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0062_invoice_service_period'),
    ]

    operations = [
        # Add quote FK to Contract
        migrations.AddField(
            model_name='contract',
            name='quote',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contracts',
                to='crm_app.quote',
            ),
        ),
        # Create ContractLineItem model
        migrations.CreateModel(
            name='ContractLineItem',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('product_service', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('discount_percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('tax_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('line_total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('contract', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='line_items',
                    to='crm_app.contract',
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
    ]
