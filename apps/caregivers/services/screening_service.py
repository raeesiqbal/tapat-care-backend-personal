"""Caregiver screening lifecycle helpers."""
from __future__ import annotations

import logging

from django.db import transaction

from apps.caregivers.models import Caregiver, ScreeningOrder
from apps.payments.models import Payment
from apps.payments.services import stripe_service

logger = logging.getLogger(__name__)


class ScreeningCompletionError(Exception):
    """Raised when a screening order cannot be completed."""


def complete_screening_order(order: ScreeningOrder) -> ScreeningOrder:
    """Complete a screening order and capture its authorized payment.

    The order is only advanced when Stripe Checkout already authorized the
    manual-capture PaymentIntent. This mirrors the Checkr completion webhook.
    """
    payment: Payment | None

    with transaction.atomic():
        locked_order = (
            ScreeningOrder.objects.select_for_update()
            .select_related("caregiver", "caregiver__user")
            .get(id=order.id)
        )
        if locked_order.payment_id is None:
            raise ScreeningCompletionError(
                f"Screening order {locked_order.id} has no payment to capture."
            )
        payment = Payment.objects.select_for_update().get(id=locked_order.payment_id)

        if payment.status == Payment.Status.CAPTURED:
            if locked_order.status != ScreeningOrder.Status.PAYMENT_CAPTURED:
                locked_order.status = ScreeningOrder.Status.PAYMENT_CAPTURED
                locked_order.save(update_fields=["status", "updated_at"])
            _mark_caregiver_in_review(locked_order.caregiver)
            return locked_order

        if payment.status not in {
            Payment.Status.AUTHORIZED,
            Payment.Status.CAPTURE_PENDING,
        }:
            raise ScreeningCompletionError(
                "Screening can only be completed after Stripe authorizes payment."
            )
        if not payment.stripe_payment_intent_id:
            raise ScreeningCompletionError(
                "Screening payment has no Stripe PaymentIntent to capture."
            )

        if locked_order.status not in {
            ScreeningOrder.Status.PAYMENT_AUTHORIZED,
            ScreeningOrder.Status.CHECKR_INVITED,
            ScreeningOrder.Status.CHECKR_COMPLETED,
        }:
            raise ScreeningCompletionError(
                f"Screening order is not ready for completion: {locked_order.status}."
            )

        if locked_order.status != ScreeningOrder.Status.CHECKR_COMPLETED:
            locked_order.status = ScreeningOrder.Status.CHECKR_COMPLETED
            locked_order.save(update_fields=["status", "updated_at"])

        if payment.status == Payment.Status.AUTHORIZED:
            payment.status = Payment.Status.CAPTURE_PENDING
            payment.save(update_fields=["status", "updated_at"])

    try:
        intent = stripe_service.capture_payment(payment)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Stripe capture failed for payment=%s: %s", payment.id, exc)
        payment.refresh_from_db()
        payment.status = Payment.Status.FAILED
        payment.failure_message = str(exc)
        payment.save(update_fields=["status", "failure_message", "updated_at"])
        order.refresh_from_db()
        order.status = ScreeningOrder.Status.FAILED
        order.save(update_fields=["status", "updated_at"])
        raise ScreeningCompletionError("Stripe capture failed.") from exc

    if intent is None:
        raise ScreeningCompletionError("Stripe capture could not be started.")

    payment.refresh_from_db()
    order.refresh_from_db()
    if payment.status == Payment.Status.CAPTURED:
        with transaction.atomic():
            order.status = ScreeningOrder.Status.PAYMENT_CAPTURED
            order.save(update_fields=["status", "updated_at"])
            _mark_caregiver_in_review(order.caregiver)

    return order


def _mark_caregiver_in_review(caregiver: Caregiver):
    from apps.caregivers.views.caregiver_viewset import (
        ONBOARDING_STEPS,
        _normalize_resume_state,
    )

    state = _normalize_resume_state(caregiver)
    completed = list(state["completed_steps"])
    for step in (
        "account",
        "verification",
        "personal-details",
        "skills-availability",
        "qualifications-experience",
        "screening-payment",
    ):
        if step in ONBOARDING_STEPS and step not in completed:
            completed.append(step)
    caregiver.onboarding_resume = {
        "status": "completed",
        "completed_steps": completed,
        "next_step": "submitted",
    }
    caregiver.screening_status = Caregiver.ScreeningStatus.CHECKR_IN_PROGRESS
    if caregiver.account_status == Caregiver.AccountStatus.ONBOARDING_IN_PROGRESS:
        caregiver.account_status = Caregiver.AccountStatus.IN_REVIEW
    caregiver.save(
        update_fields=[
            "onboarding_resume",
            "screening_status",
            "account_status",
            "updated_at",
        ]
    )
