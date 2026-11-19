"""User.smtp_password becomes an encrypted field.

Forward: schema only. The column type widens from varchar(255) to text, because an
encrypted value is longer than the plain one (a 255-character value encrypts to about
440 characters). No stored value is changed. Existing plain values keep working (reads
accept both forms) until `manage.py encrypt_smtp_passwords --execute` encrypts them.

Backward: narrowing back to varchar(255) would cut longer values without an error on
PostgreSQL, so the reverse first checks every stored value and refuses while any is
encrypted or longer than 255 characters. Rollback procedure:
1. `manage.py encrypt_smtp_passwords --decrypt-to-plain` (dry run), then with `--execute`;
2. `manage.py migrate crm_app 0105`.
"""
import crm_app.fields
from django.db import migrations


def refuse_reverse_while_values_would_not_fit(apps, schema_editor):
    from crm_app.fields import is_token_shaped

    table = schema_editor.quote_name('auth_user')
    column = schema_editor.quote_name('smtp_password')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'SELECT {column} FROM {table} WHERE {column} IS NOT NULL')
        values = [row[0] for row in cursor.fetchall()]
    encrypted = sum(1 for v in values if is_token_shaped(v))
    too_long = sum(1 for v in values if len(v) > 255)
    if encrypted or too_long:
        raise RuntimeError(
            f'Migration 0106 cannot be reversed: {encrypted} stored SMTP password(s) are encrypted and '
            f'{too_long} are longer than 255 characters, which the narrower column would cut. Run '
            '"manage.py encrypt_smtp_passwords --decrypt-to-plain --execute" first, then reverse.'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('crm_app', '0105_care_touch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='smtp_password',
            field=crm_app.fields.EncryptedSecretField(
                blank=True, help_text='Gmail app password (stored encrypted)', max_length=255, null=True,
            ),
        ),
        # Reversed before the AlterField above, so it guards the narrowing.
        migrations.RunPython(migrations.RunPython.noop, refuse_reverse_while_values_would_not_fit),
    ]
