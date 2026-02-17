import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0070_contract_draft_sent_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractServiceLocation',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_locations', to='crm_app.contract')),
                ('location_name', models.CharField(max_length=200)),
                ('platform', models.CharField(choices=[('soundtrack', 'Soundtrack Your Brand'), ('beatbreeze', 'Beat Breeze')], default='soundtrack', max_length=20)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['sort_order', 'platform', 'location_name'],
            },
        ),
    ]
