from django.contrib import admin

from .models import JobPost, JobApplication, JobRequiredSkill


class JobRequiredSkillInline(admin.TabularInline):
    model = JobRequiredSkill
    extra = 0
    autocomplete_fields = ("skill",)
    readonly_fields = ("created_at", "updated_at")


class JobApplicationInline(admin.TabularInline):
    model = JobApplication
    extra = 0
    autocomplete_fields = ("caregiver",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "careseeker",
        "created_by_user",
        "status",
        "start_at",
        "end_at",
    )
    list_filter = ("status", "start_at")
    search_fields = ("title", "careseeker__careseeker_user__email")
    date_hierarchy = "start_at"
    autocomplete_fields = ("careseeker", "created_by_user", "careseeker_address")
    readonly_fields = ("created_at", "updated_at")
    inlines = [JobRequiredSkillInline, JobApplicationInline]


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("job_post", "caregiver", "status", "created_at")
    list_filter = ("status",)
    search_fields = (
        "job_post__title",
        "caregiver__user__email",
    )
    autocomplete_fields = ("job_post", "caregiver")
    readonly_fields = ("created_at", "updated_at")


@admin.register(JobRequiredSkill)
class JobRequiredSkillAdmin(admin.ModelAdmin):
    list_display = ("job_post", "skill", "created_at")
    search_fields = ("job_post__title", "skill__name")
    autocomplete_fields = ("job_post", "skill")
    readonly_fields = ("created_at", "updated_at")
