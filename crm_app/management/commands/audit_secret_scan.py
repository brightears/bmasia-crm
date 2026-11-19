"""Read-only: count existing audit rows whose stored payload holds a secret-like key.

    manage.py audit_secret_scan

Prints counts only: rows scanned, rows with at least one secret-like key whose value is
not already "[redacted]", and the number of rows per model and dotted key name (for
example "User smtp_password: 2"). Never prints a value. Scans AuditLog.changes and
AuditLog.additional_data. On PostgreSQL it runs in a READ ONLY transaction; it writes
nothing on any database. Secret-like: crm_app/services/audit_redaction.py.
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from crm_app.services.audit_redaction import secret_keys_in


class Command(BaseCommand):
    help = 'Count audit rows whose stored changes contain a secret-like key (counts and names only).'

    def handle(self, *args, **options):
        from crm_app.models import AuditLog

        scanned = 0
        flagged = 0
        per_field = Counter()
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION READ ONLY')
            rows = AuditLog.objects.values_list('model_name', 'changes', 'additional_data').order_by('pk')
            for model_name, changes, additional in rows.iterator(chunk_size=500):
                scanned += 1
                names = set(secret_keys_in(changes)) | {f'additional_data.{n}' for n in secret_keys_in(additional)}
                if names:
                    flagged += 1
                    for name in names:
                        per_field[(model_name or '-', name)] += 1

        self.stdout.write(f'Audit rows scanned: {scanned}')
        self.stdout.write(f'Rows with a secret-like key holding a value: {flagged}')
        for (model_name, name), count in sorted(per_field.items()):
            self.stdout.write(f'  {model_name} {name}: {count}')
