# Generated for careseeker care-needs onboarding.

import autoslug.fields
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def seed_conditions(apps, schema_editor):
    Condition = apps.get_model("careseekers", "Condition")
    for name in ("Alzheimer's", "Dementia", "Parkinson's", "Cancer", "Other"):
        Condition.objects.get_or_create(name=name, defaults={"is_active": True})


def unseed_conditions(apps, schema_editor):
    Condition = apps.get_model("careseekers", "Condition")
    Condition.objects.filter(
        name__in=("Alzheimer's", "Dementia", "Parkinson's", "Cancer", "Other")
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("careseekers", "0005_careseeker_account_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="careseeker",
            name="can_stand",
            field=models.CharField(
                blank=True,
                choices=[
                    ("independently", "Independently"),
                    ("with_assistance", "With assistance"),
                    ("no", "No"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="continence",
            field=models.CharField(
                blank=True,
                choices=[
                    ("continent", "Continent"),
                    ("incontinent", "Incontinent"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="driver_needed",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="lifting_level",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="lifting_required",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="lives_alone",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="medical_equipment",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="medication_reminder_needed",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="mobility",
            field=models.CharField(
                blank=True,
                choices=[
                    ("walks_independently", "Walks independently"),
                    ("walks_with_assistance", "Walks with assistance"),
                    ("walker", "Walker"),
                    ("cane", "Cane"),
                    ("wheelchair", "Wheelchair"),
                    ("bedridden", "Bedridden"),
                    ("hoyer_lift", "Hoyer lift"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="pets_at_home",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="preferred_caregiver_gender",
            field=models.CharField(
                blank=True,
                choices=[
                    ("male", "Male"),
                    ("female", "Female"),
                    ("no_preference", "No preference"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="transportation_mode",
            field=models.CharField(
                blank=True,
                choices=[
                    ("client_car", "Client car"),
                    ("caregiver_car", "Caregiver car"),
                    ("uber_lyft", "Uber/Lyft"),
                    ("no_transportation", "No transportation"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="Condition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True)),
                (
                    "slug",
                    autoslug.fields.AutoSlugField(
                        editable=False,
                        populate_from="name",
                        unique=True,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="FamilyContact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=32)),
                ("email", models.EmailField(max_length=254)),
                ("relationship", models.CharField(max_length=100)),
                (
                    "contact_priority",
                    models.CharField(
                        choices=[
                            ("primary", "Primary"),
                            ("secondary", "Secondary"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "careseeker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="family_contacts",
                        to="careseekers.careseeker",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="CareseekerCondition",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "condition_stage",
                    models.CharField(
                        choices=[
                            ("beginning", "Beginning"),
                            ("intermediate", "Intermediate"),
                            ("end", "End"),
                            ("none_unknown", "None/Unknown"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "careseeker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="careseeker_conditions",
                        to="careseekers.careseeker",
                    ),
                ),
                (
                    "condition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="careseeker_conditions",
                        to="careseekers.condition",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
                "unique_together": {("careseeker", "condition")},
            },
        ),
        migrations.AddConstraint(
            model_name="familycontact",
            constraint=models.UniqueConstraint(
                condition=models.Q(contact_priority="primary"),
                fields=("careseeker",),
                name="unique_primary_family_contact_per_careseeker",
            ),
        ),
        migrations.RunPython(seed_conditions, unseed_conditions),
    ]
