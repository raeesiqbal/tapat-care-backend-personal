from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.careseekers.models import (
    Careseeker,
    CareseekerCondition,
    CareseekerEquipment,
    FamilyContact,
)
from apps.utils.models import Condition, Equipment
from apps.users.models import Role, User, UserAddress, UserProfile, UserRole


@override_settings(
    FRONTEND_URL="http://localhost:3000",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class CareseekerOnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="careseeker@example.com",
            password="StrongPassword123!",
        )
        self.user.is_verified = True
        self.user.phone = "+13472189042"
        self.user.phone_verified_at = timezone.now()
        self.user.save(update_fields=["is_verified", "phone", "phone_verified_at"])

        role, _ = Role.objects.get_or_create(code="careseeker")
        UserRole.objects.get_or_create(user=self.user, role=role)
        self.careseeker = Careseeker.objects.create(
            careseeker_user=self.user,
            onboarding_resume={
                "status": "in_progress",
                "completed_steps": ["account", "verification"],
                "next_step": "personal-details",
            },
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.condition = Condition.objects.get_or_create(
            name="Dementia",
            defaults={"is_active": True},
        )[0]
        self.equipment = Equipment.objects.get_or_create(
            name="Diapers",
            slug="diapers",
            defaults={"is_active": True},
        )[0]
        self.second_equipment = Equipment.objects.get_or_create(
            name="Bedside commode",
            slug="bedside_commode",
            defaults={"is_active": True},
        )[0]

    def care_needs_payload(self, **overrides):
        payload = {
            "family_contacts": [
                {
                    "name": "Jane Doe",
                    "phone": "+1 555 123 4567",
                    "email": "jane@example.com",
                    "relationship": "Daughter",
                    "contact_priority": "primary",
                }
            ],
            "care_needs": {
                "lives_alone": True,
                "mobility": "walker",
                "can_stand": "with_assistance",
                "lifting_required": True,
                "lifting_level": "Light assistance only",
                "continence": "incontinent",
                "medication_reminder_needed": True,
                "preferred_caregiver_gender": "no_preference",
                "driver_needed": True,
                "transportation_mode": "client_car",
                "pets_at_home": False,
            },
            "equipment": [
                {
                    "equipment_id": self.equipment.id,
                    "skill_level": "some_experience",
                },
                {
                    "equipment_id": self.second_equipment.id,
                    "skill_level": "good_experience",
                },
            ],
            "conditions": [
                {
                    "condition_id": self.condition.id,
                    "condition_stage": "beginning",
                }
            ],
        }
        for key, value in overrides.items():
            if key == "care_needs":
                payload["care_needs"].update(value)
            else:
                payload[key] = value
        return payload

    def test_update_profile_completes_careseeker_onboarding(self):
        response = self.client.patch(
            "/api/careseekers/update-profile/",
            {
                "profile": {
                    "fullName": "Care Seeker",
                    "pronouns": "they/them",
                    "date_of_birth": "1990-01-15",
                    "gender_identity": "non-binary",
                    "languages": ["en", "es"],
                },
                "address": {
                    "line_1": "123 Main St",
                    "line_2": "Apt 4B",
                    "zip": "60007",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)

        self.user.refresh_from_db()
        self.careseeker.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        address = UserAddress.objects.get(user=self.user)

        self.assertEqual(self.user.first_name, "Care")
        self.assertEqual(self.user.last_name, "Seeker")
        self.assertEqual(profile.pronouns, "they/them")
        self.assertEqual(profile.gender_identity, "non-binary")
        self.assertEqual(str(profile.date_of_birth), "1990-01-15")
        self.assertEqual(profile.languages, ["en", "es"])
        self.assertEqual(address.line_1, "123 Main St")
        self.assertEqual(address.line_2, "Apt 4B")
        self.assertEqual(address.zip, "60007")
        self.assertEqual(self.careseeker.primary_address, address)
        self.assertEqual(self.careseeker.onboarding_resume["status"], "in_progress")
        self.assertEqual(self.careseeker.onboarding_resume["next_step"], "care-needs")
        self.assertEqual(
            self.careseeker.account_status,
            Careseeker.AccountStatus.ONBOARDING_IN_PROGRESS,
        )
        self.assertEqual(
            self.careseeker.onboarding_resume["completed_steps"],
            ["account", "verification", "personal-details"],
        )

    def test_onboarding_state_returns_resume_and_saved_values(self):
        profile = UserProfile.objects.create(
            user=self.user,
            date_of_birth=date(1990, 1, 15),
            pronouns="she/her",
            gender_identity="woman",
            languages=["en", "ur"],
        )
        address = UserAddress.objects.create(
            user=self.user,
            line_1="123 Main St",
            line_2="Apt 4B",
            city="Elk Grove Village",
            state="IL",
            zip="60007",
        )
        self.user.first_name = "Care"
        self.user.last_name = "Seeker"
        self.user.save(update_fields=["first_name", "last_name"])
        self.careseeker.birth_date = profile.date_of_birth
        self.careseeker.primary_address = address
        self.careseeker.onboarding_resume = {
            "status": "completed",
            "completed_steps": ["account", "verification", "personal-details"],
            "next_step": "dashboard",
        }
        self.careseeker.save(
            update_fields=["birth_date", "primary_address", "onboarding_resume"]
        )

        response = self.client.get("/api/careseekers/onboarding-state/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.data["data"]
        self.assertTrue(data["phone_verified"])
        self.assertEqual(data["account_status"], self.careseeker.account_status)
        self.assertEqual(data["onboarding"]["status"], "completed")
        self.assertEqual(data["onboarding"]["next_step"], "dashboard")
        self.assertEqual(
            data["values_by_step"]["personal-details"]["fullName"],
            "Care Seeker",
        )
        self.assertEqual(
            data["values_by_step"]["personal-details"]["birthDate"],
            "1990-01-15",
        )
        self.assertEqual(
            data["values_by_step"]["personal-details"]["languages"],
            '["en", "ur"]',
        )
        self.assertEqual(
            data["values_by_step"]["personal-details"]["line1"],
            "123 Main St",
        )

    def test_cannot_save_care_needs_without_family_contact(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(family_contacts=[]),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(FamilyContact.objects.filter(careseeker=self.careseeker).exists())

    def test_required_care_needs_fields_are_enforced(self):
        payload = self.care_needs_payload()
        del payload["care_needs"]["mobility"]

        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_invalid_family_contact_email_fails(self):
        payload = self.care_needs_payload(
            family_contacts=[
                {
                    "name": "Jane Doe",
                    "phone": "+1 555 123 4567",
                    "email": "not-an-email",
                    "relationship": "Daughter",
                    "contact_priority": "primary",
                }
            ]
        )

        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_invalid_choice_values_fail(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(care_needs={"mobility": "flies"}),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_equipment_rejects_unknown_values(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                equipment=[
                    {
                        "equipment_id": 999999,
                        "skill_level": "some_experience",
                    }
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_duplicate_equipment_is_rejected(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                equipment=[
                    {
                        "equipment_id": self.equipment.id,
                        "skill_level": "some_experience",
                    },
                    {
                        "equipment_id": self.equipment.id,
                        "skill_level": "good_experience",
                    },
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_lifting_level_is_cleared_when_lifting_not_required(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                care_needs={
                    "lifting_required": False,
                    "lifting_level": "Should be cleared",
                }
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.careseeker.refresh_from_db()
        self.assertIsNone(self.careseeker.lifting_level)

    def test_transportation_mode_is_required_when_driver_needed(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                care_needs={
                    "driver_needed": True,
                    "transportation_mode": "",
                }
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)

    def test_transportation_mode_is_cleared_when_driver_not_needed(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                care_needs={
                    "driver_needed": False,
                    "transportation_mode": "caregiver_car",
                }
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.careseeker.refresh_from_db()
        self.assertIsNone(self.careseeker.transportation_mode)

    def test_duplicate_condition_for_same_careseeker_is_rejected(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(
                conditions=[
                    {
                        "condition_id": self.condition.id,
                        "condition_stage": "beginning",
                    },
                    {
                        "condition_id": self.condition.id,
                        "condition_stage": "intermediate",
                    },
                ]
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(
            CareseekerCondition.objects.filter(careseeker=self.careseeker).exists()
        )

    def test_caregiver_cannot_update_careseeker_care_needs(self):
        caregiver = User.objects.create_user(
            email="caregiver@example.com",
            password="StrongPassword123!",
        )
        caregiver.is_verified = True
        caregiver.phone = "+13472189043"
        caregiver.phone_verified_at = timezone.now()
        caregiver.save(update_fields=["is_verified", "phone", "phone_verified_at"])
        role, _ = Role.objects.get_or_create(code="caregiver")
        UserRole.objects.get_or_create(user=caregiver, role=role)

        self.client.force_authenticate(user=caregiver)
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_successful_care_needs_save_updates_onboarding_progress(self):
        response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.careseeker.refresh_from_db()
        self.assertEqual(self.careseeker.mobility, "walker")
        self.assertEqual(self.careseeker.onboarding_resume["status"], "completed")
        self.assertEqual(self.careseeker.onboarding_resume["next_step"], "dashboard")
        self.assertIn("care-needs", self.careseeker.onboarding_resume["completed_steps"])
        self.assertEqual(self.careseeker.account_status, Careseeker.AccountStatus.APPROVED)
        self.assertEqual(
            response.data["data"]["family_contacts"][0]["email"],
            "jane@example.com",
        )
        self.assertEqual(response.data["data"]["care_needs"]["mobility"], "walker")
        self.assertEqual(
            CareseekerEquipment.objects.filter(careseeker=self.careseeker).count(),
            2,
        )

    def test_get_care_needs_returns_previously_saved_data(self):
        save_response = self.client.put(
            "/api/onboarding/careseeker/care-needs/",
            self.care_needs_payload(),
            format="json",
        )
        self.assertEqual(save_response.status_code, 200, save_response.content)

        response = self.client.get("/api/onboarding/careseeker/care-needs/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.data["data"]
        self.assertEqual(
            [item["equipment_id"] for item in data["equipment"]],
            [self.equipment.id, self.second_equipment.id],
        )
        self.assertEqual(data["family_contacts"][0]["contact_priority"], "primary")
        self.assertEqual(data["conditions"][0]["condition_id"], self.condition.id)
        self.assertTrue(
            any(
                option["id"] == self.condition.id and option["name"] == "Dementia"
                for option in data["condition_options"]
            )
        )
        self.assertTrue(
            any(
                option["id"] == self.equipment.id and option["name"] == "Diapers"
                for option in data["equipment_options"]
            )
        )
        self.assertIn("options", data)
        self.assertTrue(
            any(
                option["value"] == "walker" and option["label"] == "Walker"
                for option in data["options"]["mobility"]
            )
        )
        self.assertTrue(
            any(
                option["value"] == "beginning" and option["label"] == "Beginning"
                for option in data["options"]["condition_stages"]
            )
        )
        self.assertTrue(
            any(
                option["id"] == self.condition.id and option["name"] == "Dementia"
                for option in data["options"]["conditions"]
            )
        )

    def test_new_careseekers_start_onboarding_in_progress(self):
        careseeker = Careseeker.objects.create(careseeker_user=self.user)

        self.assertEqual(
            careseeker.account_status,
            Careseeker.AccountStatus.ONBOARDING_IN_PROGRESS,
        )

    @patch("apps.utils.services.account_status_email_service.send_email_to_user")
    def test_careseeker_welcome_email_sent_once_on_approval_transition(
        self, mock_send_email
    ):
        self.careseeker.account_status = Careseeker.AccountStatus.APPROVED
        self.careseeker.save(update_fields=["account_status", "updated_at"])

        self.assertEqual(mock_send_email.call_count, 1)
        subject, html_message, plaintext_message, from_email, to_email = (
            mock_send_email.call_args.args
        )
        self.assertEqual(subject, "Your Tapat Care account is ready")
        self.assertEqual(from_email, "noreply@example.com")
        self.assertEqual(to_email, self.user.email)
        self.assertIn("Your account is ready", html_message)
        self.assertIn("browse caregiver profiles", html_message)
        self.assertIn("subscription is required", plaintext_message)
        self.assertIn("http://localhost:3000/dashboard", html_message)

        self.careseeker.birth_date = date(1991, 2, 20)
        self.careseeker.save(update_fields=["birth_date", "updated_at"])

        self.assertEqual(mock_send_email.call_count, 1)
