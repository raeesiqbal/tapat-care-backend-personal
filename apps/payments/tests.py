"""Tests for caregiver-screening payment flow.

These tests stub Stripe and Checkr SDK calls so they run offline.
"""
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.caregivers.models import Caregiver, ScreeningOrder
from apps.payments.models import Payment
from apps.payments.services import fulfillment
from apps.users.models import Role, UserRole

User = get_user_model()


def _login(client: APIClient, user) -> None:
    client.force_authenticate(user=user)


@override_settings(
    STRIPE_SECRET_KEY="sk_test_dummy",
    STRIPE_WEBHOOK_SECRET="whsec_dummy",
    CHECKR_API_KEY="ck_test_dummy",
    CHECKR_WEBHOOK_SECRET="whsec_checkr_dummy",
    CHECKR_PACKAGE_SLUG="tasker_standard",
    CHECKR_MANUAL_BYPASS_ENABLED=False,
    SCREENING_FEE_AMOUNT_CENTS=2999,
    SCREENING_FEE_CURRENCY="usd",
    FRONTEND_URL="http://localhost:3000",
)
class ScreeningPaymentFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role, _ = Role.objects.get_or_create(code="caregiver")

    def setUp(self):
        self.user = User.objects.create_user(
            email="cg@example.com",
            password="TestPass123!",
            first_name="Care",
            last_name="Giver",
        )
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.phone_verified_at = timezone.now()
        self.user.save(update_fields=["is_verified", "phone", "phone_verified_at"])
        UserRole.objects.create(user=self.user, role=self.role)
        self.caregiver = Caregiver.objects.create(user=self.user)
        self.client = APIClient()
        _login(self.client, self.user)

    # ---------- Stripe customer reuse ----------

    @patch("apps.payments.services.stripe_service.stripe.Customer.create")
    def test_stripe_customer_created_once(self, mock_create):
        mock_create.return_value = {"id": "cus_123"}
        from apps.payments.services.stripe_service import (
            get_or_create_stripe_customer,
        )

        cid1 = get_or_create_stripe_customer(self.user)
        self.user.refresh_from_db()
        cid2 = get_or_create_stripe_customer(self.user)

        self.assertEqual(cid1, "cus_123")
        self.assertEqual(cid2, "cus_123")
        mock_create.assert_called_once()

    def test_stripe_object_normalizer_handles_sdk_objects(self):
        from apps.payments.services.stripe_service import normalize_stripe_object

        session = stripe.StripeObject.construct_from(
            {"id": "cs_123", "payment_status": "paid"},
            "sk_test_dummy",
        )

        normalized = normalize_stripe_object(session)

        self.assertEqual(normalized["id"], "cs_123")
        self.assertEqual(normalized["payment_status"], "paid")

    # ---------- checkout-session creation ----------

    @patch("apps.payments.services.stripe_service.stripe.checkout.Session.create")
    @patch("apps.payments.services.stripe_service.stripe.Customer.create")
    def test_checkout_session_creates_order_and_payment(
        self, mock_customer, mock_session
    ):
        mock_customer.return_value = {"id": "cus_123"}
        mock_session.return_value = {
            "id": "cs_test_1",
            "url": "https://checkout.stripe.com/c/pay/cs_test_1",
        }

        url = "/api/payments/caregiver-screening/checkout-session/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

        order = ScreeningOrder.objects.get(caregiver=self.caregiver)
        self.assertEqual(order.status, ScreeningOrder.Status.PAYMENT_REQUIRED)
        payment = order.payment
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.CHECKOUT_STARTED)
        self.assertEqual(payment.stripe_checkout_session_id, "cs_test_1")
        self.assertEqual(payment.amount, 2999)

        kwargs = mock_session.call_args.kwargs
        self.assertEqual(
            kwargs["payment_intent_data"]["capture_method"], "manual"
        )
        self.assertEqual(kwargs["client_reference_id"], str(payment.id))

    def test_checkout_session_requires_phone_verified(self):
        self.user.phone_verified_at = None
        self.user.save(update_fields=["phone_verified_at"])

        url = "/api/payments/caregiver-screening/checkout-session/"
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, 403, response.content)

    # ---------- fulfillment is idempotent ----------

    @patch("apps.caregivers.services.checkr_service.create_checkr_invitation")
    @patch("apps.caregivers.services.checkr_service.get_or_create_checkr_candidate")
    @patch(
        "apps.payments.services.stripe_service.stripe.PaymentIntent.retrieve"
    )
    def test_fulfill_authorizes_and_invites_once(
        self, mock_retrieve, mock_candidate, mock_invitation
    ):
        mock_candidate.return_value = "cand_1"

        def fake_invite(order):
            order.checkr_invitation_id = "inv_1"
            order.invitation_url = "https://checkr.example/inv_1"
            order.status = ScreeningOrder.Status.CHECKR_INVITED
            order.save()
            return {"id": "inv_1"}

        mock_invitation.side_effect = fake_invite
        mock_retrieve.return_value = {
            "id": "pi_1",
            "status": "requires_capture",
            "amount_capturable": 2999,
            "amount_received": 0,
        }

        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_checkout_session_id="cs_x",
            status=Payment.Status.CHECKOUT_STARTED,
        )
        order = ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
        )

        session = {
            "id": "cs_x",
            "payment_intent": "pi_1",
            "client_reference_id": str(payment.id),
        }
        fulfillment.fulfill_checkout_session(session)
        fulfillment.fulfill_checkout_session(session)  # idempotent

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.AUTHORIZED)
        self.assertEqual(order.status, ScreeningOrder.Status.CHECKR_INVITED)
        self.assertEqual(order.checkr_invitation_id, "inv_1")
        # Invitation creation must be called only once
        self.assertEqual(mock_invitation.call_count, 1)

    @override_settings(CHECKR_MANUAL_BYPASS_ENABLED=True)
    @patch("apps.caregivers.services.checkr_service.create_checkr_invitation")
    @patch("apps.caregivers.services.checkr_service.get_or_create_checkr_candidate")
    @patch(
        "apps.payments.services.stripe_service.stripe.PaymentIntent.retrieve"
    )
    def test_fulfill_bypasses_checkr_when_manual_bypass_enabled(
        self, mock_retrieve, mock_candidate, mock_invitation
    ):
        mock_retrieve.return_value = {
            "id": "pi_1",
            "status": "requires_capture",
            "amount_capturable": 2999,
            "amount_received": 0,
        }
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_checkout_session_id="cs_x",
            status=Payment.Status.CHECKOUT_STARTED,
        )
        order = ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
        )

        fulfillment.fulfill_checkout_session(
            {
                "id": "cs_x",
                "payment_intent": "pi_1",
                "client_reference_id": str(payment.id),
            }
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        self.caregiver.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.AUTHORIZED)
        self.assertEqual(order.status, ScreeningOrder.Status.PAYMENT_AUTHORIZED)
        self.assertEqual(
            self.caregiver.screening_status,
            Caregiver.ScreeningStatus.PAYMENT_AUTHORIZED,
        )
        self.assertFalse(order.checkr_invitation_id)
        mock_candidate.assert_not_called()
        mock_invitation.assert_not_called()

    @override_settings(CHECKR_MANUAL_BYPASS_ENABLED=True)
    @patch("apps.payments.services.stripe_service.stripe.checkout.Session.retrieve")
    @patch("apps.payments.services.stripe_service.stripe.PaymentIntent.retrieve")
    def test_checkout_return_fulfills_manual_capture_completed_session(
        self, mock_intent_retrieve, mock_session_retrieve
    ):
        mock_session_retrieve.return_value = {
            "id": "cs_x",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_1",
            "client_reference_id": "",
        }
        mock_intent_retrieve.return_value = {
            "id": "pi_1",
            "status": "requires_capture",
            "amount_capturable": 2999,
            "amount_received": 0,
        }
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_checkout_session_id="cs_x",
            status=Payment.Status.CHECKOUT_STARTED,
        )
        order = ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
            status=ScreeningOrder.Status.PAYMENT_REQUIRED,
        )

        response = self.client.post(
            "/api/payments/caregiver-screening/checkout-return/",
            {"session_id": "cs_x"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.caregiver.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.AUTHORIZED)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_1")
        self.assertEqual(order.status, ScreeningOrder.Status.PAYMENT_AUTHORIZED)
        self.assertEqual(
            self.caregiver.screening_status,
            Caregiver.ScreeningStatus.PAYMENT_AUTHORIZED,
        )

    # ---------- Checkr completion captures once ----------

    @patch("apps.caregivers.services.checkr_service.verify_checkr_webhook")
    @patch("apps.payments.services.stripe_service.stripe.PaymentIntent.capture")
    def test_checkr_completion_captures_payment_idempotent(
        self, mock_capture, mock_verify
    ):
        mock_verify.return_value = True
        mock_capture.return_value = {
            "id": "pi_1",
            "status": "succeeded",
            "amount_received": 2999,
            "amount_capturable": 0,
            "charges": {"data": [{"id": "ch_1"}]},
        }

        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_payment_intent_id="pi_1",
            status=Payment.Status.AUTHORIZED,
        )
        order = ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
            status=ScreeningOrder.Status.CHECKR_INVITED,
            checkr_invitation_id="inv_1",
        )

        url = "/api/caregivers/checkr/webhook/"
        body = {
            "type": "invitation.completed",
            "data": {"object": {"id": "inv_1"}},
        }
        r1 = self.client.post(url, body, format="json")
        r2 = self.client.post(url, body, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(mock_capture.call_count, 1)

        payment.refresh_from_db()
        order.refresh_from_db()
        self.caregiver.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CAPTURED)
        self.assertEqual(order.status, ScreeningOrder.Status.PAYMENT_CAPTURED)
        self.assertEqual(
            self.caregiver.account_status,
            Caregiver.AccountStatus.IN_REVIEW,
        )
        self.assertEqual(
            self.caregiver.screening_status,
            Caregiver.ScreeningStatus.CHECKR_IN_PROGRESS,
        )
        self.assertEqual(
            self.caregiver.onboarding_resume.get("status"), "completed"
        )
        self.assertEqual(
            self.caregiver.onboarding_resume.get("next_step"), "submitted"
        )

    @override_settings(CHECKR_MANUAL_BYPASS_ENABLED=True)
    @patch("apps.payments.services.stripe_service.stripe.PaymentIntent.capture")
    def test_manual_bypass_completion_captures_authorized_payment(
        self, mock_capture
    ):
        mock_capture.return_value = {
            "id": "pi_1",
            "status": "succeeded",
            "amount_received": 2999,
            "amount_capturable": 0,
            "charges": {"data": [{"id": "ch_1"}]},
        }
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_payment_intent_id="pi_1",
            status=Payment.Status.AUTHORIZED,
        )
        ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
            status=ScreeningOrder.Status.PAYMENT_AUTHORIZED,
        )

        response = self.client.post(
            "/api/caregivers/screening-order/manual-complete/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(mock_capture.call_count, 1)
        payment.refresh_from_db()
        order = ScreeningOrder.objects.get(payment=payment)
        self.caregiver.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CAPTURED)
        self.assertEqual(order.status, ScreeningOrder.Status.PAYMENT_CAPTURED)
        self.assertEqual(
            self.caregiver.account_status,
            Caregiver.AccountStatus.IN_REVIEW,
        )
        self.assertEqual(
            self.caregiver.screening_status,
            Caregiver.ScreeningStatus.CHECKR_IN_PROGRESS,
        )
        self.assertEqual(
            self.caregiver.onboarding_resume.get("status"), "completed"
        )

    def test_manual_bypass_completion_disabled_by_default(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_payment_intent_id="pi_1",
            status=Payment.Status.AUTHORIZED,
        )
        ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
            status=ScreeningOrder.Status.PAYMENT_AUTHORIZED,
        )

        response = self.client.post(
            "/api/caregivers/screening-order/manual-complete/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.content)

    # ---------- expired session ----------

    def test_checkout_session_expired_marks_payment_expired(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_checkout_session_id="cs_exp",
            status=Payment.Status.CHECKOUT_STARTED,
        )
        ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
        )
        fulfillment.mark_payment_expired({"id": "cs_exp"})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.EXPIRED)

    # ---------- capture failure ----------

    def test_capture_failure_marks_payment_failed(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            stripe_payment_intent_id="pi_fail",
            status=Payment.Status.AUTHORIZED,
        )
        ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
        )
        fulfillment.mark_payment_failed(
            {
                "id": "pi_fail",
                "last_payment_error": {"code": "card_declined", "message": "Declined"},
            }
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_code, "card_declined")

    # ---------- current screening order endpoint ----------

    def test_current_screening_order_endpoint(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=2999,
            currency="usd",
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            status=Payment.Status.AUTHORIZED,
        )
        ScreeningOrder.objects.create(
            caregiver=self.caregiver,
            payment=payment,
            amount=2999,
            currency="usd",
            status=ScreeningOrder.Status.CHECKR_INVITED,
            invitation_url="https://checkr.example/inv_1",
            checkr_invitation_id="inv_1",
        )
        url = reverse("caregivers:screening-order-current")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]["screening_order"]
        self.assertEqual(body["status"], "checkr_invited")
        self.assertEqual(body["invitation_url"], "https://checkr.example/inv_1")
