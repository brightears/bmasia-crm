"""Reset the password of the existing `admin` user.

The new password comes from ADMIN_INITIAL_PASSWORD or an interactive prompt;
the command refuses to run when neither is available.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from crm_app.management.admin_password import add_no_input_argument, resolve_admin_password


class Command(BaseCommand):
    help = (
        'Reset the admin user password. Reads ADMIN_INITIAL_PASSWORD, '
        'or prompts when run interactively.'
    )

    def add_arguments(self, parser):
        add_no_input_argument(parser)

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            admin_user = User.objects.get(username='admin')
        except User.DoesNotExist:
            raise CommandError('Admin user not found. Use the createadmin command instead.')

        password = resolve_admin_password(interactive=options['interactive'], user=admin_user)
        admin_user.set_password(password)
        admin_user.save()
        self.stdout.write(self.style.SUCCESS('Admin password reset.'))
