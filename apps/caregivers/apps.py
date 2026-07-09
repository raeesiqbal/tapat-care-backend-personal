from django.apps import AppConfig


class CaregiversConfig(AppConfig):
    name = 'apps.caregivers'

    def ready(self):
        import apps.caregivers.signals  # noqa: F401
