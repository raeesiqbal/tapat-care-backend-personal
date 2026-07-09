from django.db import models


class AccountStatus(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    REVIEW_REQUIRED = "review_required", "Review required"
    IN_REVIEW = "in_review", "In review"
    ONBOARDING_IN_PROGRESS = (
        "onboarding_in_progress",
        "Onboarding in progress",
    )


class Mobility(models.TextChoices):
    WALKS_INDEPENDENTLY = "walks_independently", "Walks independently"
    WALKS_WITH_ASSISTANCE = "walks_with_assistance", "Walks with assistance"
    WALKER = "walker", "Walker"
    CANE = "cane", "Cane"
    WHEELCHAIR = "wheelchair", "Wheelchair"
    BEDRIDDEN = "bedridden", "Bedridden"
    HOYER_LIFT = "hoyer_lift", "Hoyer lift"


class StandingAbility(models.TextChoices):
    INDEPENDENTLY = "independently", "Independently"
    WITH_ASSISTANCE = "with_assistance", "With assistance"
    NO = "no", "No"


class Continence(models.TextChoices):
    CONTINENT = "continent", "Continent"
    INCONTINENT = "incontinent", "Incontinent"


class PreferredCaregiverGender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    NO_PREFERENCE = "no_preference", "No preference"


class TransportationMode(models.TextChoices):
    CLIENT_CAR = "client_car", "Client car"
    CAREGIVER_CAR = "caregiver_car", "Caregiver car"
    UBER_LYFT = "uber_lyft", "Uber/Lyft"
    NO_TRANSPORTATION = "no_transportation", "No transportation"


class ContactPriority(models.TextChoices):
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"
