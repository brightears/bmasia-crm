import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('crm_app', '0100_beat_breeze_player_variants')]

    operations = [
        migrations.CreateModel(
            name='ContractSendReceiptUse',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_key', models.CharField(max_length=256, unique=True)),
                ('nonce', models.UUIDField(unique=True)),
                ('receipt_sha256', models.CharField(max_length=64, unique=True)),
                ('key_id', models.CharField(max_length=64)),
                ('contract_number', models.CharField(max_length=50)),
                ('sent_date', models.DateField()),
                ('before_version', models.CharField(max_length=128)),
                ('after_version', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='send_receipt_uses', to='crm_app.contract',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
