from django.db import models


class TransportationComfort(models.TextChoices):
    CAN_DRIVE_CLIENT = "can_drive_client", "Can drive client"
    ERRANDS_ONLY = "errands_only", "Errands only"
    NO_TRANSPORTATION = "no_transportation", "No transportation"


class ScreeningStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    PAYMENT_AUTHORIZED = "payment_authorized", "Payment authorized"
    CHECKR_INVITED = "checkr_invited", "Checkr invited"
    CHECKR_IN_PROGRESS = "checkr_in_progress", "Checkr in progress"
    APPROVED = "approved", "Approved"
    REVIEW_REQUIRED = "review_required", "Review required"
    REJECTED = "rejected", "Rejected"


class AccountStatus(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    REVIEW_REQUIRED = "review_required", "Review required"
    IN_REVIEW = "in_review", "In review"
    ONBOARDING_IN_PROGRESS = (
        "onboarding_in_progress",
        "Onboarding in progress",
    )


class ScreeningOrderStatus(models.TextChoices):
    PAYMENT_REQUIRED = "payment_required", "Payment required"
    PAYMENT_AUTHORIZED = "payment_authorized", "Payment authorized"
    CHECKR_INVITED = "checkr_invited", "Checkr invited"
    CHECKR_COMPLETED = "checkr_completed", "Checkr completed"
    PAYMENT_CAPTURED = "payment_captured", "Payment captured"
    EXPIRED = "expired", "Expired"
    FAILED = "failed", "Failed"


class CaregiverSkillLevel(models.TextChoices):
    BASIC = "basic", "Basic"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class CertificationVerificationStatus(models.TextChoices):
    SELF_REPORTED = "self_reported", "Self reported"
    PENDING_REVIEW = "pending_review", "Pending review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class PetType(models.TextChoices):
    CATS = "cats", "Cats"
    DOGS = "dogs", "Dogs"
    OTHER = "other", "Other"
