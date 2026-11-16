from django.apps import AppConfig


class CrmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_app'

    def ready(self):
        import crm_app.signals  # noqa - registers signal handlers

        # django-mcp-server's query_data_collections: one-line errors for unknown
        # fields and collections that list only published fields. Valid queries
        # are passed through untouched. See crm_app/mcp_query_help.py.
        from crm_app.mcp_query_help import install as install_query_error_hints
        install_query_error_hints()
