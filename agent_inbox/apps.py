from django.apps import AppConfig
from django.conf import settings


class AgentInboxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent_inbox'
    verbose_name = 'Activity log and review queue'

    def ready(self):
        # Email content recorded here follows the mail-capture rules: when that app
        # purges a message, it is redacted here. The signal is looked up by its
        # dotted path, so this app does not import the other one.
        from agent_inbox.redaction import connect_purge_signal
        connect_purge_signal(getattr(settings, 'AGENT_INBOX_MAIL_PURGED_SIGNAL', ''))
