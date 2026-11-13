"""Where the admin bootstrap commands get the admin password from.

There is deliberately no default: the password comes from the
ADMIN_INITIAL_PASSWORD environment variable or from an interactive prompt,
and the commands refuse to run when neither is available. The value is
checked against AUTH_PASSWORD_VALIDATORS and is never printed.
"""
import getpass
import os
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

ADMIN_PASSWORD_ENV_VAR = 'ADMIN_INITIAL_PASSWORD'


def add_no_input_argument(parser):
    parser.add_argument(
        '--noinput', '--no-input',
        action='store_false',
        dest='interactive',
        help=f'Never prompt; read the password from {ADMIN_PASSWORD_ENV_VAR} only.',
    )


def resolve_admin_password(*, interactive=True, user=None):
    password = os.environ.get(ADMIN_PASSWORD_ENV_VAR, '')
    if password.strip():
        _validate(password, user)
        return password

    if interactive and sys.stdin.isatty():
        password = getpass.getpass('Admin password: ')
        if not password.strip():
            raise CommandError('Admin password cannot be blank.')
        if getpass.getpass('Admin password (again): ') != password:
            raise CommandError('Passwords did not match.')
        _validate(password, user)
        return password

    raise CommandError(
        f'No admin password available. Set the {ADMIN_PASSWORD_ENV_VAR} environment '
        'variable or run this command from an interactive terminal.'
    )


def _validate(password, user):
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise CommandError('Admin password rejected: ' + ' '.join(exc.messages)) from exc
