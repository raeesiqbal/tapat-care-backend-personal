from django.db import models
from django.db.models import Q

from apps.utils.models.base import AbstractBaseModel 
from apps.utils.constants import ConditionStage, ExperienceLevel
from apps.utils.models import Condition, Equipment
from apps.careseekers.constants import (
    AccountStatus as CareseekerAccountStatus,
    ContactPriority as FamilyContactPriority,
    Continence,
    Mobility,
    PreferredCaregiverGender,
    StandingAbility,
    TransportationMode,
)
# Create your models here.
class Careseeker(AbstractBaseModel):
    AccountStatus = CareseekerAccountStatus
    Mobility = Mobility
    StandingAbility = StandingAbility
    Continence = Continence
    PreferredCaregiverGender = PreferredCaregiverGender
    TransportationMode = TransportationMode

    careseeker_user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='careseeker_profile')
    birth_date = models.DateField(null=True, blank=True)
    onboarding_resume = models.JSONField(default=dict, blank=True)
    account_status = models.CharField(
        max_length=32,
        choices=CareseekerAccountStatus.choices,
        default=CareseekerAccountStatus.ONBOARDING_IN_PROGRESS,
    )
    primary_address = models.ForeignKey(
        "users.UserAddress",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_for"
    )
    lives_alone = models.BooleanField(null=True, blank=True)
    mobility = models.CharField(
        max_length=32,
        choices=Mobility.choices,
        null=True,
        blank=True,
    )
    can_stand = models.CharField(
        max_length=32,
        choices=StandingAbility.choices,
        null=True,
        blank=True,
    )
    lifting_required = models.BooleanField(null=True, blank=True)
    lifting_level = models.TextField(null=True, blank=True)
    continence = models.CharField(
        max_length=32,
        choices=Continence.choices,
        null=True,
        blank=True,
    )
    medication_reminder_needed = models.BooleanField(null=True, blank=True)
    preferred_caregiver_gender = models.CharField(
        max_length=32,
        choices=PreferredCaregiverGender.choices,
        null=True,
        blank=True,
    )
    driver_needed = models.BooleanField(null=True, blank=True)
    transportation_mode = models.CharField(
        max_length=32,
        choices=TransportationMode.choices,
        null=True,
        blank=True,
    )
    pets_at_home = models.BooleanField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.careseeker_user} - Careseeker"


class FamilyContact(AbstractBaseModel):
    ContactPriority = FamilyContactPriority

    careseeker = models.ForeignKey(
        Careseeker,
        on_delete=models.CASCADE,
        related_name="family_contacts",
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    relationship = models.CharField(max_length=100)
    contact_priority = models.CharField(
        max_length=16,
        choices=FamilyContactPriority.choices,
    )

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["careseeker"],
                condition=Q(contact_priority="primary"),
                name="unique_primary_family_contact_per_careseeker",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.contact_priority})"


class CareseekerCondition(AbstractBaseModel):
    careseeker = models.ForeignKey(
        Careseeker,
        on_delete=models.CASCADE,
        related_name="careseeker_conditions",
    )
    condition = models.ForeignKey(
        Condition,
        on_delete=models.CASCADE,
        related_name="careseeker_conditions",
    )
    condition_stage = models.CharField(
        max_length=20,
        choices=ConditionStage.choices,
    )

    class Meta:
        ordering = ["-id"]
        unique_together = ("careseeker", "condition")

    def __str__(self):
        return f"{self.careseeker} - {self.condition} ({self.condition_stage})"


class CareseekerEquipment(AbstractBaseModel):
    careseeker = models.ForeignKey(
        Careseeker,
        on_delete=models.CASCADE,
        related_name="careseeker_equipments",
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="careseeker_equipments",
    )
    skill_level = models.CharField(max_length=32, choices=ExperienceLevel.choices)

    class Meta:
        ordering = ["-id"]
        unique_together = ("careseeker", "equipment")

    def __str__(self):
        return f"{self.careseeker} - {self.equipment} ({self.skill_level})"
