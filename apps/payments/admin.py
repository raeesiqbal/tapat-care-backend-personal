from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "purpose",
        "status",
        "amount",
        "currency",
        "stripe_payment_intent_id",
        "created_at",
    )
    list_filter = ("status", "purpose", "provider")
    search_fields = (
        "user__email",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    )
    readonly_fields = ("created_at", "updated_at")
