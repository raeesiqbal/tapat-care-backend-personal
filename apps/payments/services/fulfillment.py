"""Shared, idempotent fulfillment for the caregiver-screening payment flow.

Used by both the Stripe webhook (`checkout.session.completed`) and the
checkout-return endpoint after the redirect from Stripe Checkout.

Idempotency relies on terminal/post-processing statuses on Payment and
ScreeningOrder, plus the unique Stripe identifiers stored on Payment.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.services import stripe_service

logger = logging.getLogger(__name__)


def fulfill_checkout_session(session) -> Payment | None:
    """Process a completed Stripe Checkout Session.

    `session` is a Stripe Session object (dict-like). Idempotent: returns the
    Payment whether the session was already fulfilled or freshly fulfilled.
    """
    from apps.caregivers.models import ScreeningOrder

    session = stripe_service.normalize_stripe_object(session)
    session_id = session.get("id")
    payment_intent_id = session.get("payment_intent")
    client_reference_id = session.get("client_reference_id")

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(stripe_checkout_session_id=session_id)
            .first()
        )
        if payment is None and client_reference_id:
            try:
                payment = (
                    Payment.objects.select_for_update()
                    .filter(id=int(client_reference_id))
                    .first()
                )
            except (TypeError, ValueError):
                payment = None
        if payment is None:
            logger.warning(
                "fulfill_checkout_session: payment not found for session=%s",
                session_id,
            )
            return None

        # Already advanced past the authorize step? Idempotent return.
        if payment.status in {
            Payment.Status.AUTHORIZED,
            Payment.Status.CAPTURE_PENDING,
            Payment.Status.CAPTURED,
        }:
            return payment

        # Save PI id (and session id if discovered via reference id).
        update_fields: list[str] = []
        if payment.stripe_checkout_session_id != session_id and session_id:
            payment.stripe_checkout_session_id = session_id
            update_fields.append("stripe_checkout_session_id")
        if payment_intent_id and payment.stripe_payment_intent_id != payment_intent_id:
            payment.stripe_payment_intent_id = payment_intent_id
            update_fields.append("stripe_payment_intent_id")
        if update_fields:
            payment.save(update_fields=update_fields + ["updated_at"])

        # Pull live PI to confirm `requires_capture`.
        if payment.stripe_payment_intent_id:
            intent = stripe_service.retrieve_payment_intent(
                payment.stripe_payment_intent_id
            )
            payment.stripe_status = intent.get("status")
            payment.amount_capturable = intent.get("amount_capturable") or 0
            payment.amount_received = intent.get("amount_received") or 0
            if intent.get("status") == "requires_capture":
                payment.status = Payment.Status.AUTHORIZED
                payment.authorized_at = timezone.now()
            payment.save()

        screening_order = (
            ScreeningOrder.objects.select_for_update()
            .filter(payment=payment)
            .first()
        )
        if screening_order is None:
            logger.warning(
                "fulfill_checkout_session: no screening order for payment=%s",
                payment.id,
            )
            return payment

        if payment.status == Payment.Status.AUTHORIZED:
            if screening_order.status in {
                ScreeningOrder.Status.PAYMENT_REQUIRED,
            }:
                screening_order.status = ScreeningOrder.Status.PAYMENT_AUTHORIZED
                screening_order.save(update_fields=["status", "updated_at"])
            if (
                screening_order.caregiver.screening_status
                != screening_order.caregiver.ScreeningStatus.PAYMENT_AUTHORIZED
            ):
                caregiver = screening_order.caregiver
                caregiver.screening_status = caregiver.ScreeningStatus.PAYMENT_AUTHORIZED
                caregiver.save(update_fields=["screening_status", "updated_at"])

        if settings.CHECKR_MANUAL_BYPASS_ENABLED:
            logger.info(
                "Checkr manual bypass enabled; order=%s awaits manual completion.",
                screening_order.id,
            )
            return payment

        # Create Checkr candidate + invitation only if not already created.
        if not screening_order.checkr_invitation_id and screening_order.status in {
            ScreeningOrder.Status.PAYMENT_AUTHORIZED,
        }:
            from apps.caregivers.services import checkr_service

            try:
                checkr_service.get_or_create_checkr_candidate(
                    screening_order.caregiver
                )
                checkr_service.create_checkr_invitation(screening_order)
            except Exception as exc:  # pragma: no cover - logging
                logger.exception(
                    "Failed to create Checkr invitation for order=%s: %s",
                    screening_order.id,
                    exc,
                )
                # Leave order at payment_authorized; webhook can retry later.

    return payment


def mark_payment_expired(session) -> Payment | None:
    """Handle Stripe `checkout.session.expired`."""
    session = stripe_service.normalize_stripe_object(session)
    session_id = session.get("id")
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(stripe_checkout_session_id=session_id)
            .first()
        )
        if payment is None:
            return None
        if payment.status in {
            Payment.Status.CAPTURED,
            Payment.Status.CAPTURE_PENDING,
            Payment.Status.AUTHORIZED,
            Payment.Status.EXPIRED,
        }:
            return payment
        payment.status = Payment.Status.EXPIRED
        payment.expires_at = timezone.now()
        payment.save(update_fields=["status", "expires_at", "updated_at"])
    return payment


def mark_payment_failed(intent) -> Payment | None:
    intent = stripe_service.normalize_stripe_object(intent)
    intent_id = intent.get("id")
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(stripe_payment_intent_id=intent_id)
            .first()
        )
        if payment is None:
            return None
        if payment.status == Payment.Status.CAPTURED:
            return payment
        payment.status = Payment.Status.FAILED
        last_error = intent.get("last_payment_error") or {}
        payment.failure_code = last_error.get("code") or last_error.get("type")
        payment.failure_message = last_error.get("message") or ""
        payment.save()
        # Cascade to screening order.
        order = getattr(payment, "screening_order", None)
        if order is not None:
            from apps.caregivers.models import ScreeningOrder

            order.status = ScreeningOrder.Status.FAILED
            order.save(update_fields=["status", "updated_at"])
    return payment


def mark_payment_canceled(intent) -> Payment | None:
    intent = stripe_service.normalize_stripe_object(intent)
    intent_id = intent.get("id")
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(stripe_payment_intent_id=intent_id)
            .first()
        )
        if payment is None:
            return None
        if payment.status == Payment.Status.CAPTURED:
            return payment
        payment.status = Payment.Status.CANCELED
        payment.canceled_at = timezone.now()
        payment.save(update_fields=["status", "canceled_at", "updated_at"])
    return payment
