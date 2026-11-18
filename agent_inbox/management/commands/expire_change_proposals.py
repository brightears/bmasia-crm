"""Mark open change proposals past their expiry as expired.

The API also does this before listing or deciding, so running this command is
optional (for example as part of a nightly job). It changes only proposal rows.
"""
from django.core.management.base import BaseCommand

from agent_inbox.proposals import expire_due


class Command(BaseCommand):
    help = 'Mark open change proposals past their expiry as expired.'

    def handle(self, *args, **options):
        count = expire_due()
        self.stdout.write(f'expired={count}')
