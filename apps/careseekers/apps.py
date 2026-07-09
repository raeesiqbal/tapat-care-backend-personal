from django.apps import AppConfig

class CareseekersConfig(AppConfig):
    name = 'apps.careseekers'

    def ready(self):
        import apps.careseekers.signals  # noqa: F401
