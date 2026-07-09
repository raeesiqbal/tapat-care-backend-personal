from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.caregivers.models import Caregiver
from apps.utils.services.account_status_email_service import (
    send_caregiver_approved_email,
    send_caregiver_rejected_email,
)


@receiver(pre_save, sender=Caregiver)
def cache_previous_caregiver_statuses(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_account_status = None
        instance._previous_screening_status = None
        return

    previous = sender.objects.filter(pk=instance.pk).values(
        "account_status",
        "screening_status",
    ).first()
    if not previous:
        instance._previous_account_status = None
        instance._previous_screening_status = None
        return

    instance._previous_account_status = previous["account_status"]
    instance._previous_screening_status = previous["screening_status"]


@receiver(post_save, sender=Caregiver)
def send_caregiver_account_status_email(sender, instance, created, **kwargs):
    if created:
        return

    previous_account_status = getattr(instance, "_previous_account_status", None)
    previous_screening_status = getattr(instance, "_previous_screening_status", None)

    was_approved = (
        previous_account_status == Caregiver.AccountStatus.APPROVED
        and previous_screening_status == Caregiver.ScreeningStatus.APPROVED
    )
    is_approved = (
        instance.account_status == Caregiver.AccountStatus.APPROVED
        and instance.screening_status == Caregiver.ScreeningStatus.APPROVED
    )
    if is_approved and not was_approved:
        send_caregiver_approved_email(instance)
        return

    was_rejected = (
        previous_account_status == Caregiver.AccountStatus.REJECTED
        and previous_screening_status == Caregiver.ScreeningStatus.REJECTED
    )
    is_rejected = (
        instance.account_status == Caregiver.AccountStatus.REJECTED
        and instance.screening_status == Caregiver.ScreeningStatus.REJECTED
    )
    if is_rejected and not was_rejected:
        send_caregiver_rejected_email(instance)
