from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        # Registra el receptor de hijack_ended (restauración de OTP del admin).
        from . import signals  # noqa: F401
