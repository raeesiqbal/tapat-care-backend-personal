from django.urls import path

from apps.payments.views import (
    CaregiverScreeningCheckoutReturnView,
    CaregiverScreeningCheckoutSessionView,
    StripeWebhookView,
)

app_name = "payments"

urlpatterns = [
    path(
        "caregiver-screening/checkout-session/",
        CaregiverScreeningCheckoutSessionView.as_view(),
        name="caregiver-screening-checkout-session",
    ),
    path(
        "caregiver-screening/checkout-return/",
        CaregiverScreeningCheckoutReturnView.as_view(),
        name="caregiver-screening-checkout-return",
    ),
    path(
        "stripe/webhook/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
]
