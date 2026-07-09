from django.db import models

# Create your models here.
from apps.utils.models.base import AbstractBaseModel

class Booking(AbstractBaseModel):
    class StatusChoices(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"
        NO_SHOW = "no_show", "No Show"

    careseeker = models.ForeignKey(
        'careseekers.Careseeker',
        on_delete=models.CASCADE,
        related_name='booking_careseeker',
        db_index=True
    )
    caregiver = models.ForeignKey(
        'caregivers.Caregiver',
        on_delete=models.CASCADE,
        related_name='booking_caregiver',
        db_index=True
    )
    job_post = models.ForeignKey(
        'marketplace.JobPost',
        on_delete=models.CASCADE,
        related_name='booking_job_post',
        null=True,blank=True,
        db_index=True 
    )
    application = models.ForeignKey(
        'marketplace.JobApplication',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='booking_application',
        db_index=True
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        db_index=True
    )
    def __str__(self):
        return f"Booking {self.id} - {self.careseeker} with {self.caregiver}"
