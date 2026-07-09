"""Caregiver screening endpoints.

- GET /api/caregivers/screening-order/current/
- POST /api/caregivers/screening-order/manual-complete/
- POST /api/caregivers/checkr/webhook/
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.caregivers.models import Caregiver, ScreeningOrder
from apps.caregivers.permissions import IsCaregiver
from apps.caregivers.services import checkr_service
from apps.caregivers.services.screening_service import (
    ScreeningCompletionError,
    complete_screening_order,
)
from apps.users.permissions import IsPhoneVerified
from apps.utils.views.base import ResponseInfo

logger = logging.getLogger(__name__)


def _serialize_order(order: ScreeningOrder) -> dict:
    payment = order.payment
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
                "stripe_status": payment.stripe_status,
            }
            if payment is not None
            else None
        ),
    }


class CurrentScreeningOrderView(APIView):
    """Return the caregiver's current (active) screening order, if any."""

    permission_classes = [IsAuthenticated, IsCaregiver, IsPhoneVerified]

    def get(self, request):
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

        order = (
            ScreeningOrder.objects.select_related("payment")
            .filter(caregiver=caregiver)
            .order_by("-id")
            .first()
        )
        return Response(
            ResponseInfo().format_response(
                data={
                    "screening_order": _serialize_order(order) if order else None,
                },
                status_code=status.HTTP_200_OK,
                message="Current screening order fetched.",
            ),
            status=status.HTTP_200_OK,
        )


class ManualScreeningCompletionView(APIView):
    """Manually complete a bypassed screening order after Stripe authorization."""

    permission_classes = [IsAuthenticated, IsCaregiver, IsPhoneVerified]

    def post(self, request):
        if not settings.CHECKR_MANUAL_BYPASS_ENABLED:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_403_FORBIDDEN,
                    message="Manual screening completion is disabled.",
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

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

        order = (
            ScreeningOrder.objects.select_related("payment")
            .filter(caregiver=caregiver)
            .exclude(status__in=ScreeningOrder.TERMINAL_STATUSES)
            .order_by("-id")
            .first()
        )
        if order is None:
            return Response(
                ResponseInfo().format_response(
                    data={},
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="No active screening order found.",
                ),
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            order = complete_screening_order(order)
        except ScreeningCompletionError as exc:
            order.refresh_from_db()
            return Response(
                ResponseInfo().format_response(
                    data={"screening_order": _serialize_order(order)},
                    status_code=status.HTTP_409_CONFLICT,
                    message=str(exc),
                ),
                status=status.HTTP_409_CONFLICT,
            )

        order.refresh_from_db()
        return Response(
            ResponseInfo().format_response(
                data={"screening_order": _serialize_order(order)},
                status_code=status.HTTP_200_OK,
                message="Screening completed manually.",
            ),
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class CheckrWebhookView(APIView):
    """Receive Checkr webhook events. Reacts to `invitation.completed`."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        if not checkr_service.verify_checkr_webhook(request):
            logger.warning("Checkr webhook rejected: bad signature")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        event_type = (
            request.data.get("type") or request.data.get("event_type") or ""
        )
        data = request.data.get("data") or {}
        obj = data.get("object") or data

        if event_type == "invitation.completed":
            invitation_id = obj.get("id") or request.data.get("id")
            self._handle_invitation_completed(invitation_id)
        else:
            logger.info("Unhandled checkr event: %s", event_type)

        return Response({"received": True}, status=status.HTTP_200_OK)

    def _handle_invitation_completed(self, invitation_id: str | None):
        if not invitation_id:
            return
        try:
            order = ScreeningOrder.objects.get(checkr_invitation_id=invitation_id)
        except ScreeningOrder.DoesNotExist:
            logger.warning(
                "Checkr invitation.completed for unknown invitation %s",
                invitation_id,
            )
            return

        try:
            complete_screening_order(order)
        except ScreeningCompletionError as exc:
            logger.warning(
                "Could not complete screening order=%s from Checkr webhook: %s",
                order.id,
                exc,
            )
