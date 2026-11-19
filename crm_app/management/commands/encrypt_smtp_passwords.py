"""Encrypt stored SMTP app passwords (User.smtp_password) with FIELD_ENCRYPTION_KEY.

Dry run by default: prints counts only. Never prints or logs a value or its length.

    manage.py encrypt_smtp_passwords                  # counts: what --execute would do
    manage.py encrypt_smtp_passwords --execute        # encrypt; one transaction per row
    manage.py encrypt_smtp_passwords --execute --skip-undecryptable
                                                      # same, leaving unreadable values as they are
    manage.py encrypt_smtp_passwords --verify         # exit 1 unless every value is encrypted
                                                      # with the current key
    manage.py encrypt_smtp_passwords --decrypt-to-plain [--execute]
                                                      # rollback only: store plain text again
                                                      # (before reversing migration 0106)

Each stored value is one of:
- empty: no password stored;
- current: encrypted with FIELD_ENCRYPTION_KEY;
- previous key: encrypted with FIELD_ENCRYPTION_KEY_PREVIOUS (re-encrypted by --execute);
- undecryptable: an encrypted token (see crm_app/fields.py, "token-shaped") that no configured
  key decrypts. It is never treated as plain text: --execute refuses to run while any exist
  (unless --skip-undecryptable, which leaves them untouched and reports them), and --verify
  fails. The usual cause is a different key on this service; set the right key, or have the
  user enter the password again;
- plain: stored before encryption (encrypted by --execute).

--execute re-reads each row under a row lock, writes the encrypted form, reads the stored
column back and checks in memory that it decrypts with the current key to the same text;
otherwise the row's transaction rolls back and the command stops. Running it again
changes nothing. It refuses to run while FIELD_ENCRYPTION_KEY is unset, empty or the
built-in development default.

Key rotation (old key -> new key), with the owner's go-ahead:
1. Set FIELD_ENCRYPTION_KEY_PREVIOUS to the current key and FIELD_ENCRYPTION_KEY to the
   new one on the web service and every cron (the same values everywhere); deploy.
   Both keys read; saves use the new one.
2. Run `encrypt_smtp_passwords` (dry run), then `--execute`, then `--verify`.
3. Remove FIELD_ENCRYPTION_KEY_PREVIOUS everywhere and deploy.
If values show as undecryptable at any point, a service is using the wrong key: correct the
key instead of running --execute.
"""
from cryptography.fernet import InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import F, TextField
from django.db.models.functions import Cast

from crm_app import fields

EMPTY, CURRENT, PREVIOUS, UNDECRYPTABLE, PLAIN = 'empty', 'current', 'previous key', 'undecryptable', 'plain'


def _refuse_unless_real_key():
    try:
        keys = fields.configured_keys()
    except ImproperlyConfigured:
        keys = ()
    if not keys or not keys[0] or keys[0] == fields._builtin_key():
        raise CommandError(
            'FIELD_ENCRYPTION_KEY is unset or is the built-in development default; '
            'set a real key on this service first. Nothing was changed.'
        )
    try:
        return fields.current_fernet(), fields.crypter()
    except ImproperlyConfigured:
        raise CommandError('FIELD_ENCRYPTION_KEY is not in the expected format. Nothing was changed.') from None


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
        pass
    return UNDECRYPTABLE if fields.is_token_shaped(raw) else PLAIN


def _raw_rows(queryset):
    """(pk, stored column text) without the field's own decryption."""
    return queryset.annotate(raw_smtp=Cast(F('smtp_password'), output_field=TextField())).values_list(
        'pk', 'raw_smtp'
    )


def _write_raw(User, pk, text):
    """Write the column directly, bypassing the field (rollback path only)."""
    table = connection.ops.quote_name(User._meta.db_table)
    column = connection.ops.quote_name(User._meta.get_field('smtp_password').column)
    pk_column = connection.ops.quote_name(User._meta.pk.column)
    pk_value = User._meta.pk.get_db_prep_value(pk, connection)
    with connection.cursor() as cursor:
        cursor.execute(f'UPDATE {table} SET {column} = %s WHERE {pk_column} = %s', [text, pk_value])


class Command(BaseCommand):
    help = 'Encrypt stored SMTP app passwords. Dry run unless --execute. Prints counts only.'

    def add_arguments(self, parser):
        parser.add_argument('--execute', action='store_true', help='Write the changes (default: dry run).')
        parser.add_argument('--skip-undecryptable', action='store_true',
                            help='With --execute: leave values no configured key can read untouched.')
        parser.add_argument('--verify', action='store_true',
                            help='Exit with an error unless every stored value uses the current key.')
        parser.add_argument('--decrypt-to-plain', action='store_true',
                            help='Rollback only: store values as plain text again.')

    def handle(self, *args, **options):
        from crm_app.models import User

        current, everything = _refuse_unless_real_key()
        counts = self._count(User, current, everything)
        self._print_counts(counts)

        if options['verify']:
            left = counts[PLAIN] + counts[PREVIOUS] + counts[UNDECRYPTABLE]
            if left:
                raise CommandError(
                    f'{left} stored value(s) are not encrypted with the current key '
                    f'({counts[UNDECRYPTABLE]} cannot be decrypted with any configured key).'
                )
            self.stdout.write('Verified: every stored value is encrypted with the current key.')
            return

        if options['decrypt_to_plain']:
            return self._decrypt_to_plain(User, counts, everything, options['execute'])

        todo = counts[PLAIN] + counts[PREVIOUS]
        if not options['execute']:
            self.stdout.write(f'Dry run: would encrypt {todo} value(s). Nothing was changed.')
            if counts[UNDECRYPTABLE]:
                self.stdout.write(
                    f'{counts[UNDECRYPTABLE]} value(s) cannot be decrypted with any configured key; '
                    '--execute will refuse to run until that is resolved (or use --skip-undecryptable).'
                )
            return

        if counts[UNDECRYPTABLE] and not options['skip_undecryptable']:
            raise CommandError(
                f'{counts[UNDECRYPTABLE]} stored value(s) cannot be decrypted with any configured key. '
                'Nothing was changed. Check that this service uses the same FIELD_ENCRYPTION_KEY as the '
                'others, or pass --skip-undecryptable to leave those values as they are.'
            )

        done = 0
        for pk, _ in _raw_rows(User.objects.exclude(smtp_password__isnull=True).order_by('pk')):
            if self._encrypt_one(User, pk, current, everything):
                done += 1
        self.stdout.write(f'Encrypted {done} value(s).')
        after = self._count(User, current, everything)
        self._print_counts(after)
        if after[UNDECRYPTABLE]:
            self.stdout.write(f'Left untouched: {after[UNDECRYPTABLE]} value(s) that cannot be decrypted.')
        if after[PLAIN] or after[PREVIOUS]:
            raise CommandError('Some values are still not encrypted with the current key.')

    # ------------------------------------------------------------------ helpers

    def _count(self, User, current, everything):
        counts = {EMPTY: 0, CURRENT: 0, PREVIOUS: 0, UNDECRYPTABLE: 0, PLAIN: 0}
        for _, raw in _raw_rows(User.objects.all()):
            counts[_classify(raw, current, everything)] += 1
        return counts

    def _print_counts(self, counts):
        with_value = counts[CURRENT] + counts[PREVIOUS] + counts[PLAIN] + counts[UNDECRYPTABLE]
        self.stdout.write(
            f'Users with a stored SMTP password: {with_value}; '
            f'already encrypted with the current key: {counts[CURRENT]}; '
            f'would encrypt: {counts[PLAIN] + counts[PREVIOUS]} '
            f'(plain: {counts[PLAIN]}, previous key: {counts[PREVIOUS]}); '
            f'undecryptable: {counts[UNDECRYPTABLE]}'
        )

    def _encrypt_one(self, User, pk, current, everything):
        with transaction.atomic():
            row = list(_raw_rows(User.objects.select_for_update().filter(pk=pk)))
            if not row:
                return False
            raw = row[0][1]
            kind = _classify(raw, current, everything)
            if kind not in (PLAIN, PREVIOUS):
                return False
            plain = everything.decrypt(raw.encode('utf-8')).decode('utf-8') if kind == PREVIOUS else raw
            # update() with a string goes through the field, which encrypts with the current key.
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
        if not execute:
            self.stdout.write(f'Dry run: would store {encrypted} value(s) as plain text. Nothing was changed.')
            return
        done = 0
        for pk, _ in _raw_rows(User.objects.exclude(smtp_password__isnull=True).order_by('pk')):
            with transaction.atomic():
                row = list(_raw_rows(User.objects.select_for_update().filter(pk=pk)))
                raw = row[0][1] if row else None
                if not raw:
                    continue
                try:
                    plain = everything.decrypt(raw.encode('utf-8')).decode('utf-8')
                except InvalidToken:
                    continue  # plain already, or undecryptable (left as it is)
                _write_raw(User, pk, plain)
                stored = list(_raw_rows(User.objects.filter(pk=pk)))[0][1]
                if stored != plain:
                    raise CommandError(f'Verification failed for user {pk}; that row was rolled back.')
                done += 1
        self.stdout.write(f'Stored {done} value(s) as plain text.')
        if counts[UNDECRYPTABLE]:
            self.stdout.write(f'Left untouched: {counts[UNDECRYPTABLE]} value(s) that cannot be decrypted.')
