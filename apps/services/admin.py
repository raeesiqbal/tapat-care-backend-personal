from django.contrib import admin

from .models import Service, ServiceCategory


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ("name", "is_new", "is_active")
    readonly_fields = ("slug", "created_at", "updated_at")


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_new", "is_active", "created_at")
    list_filter = ("is_new", "is_active")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ServiceInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "service_category",
        "is_new",
        "is_active",
        "created_at",
    )
    list_filter = ("is_new", "is_active", "service_category")
    search_fields = ("name", "slug", "service_category__name")
    autocomplete_fields = ("service_category",)
    readonly_fields = ("created_at", "updated_at", "slug")