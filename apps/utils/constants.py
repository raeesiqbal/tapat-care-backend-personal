from django.db import models


class ConditionStage(models.TextChoices):
    BEGINNING = "beginning", "Beginning"
    INTERMEDIATE = "intermediate", "Intermediate"
    END = "end", "End"
    NONE_UNKNOWN = "none_unknown", "None/Unknown"


class ExperienceLevel(models.TextChoices):
    NO_EXPERIENCE = "no_experience", "No experience"
    SOME_EXPERIENCE = "some_experience", "Some experience"
    GOOD_EXPERIENCE = "good_experience", "Good experience"
    EXCELLENT_EXPERIENCE = "excellent_experience", "Excellent experience"
