from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.careseekers.models import Careseeker
from apps.utils.services.account_status_email_service import (
    send_careseeker_welcome_email,
)


@receiver(pre_save, sender=Careseeker)
def cache_previous_careseeker_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_account_status = None
        return

    previous = sender.objects.filter(pk=instance.pk).values("account_status").first()
    instance._previous_account_status = (
        previous["account_status"] if previous else None
    )


@receiver(post_save, sender=Careseeker)
def send_careseeker_account_status_email(sender, instance, created, **kwargs):
    if created:
        return

    previous_account_status = getattr(instance, "_previous_account_status", None)
    if previous_account_status == instance.account_status:
        return

    if instance.account_status == Careseeker.AccountStatus.APPROVED:
        send_careseeker_welcome_email(instance)
