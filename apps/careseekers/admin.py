from django.contrib import admin

from .models import (
    Careseeker,
    CareseekerCondition,
    CareseekerEquipment,
    FamilyContact,
)


class FamilyContactInline(admin.TabularInline):
    model = FamilyContact
    extra = 0


class CareseekerConditionInline(admin.TabularInline):
    model = CareseekerCondition
    extra = 0
    autocomplete_fields = ("condition",)


class CareseekerEquipmentInline(admin.TabularInline):
    model = CareseekerEquipment
    extra = 0
    autocomplete_fields = ("equipment",)


@admin.register(Careseeker)
class CareseekerAdmin(admin.ModelAdmin):
    list_display = (
        "careseeker_user",
        "birth_date",
        "account_status",
        "mobility",
        "lives_alone",
        "driver_needed",
        "pets_at_home",
        "primary_address",
        "created_at",
    )
    search_fields = ("careseeker_user__email", "primary_address__line_1")
    list_filter = (
        "account_status",
        "birth_date",
        "mobility",
        "lives_alone",
        "driver_needed",
        "pets_at_home",
    )
    autocomplete_fields = ("careseeker_user", "primary_address")
    readonly_fields = ("created_at", "updated_at")
    inlines = (
        FamilyContactInline,
        CareseekerConditionInline,
        CareseekerEquipmentInline,
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "careseeker_user",
                    "birth_date",
                    "primary_address",
                    "account_status",
                    "onboarding_resume",
                )
            },
        ),
        (
            "Care needs",
            {
                "fields": (
                    "lives_alone",
                    "mobility",
                    "can_stand",
                    "lifting_required",
                    "lifting_level",
                    "continence",
                    "medication_reminder_needed",
                    "preferred_caregiver_gender",
                    "driver_needed",
                    "transportation_mode",
                    "pets_at_home",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )


@admin.register(FamilyContact)
class FamilyContactAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "careseeker",
        "relationship",
        "contact_priority",
        "phone",
        "email",
    )
    search_fields = ("name", "email", "phone", "careseeker__careseeker_user__email")
    list_filter = ("contact_priority", "relationship")
    autocomplete_fields = ("careseeker",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(CareseekerCondition)
class CareseekerConditionAdmin(admin.ModelAdmin):
    list_display = ("careseeker", "condition", "condition_stage", "created_at")
    search_fields = (
        "careseeker__careseeker_user__email",
        "condition__name",
        "condition__slug",
    )
    list_filter = ("condition", "condition_stage")
    autocomplete_fields = ("careseeker", "condition")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CareseekerEquipment)
class CareseekerEquipmentAdmin(admin.ModelAdmin):
    list_display = ("careseeker", "equipment", "skill_level", "created_at")
    search_fields = (
        "careseeker__careseeker_user__email",
        "equipment__name",
        "equipment__slug",
    )
    list_filter = ("equipment", "skill_level")
    autocomplete_fields = ("careseeker", "equipment")
    readonly_fields = ("created_at", "updated_at")
