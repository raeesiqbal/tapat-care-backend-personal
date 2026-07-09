from unittest.mock import patch
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
from django_rest_passwordreset.models import ResetPasswordToken
from oauth2_provider.models import AccessToken, Application, RefreshToken
from rest_framework.test import APIClient

from apps.caregivers.models import Caregiver
from apps.users.models import Role, User, UserRole
from apps.utils.services.email_verification_service import (
    EmailVerificationExpired,
    EmailVerificationInvalid,
    send_verification_email,
    verify_email_and_issue_session,
)
from apps.utils.services.phone_verification_service import (
    PhoneVerificationInvalidCode,
    check_phone_verification,
    send_phone_verification,
)


@override_settings(
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="Tapat Care <test@example.com>",
    EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS=86400,
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS=0,
)
class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="caregiver@example.com",
            password="StrongPassword123!",
        )
        self.caregiver = Caregiver.objects.create(
            user=self.user,
            onboarding_resume={
                "status": "in_progress",
                "completed_steps": ["account"],
                "next_step": "verification",
            },
        )
        self.application = Application.objects.create(
            client_id="test-client",
            client_secret="test-secret",
            hash_client_secret=False,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_PASSWORD,
            name="Test frontend",
        )

    @staticmethod
    def _token_from_mock(mock_send):
        plaintext = mock_send.call_args.args[2]
        verification_url = next(
            line.strip()
            for line in plaintext.splitlines()
            if line.strip().startswith("http")
        )
        return parse_qs(urlparse(verification_url).query)["token"][0]

    @patch(
        "apps.utils.services.email_verification_service.send_email_to_user"
    )
    def test_verification_marks_email_and_issues_oauth_session(self, mock_send):
        send_verification_email(self.user, enforce_cooldown=False)
        token = self._token_from_mock(mock_send)

        user, oauth_session, verification_status = verify_email_and_issue_session(
            token,
            "test-client",
        )

        user.refresh_from_db()
        self.caregiver.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertIsNotNone(user.email_verification_nonce)
        self.assertIn("access_token", oauth_session)
        self.assertIn("refresh_token", oauth_session)
        self.assertEqual(verification_status, "verified")
        self.assertEqual(
            self.caregiver.onboarding_resume["completed_steps"],
            ["account", "verification"],
        )
        self.assertEqual(
            self.caregiver.onboarding_resume["next_step"],
            "personal-details",
        )

    @patch(
        "apps.utils.services.email_verification_service.send_email_to_user"
    )
    def test_resending_rotates_and_invalidates_previous_link(self, mock_send):
        send_verification_email(self.user, enforce_cooldown=False)
        first_token = self._token_from_mock(mock_send)
        send_verification_email(self.user, enforce_cooldown=False)
        second_token = self._token_from_mock(mock_send)

        self.assertNotEqual(first_token, second_token)
        with self.assertRaises(EmailVerificationInvalid):
            verify_email_and_issue_session(first_token, "test-client")

        verified_user, _, verification_status = verify_email_and_issue_session(
            second_token,
            "test-client",
        )
        self.assertTrue(verified_user.is_verified)
        self.assertEqual(verification_status, "verified")

    @patch(
        "apps.utils.services.email_verification_service.send_email_to_user"
    )
    def test_verified_user_can_reuse_the_same_link_to_resume_onboarding(self, mock_send):
        send_verification_email(self.user, enforce_cooldown=False)
        token = self._token_from_mock(mock_send)

        verify_email_and_issue_session(token, "test-client")
        verified_user, oauth_session, verification_status = verify_email_and_issue_session(
            token,
            "test-client",
        )

        self.assertTrue(verified_user.is_verified)
        self.assertIn("access_token", oauth_session)
        self.assertEqual(verification_status, "already_verified")

    def test_unverified_user_can_receive_password_grant_token(self):
        response = APIClient().post(
            "/api/auth/token/",
            {
                "username": self.user.email,
                "password": "StrongPassword123!",
                "grant_type": "password",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.data)

    def test_wrong_password_does_not_expose_verification_state(self):
        response = APIClient().post(
            "/api/auth/token/",
            {
                "username": self.user.email,
                "password": "wrong-password",
                "grant_type": "password",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.data.get("error"), "email_not_verified")

    def test_get_me_includes_account_type(self):
        self.user.is_verified = True
        self.user.first_name = "Sarah"
        self.user.last_name = "Mitchell"
        self.user.save(update_fields=["is_verified", "first_name", "last_name"])
        caregiver_role, _ = Role.objects.get_or_create(code="caregiver")
        UserRole.objects.get_or_create(user=self.user, role=caregiver_role)

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get("/api/users/me/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["data"]["account_type"], "caregiver")
        self.assertIn("caregiver", response.data["data"]["roles"])
        self.assertEqual(response.data["data"]["full_name"], "Sarah Mitchell")

    @patch("apps.users.views.send_email_to_user")
    def test_update_password_rejects_wrong_current_password(self, mock_send):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(
            "/api/users/update-password/",
            {
                "old_password": "WrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            response.data["data"]["old_password"],
            ["Current password is incorrect."],
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("StrongPassword123!"))
        mock_send.assert_not_called()

    @patch("apps.users.views.send_email_to_user")
    def test_update_password_rejects_weak_new_password(self, mock_send):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(
            "/api/users/update-password/",
            {
                "old_password": "StrongPassword123!",
                "new_password": "weak",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("new_password", response.data["data"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("StrongPassword123!"))
        mock_send.assert_not_called()

    def test_reset_password_confirm_rejects_weak_password(self):
        reset_token = ResetPasswordToken.objects.create(user=self.user)

        response = APIClient().post(
            "/api/password-reset/confirm/",
            {
                "token": reset_token.key,
                "password": "weak",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(
            response.data["password"],
            [
                (
                    "Password must include at least 12 characters long, "
                    "at least one uppercase letter, at least one number, "
                    "and at least one special character."
                )
            ],
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("StrongPassword123!"))

    @patch("apps.users.views.send_email_to_user")
    def test_update_password_changes_password_revokes_tokens_and_sends_email(
        self,
        mock_send,
    ):
        access_token = AccessToken.objects.create(
            user=self.user,
            application=self.application,
            token="access-1",
            expires=timezone.now() + timedelta(hours=1),
            scope="read write",
        )
        RefreshToken.objects.create(
            user=self.user,
            application=self.application,
            token="refresh-1",
            access_token=access_token,
        )

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(
            "/api/users/update-password/",
            {
                "old_password": "StrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
            HTTP_X_CLIENT_USER_AGENT=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        self.assertFalse(AccessToken.objects.filter(user=self.user).exists())
        self.assertFalse(RefreshToken.objects.filter(user=self.user).exists())
        mock_send.assert_called_once()
        self.assertIn("Chrome on Windows", mock_send.call_args.args[2])
        self.assertIn("Tapat Care Security", mock_send.call_args.args[2])

    @patch("apps.users.views.send_email_to_user", side_effect=Exception("email down"))
    def test_update_password_keeps_success_when_security_email_fails(
        self,
        _mock_send,
    ):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(
            "/api/users/update-password/",
            {
                "old_password": "StrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))

    @patch(
        "apps.utils.services.email_verification_service.send_email_to_user"
    )
    @override_settings(EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS=-1)
    def test_expired_link_returns_the_email_for_recovery(self, mock_send):
        send_verification_email(self.user, enforce_cooldown=False)
        token = self._token_from_mock(mock_send)

        with self.assertRaises(EmailVerificationExpired) as context:
            verify_email_and_issue_session(token, "test-client")

        self.assertEqual(context.exception.email, self.user.email)

    def test_register_caregiver_rejects_weak_password(self):
        response = APIClient().post(
            "/api/users/register-caregiver/",
            {
                "email": "new-caregiver@example.com",
                "password": "weak",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(
            User.objects.filter(email__iexact="new-caregiver@example.com").exists()
        )

    @patch("apps.users.views.send_phone_verification")
    def test_send_phone_verification_returns_masked_phone(self, mock_send_phone):
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.save(update_fields=["is_verified", "phone"])
        mock_send_phone.return_value = {
            "phone": "+13472189042",
            "masked_phone": "+1***-***-9042",
            "retry_after": 60,
            "status": "pending",
        }

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            "/api/users/send-phone-verification/",
            {"phone": "(347) 218-9042"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["data"]["phone"], "+13472189042")
        self.assertEqual(response.data["data"]["masked_phone"], "+1***-***-9042")

    @patch("apps.users.views.check_phone_verification")
    def test_verify_phone_marks_phone_verified(self, mock_check_phone):
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.save(update_fields=["is_verified", "phone"])

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            "/api/users/verify-phone/",
            {"phone": "+13472189042", "code": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.caregiver.refresh_from_db()
        self.assertIsNotNone(self.user.phone_verified_at)
        self.assertEqual(
            self.caregiver.onboarding_resume["next_step"],
            "personal-details",
        )
        mock_check_phone.assert_called_once()

    @override_settings(PHONE_VERIFICATION_MODE="development")
    def test_development_phone_verification_stores_and_accepts_terminal_code(self):
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])

        with patch("builtins.print") as mock_print:
            result = send_phone_verification(self.user, "+13472189042")

        self.assertEqual(result["phone"], "+13472189042")
        printed_lines = [call.args[0] for call in mock_print.call_args_list if call.args]
        code_line = next(
            line for line in printed_lines if str(line).startswith("Code: ")
        )
        code = code_line.split("Code: ", 1)[1]

        verification_result = check_phone_verification(
            self.user,
            "+13472189042",
            code,
        )

        self.assertEqual(verification_result["status"], "approved")
        self.assertIsNone(cache.get(f"phone-verification:{self.user.pk}:+13472189042"))

    @override_settings(PHONE_VERIFICATION_MODE="development")
    def test_development_phone_verification_rejects_wrong_code(self):
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])
        send_phone_verification(self.user, "+13472189042")

        with self.assertRaisesMessage(
            PhoneVerificationInvalidCode,
            "The verification code is incorrect.",
        ):
            check_phone_verification(self.user, "+13472189042", "000000")

    @override_settings(PHONE_VERIFICATION_MODE="development")
    def test_reset_phone_verification_unlinks_verified_phone(self):
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.phone_verified_at = timezone.now()
        self.user.save(update_fields=["is_verified", "phone", "phone_verified_at"])
        send_phone_verification(self.user, "+13472189042")

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post("/api/users/reset-phone-verification/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "")
        self.assertIsNone(self.user.phone_verified_at)
        self.assertIsNone(self.user.phone_verification_sent_at)
        self.assertIsNone(cache.get(f"phone-verification:{self.user.pk}:+13472189042"))

    def test_update_profile_rejected_when_phone_unverified(self):
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.phone_verified_at = None
        self.user.save(update_fields=["is_verified", "phone", "phone_verified_at"])

        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(
            "/api/caregivers/update-profile/",
            {
                "profile": {
                    "fullName": "Care Giver",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.content)
