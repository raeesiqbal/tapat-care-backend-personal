from django.db import models
from django.conf import settings
from autoslug import AutoSlugField
from apps.utils.models.base import AbstractBaseModel 
from apps.utils.constants import ExperienceLevel
from apps.utils.models import Condition, Equipment
from apps.services.models import Service
from apps.caregivers.constants import (
    AccountStatus as CaregiverAccountStatus,
    CaregiverSkillLevel,
    CertificationVerificationStatus,
    ScreeningOrderStatus,
    ScreeningStatus,
    TransportationComfort,
)


class Caregiver(AbstractBaseModel):
    TransportationComfort = TransportationComfort
    ScreeningStatus = ScreeningStatus
    AccountStatus = CaregiverAccountStatus

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    headline = models.TextField(null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    hourly_rate_cents = models.IntegerField(null=True, blank=True)
    years_experience = models.IntegerField(null=True, blank=True)
    availability = models.JSONField(default=list, blank=True)
    onboarding_resume = models.JSONField(default=dict, blank=True)
    has_drivers_license = models.BooleanField(null=True, blank=True)
    has_car = models.BooleanField(null=True, blank=True)
    has_auto_insurance_registration = models.BooleanField(null=True, blank=True)
    transportation_comfort = models.CharField(
        max_length=32,
        choices=TransportationComfort.choices,
        null=True,
        blank=True,
    )
    willing_with_pets = models.BooleanField(null=True, blank=True)
    pet_types_comfortable = models.JSONField(default=list, blank=True)
    willing_with_smokers = models.BooleanField(null=True, blank=True)
    screening_status = models.CharField(
        max_length=32,
        choices=ScreeningStatus.choices,
        default=ScreeningStatus.NOT_STARTED,
    )
    account_status = models.CharField(
        max_length=32,
        choices=CaregiverAccountStatus.choices,
        default=CaregiverAccountStatus.ONBOARDING_IN_PROGRESS,
    )
    checkr_candidate_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    services = models.ManyToManyField(
        Service,
        through="CaregiverService",
        related_name="caregivers"
    )
    def __str__(self):
        return f"{self.user} - Caregiver"


class ScreeningOrder(AbstractBaseModel):
    Status = ScreeningOrderStatus

    TERMINAL_STATUSES = {"payment_captured", "expired", "failed"}

    caregiver = models.ForeignKey(
        Caregiver,
        on_delete=models.CASCADE,
        related_name="screening_orders",
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="screening_order",
    )
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(
        max_length=32,
        choices=ScreeningOrderStatus.choices,
        default=ScreeningOrderStatus.PAYMENT_REQUIRED,
    )
    invitation_url = models.URLField(null=True, blank=True)
    checkr_invitation_id = models.CharField(
        max_length=255, null=True, blank=True
    )

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["checkr_invitation_id"]),
        ]

    def __str__(self):
        return f"ScreeningOrder #{self.id} ({self.status})"
    
class Skill(AbstractBaseModel):
    name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CaregiverSkill(AbstractBaseModel):
    LevelChoices = CaregiverSkillLevel

    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="caregiver_skills"
    )
    caregiver = models.ForeignKey(
        Caregiver,
        on_delete=models.CASCADE,
        related_name="caregiver_skills"
    )
    level = models.CharField(
        max_length=20,
        choices=CaregiverSkillLevel.choices,
        null=False,
        blank=False
    )
    class Meta:
        unique_together = ("skill", "caregiver")

    def __str__(self):
        return f"{self.caregiver} - {self.skill} ({self.level})"
    
class CaregiverService(AbstractBaseModel):
    caregiver = models.ForeignKey(Caregiver, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("caregiver", "service")


class Certification(AbstractBaseModel):
    name = models.CharField(max_length=255, unique=True)
    slug = AutoSlugField(populate_from="name", unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CaregiverCertification(AbstractBaseModel):
    VerificationStatus = CertificationVerificationStatus

    caregiver = models.ForeignKey(
        Caregiver,
        on_delete=models.CASCADE,
        related_name="caregiver_certifications",
    )
    certification = models.ForeignKey(
        Certification,
        on_delete=models.CASCADE,
        related_name="caregiver_certifications",
    )
    verification_status = models.CharField(
        max_length=32,
        choices=CertificationVerificationStatus.choices,
        default=CertificationVerificationStatus.SELF_REPORTED,
    )
    expiration_date = models.DateField(null=True, blank=True)
    document = models.FileField(
        upload_to="caregiver_certifications/",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("caregiver", "certification")

    def __str__(self):
        return f"{self.caregiver} - {self.certification}"


class CaregiverCondition(AbstractBaseModel):
    caregiver = models.ForeignKey(
        Caregiver,
        on_delete=models.CASCADE,
        related_name="caregiver_conditions",
    )
    condition = models.ForeignKey(
        Condition,
        on_delete=models.CASCADE,
        related_name="caregiver_conditions",
    )
    skill_level = models.CharField(max_length=32, choices=ExperienceLevel.choices)

    class Meta:
        unique_together = ("caregiver", "condition")

    def __str__(self):
        return f"{self.caregiver} - {self.condition} ({self.skill_level})"


class CaregiverEquipment(AbstractBaseModel):
    caregiver = models.ForeignKey(
        Caregiver,
        on_delete=models.CASCADE,
        related_name="caregiver_equipments",
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="caregiver_equipments",
    )
    skill_level = models.CharField(max_length=32, choices=ExperienceLevel.choices)

    class Meta:
        unique_together = ("caregiver", "equipment")

    def __str__(self):
        return f"{self.caregiver} - {self.equipment} ({self.skill_level})"
