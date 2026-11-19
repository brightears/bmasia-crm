"""Encrypt stored SMTP app passwords (User.smtp_password) with FIELD_ENCRYPTION_KEY.

Dry run by default: prints counts only. Never prints or logs a value or its length.

    manage.py encrypt_smtp_passwords                  # counts: what --execute would do
    manage.py encrypt_smtp_passwords --execute        # encrypt; one transaction per row
    manage.py encrypt_smtp_passwords --verify         # exit 1 unless every value is encrypted
                                                      # with the current key
    manage.py encrypt_smtp_passwords --decrypt-to-plain [--execute]
                                                      # rollback only: store plain text again
                                                      # (before reversing migration 0106)

Each stored value is one of:
- empty: no password stored;
- current: encrypted with FIELD_ENCRYPTION_KEY;
- previous key: encrypted with FIELD_ENCRYPTION_KEY_PREVIOUS (re-encrypted by --execute);
- plain: stored before encryption (encrypted by --execute).

--execute re-reads each row under a row lock, writes the encrypted form, reads the stored
column back and checks in memory that it decrypts with the current key to the same text;
otherwise the row's transaction rolls back and the command stops. Running it again
changes nothing. It refuses to run while FIELD_ENCRYPTION_KEY is unset, empty or the
built-in development default.

Key rotation (old key -> new key), with the owner's go-ahead:
1. Set FIELD_ENCRYPTION_KEY_PREVIOUS to the current key and FIELD_ENCRYPTION_KEY to the
   new one on the web service and every cron; deploy. Both keys read; saves use the new one.
2. Run `encrypt_smtp_passwords` (dry run), then `--execute`, then `--verify`.
3. Remove FIELD_ENCRYPTION_KEY_PREVIOUS everywhere and deploy.
"""
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, TextField, Value
from django.db.models.functions import Cast

EMPTY, CURRENT, PREVIOUS, PLAIN = 'empty', 'current', 'previous key', 'plain'


def _configured_keys():
    keys = settings.FIELD_ENCRYPTION_KEY
    if isinstance(keys, (list, tuple)):
        return [k for k in keys]
    return [keys]


def _builtin_default():
    try:
        from bmasia_crm import settings as project_settings
    except Exception:  # pragma: no cover - settings module renamed
        return None
    return getattr(project_settings, '_BUILTIN_FIELD_ENCRYPTION_KEY', None)


def _refuse_unless_real_key():
    keys = _configured_keys()
    primary = keys[0] if keys else None
    if not primary or primary == _builtin_default():
        raise CommandError(
            'FIELD_ENCRYPTION_KEY is unset or is the built-in development default; '
            'set a real key on this service first. Nothing was changed.'
        )
    try:
        current = Fernet(primary)
        everything = MultiFernet([Fernet(k) for k in keys])
    except Exception:
        raise CommandError('FIELD_ENCRYPTION_KEY is not in the expected format. Nothing was changed.')
    return current, everything


def _classify(raw, current, everything):
    if raw is None or raw == '':
        return EMPTY
    try:
        current.decrypt(raw.encode('utf-8'))
        return CURRENT
    except InvalidToken:
        pass
    try:
        everything.decrypt(raw.encode('utf-8'))
        return PREVIOUS
    except InvalidToken:
        return PLAIN


def _raw_rows(queryset):
    """(pk, stored column text) without the field's own decryption."""
    return queryset.annotate(raw_smtp=Cast(F('smtp_password'), output_field=TextField())).values_list(
        'pk', 'raw_smtp'
    )


class Command(BaseCommand):
    help = 'Encrypt stored SMTP app passwords. Dry run unless --execute. Prints counts only.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Write the changes (default: dry run).')
        parser.add_argument('--verify', action='store_true',
                            help='Exit with an error unless every stored value uses the current key.')
        parser.add_argument('--decrypt-to-plain', action='store_true',
                            help='Rollback only: store values as plain text again.')

    def handle(self, *args, **options):
        from crm_app.models import User

        current, everything = _refuse_unless_real_key()
        counts = self._count(User, current, everything)

        if options['verify']:
            self._print_counts(counts)
            left = counts[PLAIN] + counts[PREVIOUS]
            if left:
                raise CommandError(f'{left} stored value(s) are not encrypted with the current key.')
            self.stdout.write('Verified: every stored value is encrypted with the current key.')
            return

        if options['decrypt_to_plain']:
            return self._decrypt_to_plain(User, counts, everything, options['execute'])

        self._print_counts(counts)
        todo = counts[PLAIN] + counts[PREVIOUS]
        if not options['execute']:
            self.stdout.write(f'Dry run: would encrypt {todo} value(s). Nothing was changed.')
            return

        done = 0
        for pk, _ in _raw_rows(User.objects.exclude(smtp_password__isnull=True).order_by('pk')):
            if self._encrypt_one(User, pk, current, everything):
                done += 1
        self.stdout.write(f'Encrypted {done} value(s).')
        after = self._count(User, current, everything)
        self._print_counts(after)
        if after[PLAIN] or after[PREVIOUS]:
            raise CommandError('Some values are still not encrypted with the current key.')

    # ------------------------------------------------------------------ helpers

    def _count(self, User, current, everything):
        counts = {EMPTY: 0, CURRENT: 0, PREVIOUS: 0, PLAIN: 0}
        for _, raw in _raw_rows(User.objects.all()):
            counts[_classify(raw, current, everything)] += 1
        return counts

    def _print_counts(self, counts):
        with_value = counts[CURRENT] + counts[PREVIOUS] + counts[PLAIN]
        self.stdout.write(
            f'Users with a stored SMTP password: {with_value}; '
            f'already encrypted with the current key: {counts[CURRENT]}; '
            f'would encrypt: {counts[PLAIN] + counts[PREVIOUS]} '
            f'(plain: {counts[PLAIN]}, previous key: {counts[PREVIOUS]})'
        )

    def _encrypt_one(self, User, pk, current, everything):
        with transaction.atomic():
            locked = User.objects.select_for_update().filter(pk=pk)
            row = list(_raw_rows(locked))
            if not row:
                return False
            raw = row[0][1]
            kind = _classify(raw, current, everything)
            if kind in (EMPTY, CURRENT):
                return False
            plain = everything.decrypt(raw.encode('utf-8')).decode('utf-8') if kind == PREVIOUS else raw
            # update() runs the field's get_db_prep_save, which encrypts with the current key.
            User.objects.filter(pk=pk).update(smtp_password=plain)
            stored = list(_raw_rows(User.objects.filter(pk=pk)))[0][1]
            try:
                ok = current.decrypt(stored.encode('utf-8')).decode('utf-8') == plain
            except InvalidToken:
                ok = False
            if not ok:
                raise CommandError(f'Verification failed for user {pk}; that row was rolled back.')
            return True

    def _decrypt_to_plain(self, User, counts, everything, execute):
        encrypted = counts[CURRENT] + counts[PREVIOUS]
        self._print_counts(counts)
        if not execute:
            self.stdout.write(f'Dry run: would store {encrypted} value(s) as plain text. Nothing was changed.')
            return
        done = 0
        rows = _raw_rows(User.objects.exclude(smtp_password__isnull=True).order_by('pk'))
        for pk, _ in rows:
            with transaction.atomic():
                row = list(_raw_rows(User.objects.select_for_update().filter(pk=pk)))
                raw = row[0][1] if row else None
                if not raw:
                    continue
                try:
                    plain = everything.decrypt(raw.encode('utf-8')).decode('utf-8')
                except InvalidToken:
                    continue  # already plain
                # Bypass the field's encryption: write the column directly.
                User.objects.filter(pk=pk).update(smtp_password=Value(plain, output_field=TextField()))
                stored = list(_raw_rows(User.objects.filter(pk=pk)))[0][1]
                if stored != plain:
                    raise CommandError(f'Verification failed for user {pk}; that row was rolled back.')
                done += 1
        self.stdout.write(f'Stored {done} value(s) as plain text.')

