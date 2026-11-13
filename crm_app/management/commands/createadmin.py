"""Create the `admin` superuser if it does not exist yet.

The password comes from ADMIN_INITIAL_PASSWORD or an interactive prompt; the
command refuses to create the user when neither is available.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from crm_app.management.admin_password import add_no_input_argument, resolve_admin_password


class Command(BaseCommand):
    help = (
        'Create the admin user for BMAsia CRM. Reads ADMIN_INITIAL_PASSWORD, '
        'or prompts when run interactively.'
    )

    def add_arguments(self, parser):
        add_no_input_argument(parser)

    def handle(self, *args, **options):
        User = get_user_model()

        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.SUCCESS('Admin user already exists; nothing to do.'))
            return

        password = resolve_admin_password(interactive=options['interactive'])
        User.objects.create_superuser(
            username='admin',
            email='admin@bmasia.com',
            password=password,
            first_name='BMAsia',
            last_name='Admin',
            role='Admin',
        )
        self.stdout.write(self.style.SUCCESS('Admin user created (username: admin).'))
