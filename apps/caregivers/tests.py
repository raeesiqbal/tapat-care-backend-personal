from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.caregivers.models import (
    Caregiver,
    CaregiverCertification,
    Certification,
)
from apps.utils.models import Condition, Equipment
from apps.users.models import Role, User, UserRole


@override_settings(
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class CaregiverAccountStatusEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role, _ = Role.objects.get_or_create(code="caregiver")

    def setUp(self):
        self.user = User.objects.create_user(
            email="caregiver@example.com",
            password="StrongPassword123!",
            first_name="Care",
            last_name="Giver",
        )
        UserRole.objects.create(user=self.user, role=self.role)
        self.caregiver = Caregiver.objects.create(user=self.user)

    @patch("apps.utils.services.account_status_email_service.send_email_to_user")
    def test_caregiver_approval_email_requires_both_approved(
        self, mock_send_email
    ):
        self.caregiver.account_status = Caregiver.AccountStatus.APPROVED
        self.caregiver.save(update_fields=["account_status", "updated_at"])
        self.assertEqual(mock_send_email.call_count, 0)

        self.caregiver.screening_status = Caregiver.ScreeningStatus.APPROVED
        self.caregiver.save(update_fields=["screening_status", "updated_at"])

        self.assertEqual(mock_send_email.call_count, 1)
        subject, html_message, plaintext_message, from_email, to_email = (
            mock_send_email.call_args.args
        )
        self.assertEqual(subject, "Your Tapat Care account is approved")
        self.assertEqual(from_email, "noreply@example.com")
        self.assertEqual(to_email, self.user.email)
        self.assertIn("Your account is approved", html_message)
        self.assertIn("safety screening is also approved", plaintext_message)
        self.assertIn("http://localhost:3000/dashboard", html_message)

        self.caregiver.headline = "Senior caregiver"
        self.caregiver.save(update_fields=["headline", "updated_at"])

        self.assertEqual(mock_send_email.call_count, 1)

    @patch("apps.utils.services.account_status_email_service.send_email_to_user")
    def test_caregiver_rejection_email_requires_both_rejected(
        self, mock_send_email
    ):
        self.caregiver.account_status = Caregiver.AccountStatus.REJECTED
        self.caregiver.save(update_fields=["account_status", "updated_at"])
        self.assertEqual(mock_send_email.call_count, 0)

        self.caregiver.screening_status = Caregiver.ScreeningStatus.REJECTED
        self.caregiver.save(update_fields=["screening_status", "updated_at"])

        self.assertEqual(mock_send_email.call_count, 1)
        subject, html_message, plaintext_message, from_email, to_email = (
            mock_send_email.call_args.args
        )
        self.assertEqual(subject, "Update on your Tapat Care application")
        self.assertEqual(from_email, "noreply@example.com")
        self.assertEqual(to_email, self.user.email)
        self.assertIn("Your application was not approved", html_message)
        self.assertIn("Dashboard access remains unavailable", plaintext_message)

    @patch("apps.utils.services.account_status_email_service.send_email_to_user")
    def test_caregiver_mixed_statuses_do_not_send_email(self, mock_send_email):
        self.caregiver.account_status = Caregiver.AccountStatus.APPROVED
        self.caregiver.screening_status = Caregiver.ScreeningStatus.REJECTED
        self.caregiver.save(
            update_fields=["account_status", "screening_status", "updated_at"]
        )

        self.assertEqual(mock_send_email.call_count, 0)


class CaregiverQualificationsExperienceTests(TestCase):
    endpoint = "/api/onboarding/caregiver/qualifications-experience/"

    @classmethod
    def setUpTestData(cls):
        cls.caregiver_role, _ = Role.objects.get_or_create(code="caregiver")
        cls.careseeker_role, _ = Role.objects.get_or_create(code="careseeker")

    def setUp(self):
        self.user = User.objects.create_user(
            email="qualified-caregiver@example.com",
            password="StrongPassword123!",
        )
        self.user.is_verified = True
        self.user.phone_verified_at = timezone.now()
        self.user.save(update_fields=["is_verified", "phone_verified_at"])
        UserRole.objects.create(user=self.user, role=self.caregiver_role)
        self.caregiver = Caregiver.objects.create(
            user=self.user,
            onboarding_resume={
                "status": "in_progress",
                "completed_steps": [
                    "account",
                    "verification",
                    "personal-details",
                    "skills-availability",
                ],
                "next_step": "qualifications-experience",
            },
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.certification = Certification.objects.create(
            name="Advanced Care Test",
            slug="advanced-care-test",
        )
        self.condition_item = Condition.objects.create(
            name="Condition Test",
            slug="condition_test",
        )
        self.equipment_item = Equipment.objects.create(
            name="Equipment Test",
            slug="equipment_test",
        )

    def payload(self):
        return {
            "certifications": [self.certification.id],
            "transportation": {
                "has_drivers_license": True,
                "has_car": True,
                "has_auto_insurance_registration": True,
                "transportation_comfort": "can_drive_client",
            },
            "preferences": {
                "willing_with_pets": True,
                "pet_types_comfortable": ["cats", "dogs"],
                "willing_with_smokers": False,
            },
            "condition_experience": [
                {
                    "item_id": self.condition_item.id,
                    "skill_level": "good_experience",
                }
            ],
            "equipment_experience": [
                {
                    "item_id": self.equipment_item.id,
                    "skill_level": "excellent_experience",
                }
            ],
        }

    def assert_bad_request(self, payload):
        response = self.client.put(self.endpoint, payload, format="json")
        self.assertEqual(response.status_code, 400, response.content)
        return response

    def test_required_caregiver_qualification_fields_are_enforced(self):
        payload = self.payload()
        del payload["transportation"]["has_drivers_license"]

        self.assert_bad_request(payload)

    def test_invalid_transportation_comfort_fails(self):
        payload = self.payload()
        payload["transportation"]["transportation_comfort"] = "rideshare_only"

        self.assert_bad_request(payload)

    def test_can_drive_client_requires_drivers_license(self):
        payload = self.payload()
        payload["transportation"]["has_drivers_license"] = False
        payload["transportation"]["transportation_comfort"] = "can_drive_client"

        self.assert_bad_request(payload)

    def test_errands_only_requires_drivers_license(self):
        payload = self.payload()
        payload["transportation"]["has_drivers_license"] = False
        payload["transportation"]["transportation_comfort"] = "errands_only"

        self.assert_bad_request(payload)

    def test_auto_insurance_registration_requires_car(self):
        payload = self.payload()
        payload["transportation"]["has_car"] = False
        payload["transportation"]["has_auto_insurance_registration"] = True

        self.assert_bad_request(payload)

    def test_willing_with_pets_false_clears_pet_types(self):
        payload = self.payload()
        payload["preferences"]["willing_with_pets"] = False
        payload["preferences"]["pet_types_comfortable"] = ["cats"]

        response = self.client.put(self.endpoint, payload, format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.caregiver.refresh_from_db()
        self.assertEqual(self.caregiver.pet_types_comfortable, [])
        self.assertEqual(
            response.data["data"]["preferences"]["pet_types_comfortable"],
            [],
        )

    def test_willing_with_pets_true_requires_pet_type(self):
        payload = self.payload()
        payload["preferences"]["pet_types_comfortable"] = []

        self.assert_bad_request(payload)

    def test_invalid_pet_type_fails(self):
        payload = self.payload()
        payload["preferences"]["pet_types_comfortable"] = ["cats", "birds"]

        self.assert_bad_request(payload)

    def test_duplicate_caregiver_certification_is_rejected(self):
        payload = self.payload()
        payload["certifications"] = [self.certification.id, self.certification.id]

        self.assert_bad_request(payload)

    def test_duplicate_caregiver_experience_item_is_rejected(self):
        payload = self.payload()
        payload["condition_experience"].append(
            deepcopy(payload["condition_experience"][0])
        )

        self.assert_bad_request(payload)

    def test_invalid_skill_level_fails(self):
        payload = self.payload()
        payload["condition_experience"][0]["skill_level"] = "expert"

        self.assert_bad_request(payload)

    def test_condition_experience_rejects_equipment_items(self):
        payload = self.payload()
        payload["condition_experience"][0]["item_id"] = self.equipment_item.id

        self.assert_bad_request(payload)

    def test_equipment_experience_rejects_condition_items(self):
        payload = self.payload()
        payload["equipment_experience"][0]["item_id"] = self.condition_item.id

        self.assert_bad_request(payload)

    def test_inactive_certification_cannot_be_selected(self):
        self.certification.is_active = False
        self.certification.save(update_fields=["is_active"])

        self.assert_bad_request(self.payload())

    def test_inactive_experience_item_cannot_be_selected(self):
        self.condition_item.is_active = False
        self.condition_item.save(update_fields=["is_active"])

        self.assert_bad_request(self.payload())

    def test_only_logged_in_caregiver_can_update_own_data(self):
        other_user = User.objects.create_user(
            email="careseeker@example.com",
            password="StrongPassword123!",
        )
        other_user.is_verified = True
        other_user.phone_verified_at = timezone.now()
        other_user.save(update_fields=["is_verified", "phone_verified_at"])
        UserRole.objects.create(user=other_user, role=self.careseeker_role)
        other_client = APIClient()
        other_client.force_authenticate(user=other_user)

        response = other_client.put(self.endpoint, self.payload(), format="json")

        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(
            CaregiverCertification.objects.filter(caregiver=self.caregiver).exists()
        )

    def test_successful_save_updates_onboarding_progress(self):
        response = self.client.put(self.endpoint, self.payload(), format="json")

        self.assertEqual(response.status_code, 200, response.content)
        self.caregiver.refresh_from_db()
        self.assertIn(
            "qualifications-experience",
            self.caregiver.onboarding_resume["completed_steps"],
        )
        self.assertEqual(
            self.caregiver.onboarding_resume["next_step"],
            "screening-payment",
        )
        self.assertEqual(
            response.data["data"]["onboarding"]["next_step"],
            "screening-payment",
        )

    def test_get_endpoint_returns_previously_saved_data(self):
        save_response = self.client.put(self.endpoint, self.payload(), format="json")
        self.assertEqual(save_response.status_code, 200, save_response.content)

        response = self.client.get(self.endpoint)

        self.assertEqual(response.status_code, 200, response.content)
        data = response.data["data"]
        self.assertEqual(data["certifications"][0]["id"], self.certification.id)
        self.assertEqual(
            data["transportation"]["transportation_comfort"],
            "can_drive_client",
        )
        self.assertEqual(
            data["condition_experience"][0]["skill_level"],
            "good_experience",
        )
        self.assertIn("options", data)

    def test_options_endpoint_returns_active_database_backed_options(self):
        response = self.client.get(f"{self.endpoint}options/")

        self.assertEqual(response.status_code, 200, response.content)
        option_ids = {
            option["id"] for option in response.data["data"]["certifications"]
        }
        self.assertIn(self.certification.id, option_ids)
