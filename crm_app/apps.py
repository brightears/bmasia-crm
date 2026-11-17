from django.apps import AppConfig


class CrmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm_app'

    def ready(self):
        import crm_app.signals  # noqa - registers signal handlers

        # Thai text in PDFs needs the bundled Sarabun files (crm_app/pdf_thai.py).
        from django.core import checks
        from crm_app.pdf_thai import check_thai_fonts
        checks.register(check_thai_fonts)

        # django-mcp-server's query_data_collections: limit paths and output to
        # published fields, with one-line errors. Never raises; if it cannot be
        # installed the query tool refuses every call (crm_app/mcp_query_guard.py).
        # See crm_app/mcp_query_help.py.
        from crm_app.mcp_query_help import install as install_query_error_hints
        install_query_error_hints()
