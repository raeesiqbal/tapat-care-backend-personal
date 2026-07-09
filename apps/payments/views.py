"""HTTP views for the payments app.

Endpoints:
- POST /api/payments/caregiver-screening/checkout-session/
- POST /api/payments/caregiver-screening/checkout-return/
- POST /api/payments/stripe/webhook/
"""
from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.caregivers.models import Caregiver, ScreeningOrder
from apps.caregivers.permissions import IsCaregiver
from apps.payments.models import Payment
from apps.payments.services import fulfillment, stripe_service
from apps.users.permissions import IsPhoneVerified
from apps.utils.views.base import ResponseInfo

logger = logging.getLogger(__name__)


def _serialize_screening_order(order: ScreeningOrder | None, payment: Payment | None):
    if order is None:
        return None
    return {
        "id": order.id,
        "status": order.status,
        "amount": order.amount,
        "currency": order.currency,
        "invitation_url": order.invitation_url,
        "checkr_invitation_id": order.checkr_invitation_id,
        "payment": (
            {
                "id": payment.id,
                "status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
            }
            if payment is not None
            else None
        ),
    }


class CaregiverScreeningCheckoutSessionView(APIView):
    """Create or reuse the active screening order + checkout session."""

    permission_classes = [IsAuthenticated, IsCaregiver, IsPhoneVerified]

    def post(self, request):
        caregiver = (
            Caregiver.objects.select_related("user").filter(user=request.user).first()
        )
        if caregiver is None:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Caregiver profile not found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        amount = settings.SCREENING_FEE_AMOUNT_CENTS
        currency = settings.SCREENING_FEE_CURRENCY
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        success_url = (
            f"{frontend_url}/onboarding/provider/screening-payment"
            "?session_id={CHECKOUT_SESSION_ID}"
        )
        cancel_url = f"{frontend_url}/onboarding/provider/screening-payment?canceled=1"

        with transaction.atomic():
            order = (
                ScreeningOrder.objects.select_for_update()
                .filter(caregiver=caregiver)
                .exclude(status__in=ScreeningOrder.TERMINAL_STATUSES)
                .order_by("-id")
                .first()
            )
            if order is None:
                order = ScreeningOrder.objects.create(
                    caregiver=caregiver,
                    amount=amount,
                    currency=currency,
                    status=ScreeningOrder.Status.PAYMENT_REQUIRED,
                )

            payment = order.payment
            if payment is None or payment.status in {
                Payment.Status.FAILED,
                Payment.Status.EXPIRED,
                Payment.Status.CANCELED,
            }:
                payment = Payment.objects.create(
                    user=request.user,
                    amount=amount,
                    currency=currency,
                    purpose=Payment.Purpose.CAREGIVER_SCREENING,
                    provider=Payment.Provider.STRIPE,
                    status=Payment.Status.CREATED,
                )
                order.payment = payment
                order.status = ScreeningOrder.Status.PAYMENT_REQUIRED
                order.save(update_fields=["payment", "status", "updated_at"])

        try:
            session = stripe_service.create_screening_checkout_session(
                payment=payment,
                screening_order=order,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe checkout session creation failed: %s", exc)
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    message="Could not start the secure payment session.",
                ),
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.stripe_checkout_session_id = session["id"]
        payment.status = Payment.Status.CHECKOUT_STARTED
        payment.save(
            update_fields=[
                "stripe_checkout_session_id",
                "status",
                "updated_at",
            ]
        )

        return Response(
            ResponseInfo().format_response(
                data={
                    "checkout_url": session["url"],
                    "payment_id": payment.id,
                    "screening_order_id": order.id,
                },
                status_code=status.HTTP_200_OK,
                message="Checkout session created.",
            ),
            status=status.HTTP_200_OK,
        )


class CaregiverScreeningCheckoutReturnView(APIView):
    """Process the redirect back from Stripe Checkout."""

    permission_classes = [IsAuthenticated, IsCaregiver, IsPhoneVerified]

    def post(self, request):
        session_id = str(request.data.get("session_id") or "").strip()
        if not session_id:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="session_id is required.",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = stripe_service.retrieve_checkout_session(session_id)
        except stripe.error.StripeError as exc:
            logger.exception("Stripe session retrieval failed: %s", exc)
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    message="Could not verify the payment session.",
                ),
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if (
            session.get("status") == "complete"
            or session.get("payment_status") in {"paid", "no_payment_required"}
        ):
            fulfillment.fulfill_checkout_session(session)

        payment = Payment.objects.filter(
            stripe_checkout_session_id=session_id
        ).first()
        order = ScreeningOrder.objects.filter(payment=payment).first() if payment else None
        return Response(
            ResponseInfo().format_response(
                data={"screening_order": _serialize_screening_order(order, payment)},
                status_code=status.HTTP_200_OK,
                message="Checkout return processed.",
            ),
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """Receive Stripe events for the screening payment lifecycle."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=secret,
            )
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            logger.warning("Stripe webhook verification failed: %s", exc)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event = stripe_service.normalize_stripe_object(event)
        event_type = event.get("type")
        data_object = event["data"]["object"]

        if event_type == "checkout.session.completed":
            fulfillment.fulfill_checkout_session(data_object)
        elif event_type == "checkout.session.expired":
            fulfillment.mark_payment_expired(data_object)
        elif event_type == "payment_intent.payment_failed":
            fulfillment.mark_payment_failed(data_object)
        elif event_type == "payment_intent.canceled":
            fulfillment.mark_payment_canceled(data_object)
        else:
            logger.info("Unhandled stripe event type: %s", event_type)

        return Response({"received": True}, status=status.HTTP_200_OK)
