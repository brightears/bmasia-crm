"""Drift guard for the agent-facing MCP surface.

Every MCP ModelQueryToolset.fields entry must be a real model field (or property/relation) — when it
isn't, agents query a name that silently returns nothing and can't see fields that do exist. This
command reports any such phantom so it's caught in CI/deploy instead of by a confused agent.

    python manage.py check_mcp_schema        # report; exit 1 if any phantom found
"""
import inspect

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Validate every MCP Query.fields entry against its model (catches phantom fields)."

    def handle(self, *args, **options):
        from crm_app import mcp

        problems = 0
        checked = 0
        for name, obj in vars(mcp).items():
            model = getattr(obj, 'model', None)
            fields = getattr(obj, 'fields', None)
            if not (inspect.isclass(obj) and model is not None and isinstance(fields, (list, tuple))):
                continue
            checked += 1
            concrete = {f.name for f in model._meta.get_fields()}
            for fname in fields:
                base = str(fname).split('__')[0]
                if base in concrete or hasattr(model, base):
                    continue
                problems += 1
                self.stdout.write(self.style.ERROR(
                    f"  {name}: '{fname}' is not a field/property on {model.__name__}"))

        if problems:
            self.stdout.write(self.style.WARNING(
                f"\n{problems} phantom field(s) across {checked} Query classes."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(
            f"OK — all Query.fields across {checked} collections map to real model fields."))
