from django.apps import AppConfig


class AgentInboxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agent_inbox'
    verbose_name = 'Activity log and review queue'
