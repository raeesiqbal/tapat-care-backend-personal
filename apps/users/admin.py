from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Role, UserProfile, UserRole, UserAddress


class UserAddressInline(admin.TabularInline):
    model = UserAddress
    fk_name = "user"
    extra = 0
    show_change_link = True
    fields = ("line_1", "city", "state", "zip")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "last_login",
    )
    list_filter = ("is_verified", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "phone")
    ordering = ("-date_joined",)
    inlines = [UserAddressInline]
    readonly_fields = ("email_verification_nonce",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "picture",
                    "delete_reason",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "is_verified",
                    "email_verification_nonce",
                    "email_verification_sent_at",
                    "phone_verified_at",
                    "phone_verification_sent_at",
                )
            },
        ),
        ("Billing", {"fields": ("stripe_customer_id",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "password1", "password2","first_name","last_name"),
            },
        ),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "created_at", "updated_at")
    search_fields = ("code",)
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at")
    autocomplete_fields = ("user", "role")
    search_fields = ("user__email", "role__code")
    list_select_related = ("user", "role")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "line_1", "city", "state", "zip")
    search_fields = ("user__email", "line_1", "city", "state", "zip")
    autocomplete_fields = ("user",)
    list_filter = ("state",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date_of_birth",
        "pronouns",
        "gender_identity",
        "ethnicity",
        "created_at",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "pronouns",
        "gender_identity",
        "ethnicity",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

