from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'

    def ready(self):
        # Register signal handlers (password reset email hooks, etc.)
        import apps.users.signals  # noqa: F401
