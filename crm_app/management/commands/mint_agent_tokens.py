"""
Mint per-agent DRF tokens for MCP access.

Creates (or gets) a User for each named agent and issues a stable auth token.
Each agent's MCP client uses this token in the ?token=xxx query param (or
Authorization header) when connecting to /mcp/.

Usage:
    python manage.py mint_agent_tokens                 # mints all default agents
    python manage.py mint_agent_tokens --agent nina    # mints a single agent
    python manage.py mint_agent_tokens --rotate        # rotates (deletes + recreates) tokens
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token

DEFAULT_AGENTS = ["lyra", "ruby", "theo", "riff", "nina"]


class Command(BaseCommand):
    help = "Mint or rotate DRF auth tokens for BMAsia agent users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--agent",
            type=str,
            default=None,
            help="Mint a token for a single agent (default: all DEFAULT_AGENTS)",
        )
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="Delete existing token and create a new one",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        agents = [options["agent"]] if options["agent"] else DEFAULT_AGENTS

        self.stdout.write(self.style.NOTICE("Minting MCP tokens for: " + ", ".join(agents)))
        self.stdout.write("")

        for name in agents:
            user, created = User.objects.get_or_create(
                username=name,
                defaults={
                    "email": f"{name}@bmasiamusic.com",
                    "first_name": name.capitalize(),
                    "last_name": "Agent",
                    "role": "Admin",
                    "is_staff": False,
                    "is_active": True,
                },
            )

            if options["rotate"]:
                Token.objects.filter(user=user).delete()

            token, tok_created = Token.objects.get_or_create(user=user)

            tag = "CREATED" if created else "EXISTS"
            tok_tag = "NEW" if tok_created or options["rotate"] else "EXISTING"

            self.stdout.write(f"[{tag}] user={name}  [{tok_tag}] token={token.key}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done. Paste tokens into each agent's .mcp.json:"))
        self.stdout.write(
            '"bmasia-crm": { "type": "http", '
            '"url": "https://bmasia-crm.onrender.com/mcp/?token=<token>" }'
        )
