from django.contrib import admin

from .models import (
    Caregiver,
    CaregiverCertification,
    CaregiverCondition,
    CaregiverEquipment,
    CaregiverService,
    CaregiverSkill,
    Certification,
    ScreeningOrder,
    Skill,
)


class CaregiverSkillInline(admin.TabularInline):
    model = CaregiverSkill
    extra = 0
    autocomplete_fields = ("skill",)
    fields = ("skill", "level")
    readonly_fields = ("created_at", "updated_at")


class CaregiverCertificationInline(admin.TabularInline):
    model = CaregiverCertification
    extra = 0
    autocomplete_fields = ("certification",)
    fields = (
        "certification",
        "verification_status",
        "expiration_date",
        "document",
    )


class CaregiverConditionInline(admin.TabularInline):
    model = CaregiverCondition
    extra = 0
    autocomplete_fields = ("condition",)
    fields = ("condition", "skill_level")


class CaregiverEquipmentInline(admin.TabularInline):
    model = CaregiverEquipment
    extra = 0
    autocomplete_fields = ("equipment",)
    fields = ("equipment", "skill_level")


@admin.register(Caregiver)
class CaregiverAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "account_status",
        "screening_status",
        "has_drivers_license",
        "has_car",
        "transportation_comfort",
        "willing_with_pets",
        "willing_with_smokers",
        "headline",
        "hourly_rate_cents",
        "years_experience",
        "created_at",
    )
    search_fields = ("user__email", "headline")
    list_filter = (
        "account_status",
        "screening_status",
        "years_experience",
        "has_drivers_license",
        "has_car",
        "transportation_comfort",
        "willing_with_pets",
        "willing_with_smokers",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "headline",
                    "bio",
                    "hourly_rate_cents",
                    "years_experience",
                    "availability",
                    "onboarding_resume",
                )
            },
        ),
        (
            "Qualifications and experience",
            {
                "fields": (
                    "has_drivers_license",
                    "has_car",
                    "has_auto_insurance_registration",
                    "transportation_comfort",
                    "willing_with_pets",
                    "pet_types_comfortable",
                    "willing_with_smokers",
                )
            },
        ),
        (
            "Review status",
            {
                "fields": (
                    "account_status",
                    "screening_status",
                    "checkr_candidate_id",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    inlines = [
        CaregiverSkillInline,
        CaregiverCertificationInline,
        CaregiverConditionInline,
        CaregiverEquipmentInline,
    ]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CaregiverSkill)
class CaregiverSkillAdmin(admin.ModelAdmin):
    list_display = ("id", "caregiver", "skill", "level", "created_at")
    list_filter = ("level",)
    search_fields = ("caregiver__user__email", "skill__name")
    autocomplete_fields = ("caregiver", "skill")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CaregiverService)
class CaregiverServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "caregiver", "service", "created_at")
    search_fields = ("caregiver__user__email", "service__name")
    autocomplete_fields = ("caregiver", "service")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    readonly_fields = ("slug", "created_at", "updated_at")


@admin.register(CaregiverCertification)
class CaregiverCertificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "caregiver",
        "certification",
        "verification_status",
        "expiration_date",
        "created_at",
    )
    list_filter = ("verification_status", "certification__is_active")
    search_fields = ("caregiver__user__email", "certification__name", "certification__slug")
    autocomplete_fields = ("caregiver", "certification")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CaregiverCondition)
class CaregiverConditionAdmin(admin.ModelAdmin):
    list_display = ("id", "caregiver", "condition", "skill_level", "created_at")
    list_filter = ("skill_level", "condition__is_active")
    search_fields = ("caregiver__user__email", "condition__name", "condition__slug")
    autocomplete_fields = ("caregiver", "condition")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CaregiverEquipment)
class CaregiverEquipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "caregiver", "equipment", "skill_level", "created_at")
    list_filter = ("skill_level", "equipment__is_active")
    search_fields = ("caregiver__user__email", "equipment__name", "equipment__slug")
    autocomplete_fields = ("caregiver", "equipment")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ScreeningOrder)
class ScreeningOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "caregiver",
        "payment",
        "amount",
        "currency",
        "status",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "caregiver__user__email",
        "checkr_invitation_id",
        "payment__stripe_checkout_session_id",
        "payment__stripe_payment_intent_id",
    )
    autocomplete_fields = ("caregiver", "payment")
    readonly_fields = ("created_at", "updated_at")
