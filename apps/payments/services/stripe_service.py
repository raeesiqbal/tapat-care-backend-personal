"""Stripe integration helpers for caregiver-screening payments.

Manual-capture flow:
- Create a Checkout Session with `payment_intent_data.capture_method="manual"`.
- After Checkout completes the PaymentIntent is in `requires_capture`.
- We capture only after Checkr invitation completes (webhook).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

import stripe

if TYPE_CHECKING:
    from apps.caregivers.models import ScreeningOrder
    from apps.payments.models import Payment

logger = logging.getLogger(__name__)


def _stripe_client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def normalize_stripe_object(value):
    """Convert Stripe SDK objects to plain Python dict/list values."""
    if hasattr(value, "to_dict_recursive"):
        return value.to_dict_recursive()
    if hasattr(value, "_to_dict_recursive"):
        return value._to_dict_recursive()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [normalize_stripe_object(item) for item in value]
    if isinstance(value, dict):
        return {
            key: normalize_stripe_object(item)
            for key, item in value.items()
        }
    return value


def get_or_create_stripe_customer(user) -> str:
    """Return the Stripe customer ID for the user, creating it on demand."""
    existing = getattr(user, "stripe_customer_id", None)
    if existing:
        return existing

    client = _stripe_client()
    full_name = " ".join(
        part for part in [user.first_name or "", user.last_name or ""] if part
    ).strip() or None

    customer = client.Customer.create(
        email=user.email,
        name=full_name,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer["id"]
    user.save(update_fields=["stripe_customer_id"])
    return customer["id"]


def create_screening_checkout_session(
    payment: "Payment",
    screening_order: "ScreeningOrder",
    success_url: str,
    cancel_url: str,
):
    """Create a Stripe Checkout Session for a caregiver screening payment."""
    client = _stripe_client()
    user = payment.user
    customer_id = get_or_create_stripe_customer(user)

    metadata = {
        "payment_id": str(payment.id),
        "screening_order_id": str(screening_order.id),
        "caregiver_id": str(screening_order.caregiver_id),
        "purpose": "caregiver_screening",
    }

    session = client.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        client_reference_id=str(payment.id),
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[
            {
                "price_data": {
                    "currency": payment.currency,
                    "product_data": {
                        "name": "Tapat Care safety screening",
                        "description": (
                            "Background screening fee. You are not charged "
                            "until you complete the background screening "
                            "application."
                        ),
                    },
                    "unit_amount": payment.amount,
                },
                "quantity": 1,
            },
        ],
        payment_intent_data={
            "capture_method": "manual",
            "metadata": metadata,
        },
        metadata=metadata,
    )
    return normalize_stripe_object(session)


def retrieve_checkout_session(session_id: str):
    return normalize_stripe_object(
        _stripe_client().checkout.Session.retrieve(session_id)
    )


def retrieve_payment_intent(payment_intent_id: str):
    return normalize_stripe_object(
        _stripe_client().PaymentIntent.retrieve(payment_intent_id)
    )


def capture_payment(payment: "Payment"):
    """Capture an authorized PaymentIntent for the given local Payment.

    Only attempts capture when the local status is `authorized` or
    `capture_pending`.
    """
    from apps.payments.models import Payment as PaymentModel

    if payment.status not in {
        PaymentModel.Status.AUTHORIZED,
        PaymentModel.Status.CAPTURE_PENDING,
    }:
        return None
    if not payment.stripe_payment_intent_id:
        return None

    client = _stripe_client()
    intent = normalize_stripe_object(
        client.PaymentIntent.capture(payment.stripe_payment_intent_id)
    )

    payment.stripe_status = intent.get("status")
    payment.amount_received = intent.get("amount_received") or 0
    payment.amount_capturable = intent.get("amount_capturable") or 0
    charges = (intent.get("charges") or {}).get("data") or []
    if charges:
        payment.stripe_charge_id = charges[0].get("id")
    if intent.get("status") == "succeeded":
        payment.status = PaymentModel.Status.CAPTURED
        payment.captured_at = timezone.now()
    payment.save()
    return intent


def cancel_uncaptured_payment(payment: "Payment", reason: str = "abandoned"):
    """Cancel a PaymentIntent that has not yet been captured."""
    from apps.payments.models import Payment as PaymentModel

    cancelable = {
        PaymentModel.Status.AUTHORIZED,
        PaymentModel.Status.CHECKOUT_STARTED,
        PaymentModel.Status.CAPTURE_PENDING,
    }
    if payment.status not in cancelable:
        return None
    if not payment.stripe_payment_intent_id:
        payment.status = PaymentModel.Status.CANCELED
        payment.canceled_at = timezone.now()
        payment.save(update_fields=["status", "canceled_at", "updated_at"])
        return None

    client = _stripe_client()
    try:
        intent = normalize_stripe_object(
            client.PaymentIntent.cancel(
                payment.stripe_payment_intent_id,
                cancellation_reason=reason if reason in {"duplicate", "fraudulent", "requested_by_customer", "abandoned"} else "abandoned",
            )
        )
    except stripe.error.InvalidRequestError as exc:
        logger.warning("Cancel PaymentIntent failed: %s", exc)
        intent = None

    payment.status = PaymentModel.Status.CANCELED
    payment.canceled_at = timezone.now()
    if intent:
        payment.stripe_status = intent.get("status")
    payment.save()
    return intent
