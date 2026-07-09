from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "careseeker",
        "caregiver",
        "status",
        "start_at",
        "end_at",
    )
    list_filter = ("status", "start_at")
    date_hierarchy = "start_at"
    search_fields = (
        "careseeker__careseeker_user__email",
        "caregiver__user__email",
        "job_post__title",
    )
    autocomplete_fields = (
        "careseeker",
        "caregiver",
        "job_post",
        "application",
    )
    readonly_fields = ("created_at", "updated_at")