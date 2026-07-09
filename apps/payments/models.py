from django.conf import settings
from django.db import models

from apps.utils.models.base import AbstractBaseModel


class Payment(AbstractBaseModel):
    class Purpose(models.TextChoices):
        CAREGIVER_SCREENING = "caregiver_screening", "Caregiver screening"

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CHECKOUT_STARTED = "checkout_started", "Checkout started"
        AUTHORIZED = "authorized", "Authorized"
        CAPTURE_PENDING = "capture_pending", "Capture pending"
        CAPTURED = "captured", "Captured"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    TERMINAL_STATUSES = {"captured", "canceled", "expired", "failed"}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default="usd")
    purpose = models.CharField(
        max_length=64,
        choices=Purpose.choices,
    )
    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
        default=Provider.STRIPE,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.CREATED,
    )

    # Stripe-specific fields
    stripe_checkout_session_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    stripe_payment_method_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    stripe_charge_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_status = models.CharField(max_length=64, null=True, blank=True)

    amount_capturable = models.PositiveIntegerField(default=0)
    amount_received = models.PositiveIntegerField(default=0)

    authorized_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    failure_code = models.CharField(max_length=128, null=True, blank=True)
    failure_message = models.TextField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["purpose"]),
        ]

    def __str__(self):
        return f"Payment #{self.id} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES
