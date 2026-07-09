"""Checkr hosted-invitation flow.

We use Checkr's hosted invitations so the caregiver completes their identity
fields, consent, and SSN directly with Checkr - we never collect that data.

Endpoints used (Checkr v1 REST API):
- POST https://api.checkr.com/v1/candidates
- POST https://api.checkr.com/v1/invitations
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings

if TYPE_CHECKING:
    from apps.caregivers.models import Caregiver, ScreeningOrder

logger = logging.getLogger(__name__)

CHECKR_API_BASE = "https://api.checkr.com/v1"


def _auth():
    return (settings.CHECKR_API_KEY, "")


def get_or_create_checkr_candidate(caregiver: "Caregiver") -> str:
    """Return Checkr candidate id for caregiver, creating if needed."""
    if caregiver.checkr_candidate_id:
        return caregiver.checkr_candidate_id

    user = caregiver.user
    payload = {
        "email": user.email,
        "first_name": (user.first_name or "").strip() or "Caregiver",
        "last_name": (user.last_name or "").strip() or "Applicant",
        "no_middle_name": True,
    }
    response = requests.post(
        f"{CHECKR_API_BASE}/candidates",
        json=payload,
        auth=_auth(),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    candidate_id = data["id"]
    caregiver.checkr_candidate_id = candidate_id
    caregiver.save(update_fields=["checkr_candidate_id", "updated_at"])
    return candidate_id


def create_checkr_invitation(screening_order: "ScreeningOrder") -> dict:
    """Create a hosted invitation for the screening order's candidate."""
    candidate_id = get_or_create_checkr_candidate(screening_order.caregiver)
    payload = {
        "candidate_id": candidate_id,
        "package": settings.CHECKR_PACKAGE_SLUG,
        "tags": [
            f"screening_order_id:{screening_order.id}",
            f"caregiver_id:{screening_order.caregiver_id}",
        ],
    }
    response = requests.post(
        f"{CHECKR_API_BASE}/invitations",
        json=payload,
        auth=_auth(),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    screening_order.checkr_invitation_id = data["id"]
    invitation_url = data.get("invitation_url") or data.get("url")
    if invitation_url:
        screening_order.invitation_url = invitation_url
    from apps.caregivers.models import ScreeningOrder as ScreeningOrderModel

    screening_order.status = ScreeningOrderModel.Status.CHECKR_INVITED
    screening_order.save(
        update_fields=[
            "checkr_invitation_id",
            "invitation_url",
            "status",
            "updated_at",
        ]
    )
    caregiver = screening_order.caregiver
    caregiver.screening_status = caregiver.ScreeningStatus.CHECKR_INVITED
    caregiver.save(update_fields=["screening_status", "updated_at"])
    return data


def verify_checkr_webhook(request) -> bool:
    """Verify Checkr webhook signature.

    Checkr signs requests using HMAC-SHA256 over the raw body with the
    webhook secret. Header: X-Checkr-Signature.
    """
    secret = settings.CHECKR_WEBHOOK_SECRET or ""
    signature_header = request.META.get("HTTP_X_CHECKR_SIGNATURE", "")
    if not secret or not signature_header:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        msg=request.body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
