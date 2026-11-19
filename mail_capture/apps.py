from django.apps import AppConfig


class MailCaptureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mail_capture'
    verbose_name = 'Mail capture'
    # No ready() hook on purpose: the app has no start-up side effects.
