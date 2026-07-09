from django.db import models
from apps.utils.models.base import AbstractBaseModel
# Create your models here.
class JobPost(AbstractBaseModel):
    class STATUS_CHOICES(models.TextChoices):
       OPEN  = "open", "Open"
       PAUSED = "paused", "Paused"
       CLOSED= "closed", "Closed"
    careseeker = models.ForeignKey(
        'careseekers.CareSeeker',
        on_delete=models.CASCADE,
        db_index=True
    )
    created_by_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        db_index=True
    )
    title = models.CharField(
        max_length=255,
    )
    description = models.TextField(
    )
    start_at = models.DateTimeField(
    )
    end_at = models.DateTimeField(
    )
    careseeker_address = models.ForeignKey(
        'users.UserAddress',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES.choices,
        db_index=True
    )

    def __str__(self):
        return self.title
    
class JobRequiredSkill(AbstractBaseModel):
    job_post = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="required_skills",
        db_index=True
    )
    skill = models.ForeignKey(
        'caregivers.Skill',
        on_delete=models.CASCADE
    )
    class Meta:
        unique_together = ("job_post", "skill")

    def __str__(self):
        return f"{self.job_post} - {self.skill}"
    
class JobApplication(AbstractBaseModel):

    class StatusChoices(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        DECLINED = "declined", "Declined"
        ACCEPTED = "accepted", "Accepted"

    job_post = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        related_name="applications",
        db_index=True
    )
    caregiver = models.ForeignKey(
        'caregivers.Caregiver',
        on_delete=models.CASCADE,
        related_name="job_applications",
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        db_index=True
    )
    class Meta:
        unique_together = ("job_post", "caregiver")
    def __str__(self):        return f"{self.caregiver} - {self.job_post} ({self.status})"