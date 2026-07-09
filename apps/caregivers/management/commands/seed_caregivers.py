from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.caregivers.models import (
    Caregiver,
    CaregiverSkill,
    ScreeningOrder,
    Skill,
)
from apps.payments.models import Payment
from apps.services.models import Service, ServiceCategory
from apps.users.models import Role, User, UserAddress, UserProfile, UserRole

MIN_COUNT = 20
MAX_COUNT = 30
DEFAULT_COUNT = 24
DEMO_EMAIL_PREFIX = "demo-caregiver-"
DEMO_EMAIL_DOMAIN = "@example.com"
DEMO_PICTURE_PATH = "/assets/images/profile.png"
BASE_RANDOM_SEED = 20260701

SERVICE_BLUEPRINTS = [
    ("Companion care", ["Conversation", "Meal preparation", "Light housekeeping"]),
    ("Personal care", ["Bathing support", "Dressing", "Grooming"]),
    ("Mobility support", ["Transfers", "Walking support", "Fall prevention"]),
    ("Overnight care", ["Sleep supervision", "Bedtime routines", "Night support"]),
    ("Dementia support", ["Memory care", "Calm routines", "Redirection"]),
    ("Transportation help", ["Appointments", "Errands", "School pickup"]),
    ("Respite support", ["Family respite", "Routine coverage", "Meal support"]),
    ("Medication reminders", ["Medication reminders", "Routine tracking", "Check-ins"]),
]

SKILL_NAMES = [
    "First aid",
    "CPR",
    "Dementia care",
    "Meal prep",
    "Mobility assistance",
    "Companionship",
    "Bathing support",
    "Medication reminders",
]

LANGUAGE_POOL = [
    "English",
    "Spanish",
    "Urdu",
    "Hindi",
    "Arabic",
    "French",
    "Punjabi",
]

AVAILABILITY_BLOCKS = [
    ("Monday", "08:00", "14:00"),
    ("Tuesday", "09:00", "15:00"),
    ("Wednesday", "10:00", "16:00"),
    ("Thursday", "08:00", "13:00"),
    ("Friday", "12:00", "18:00"),
    ("Saturday", "08:00", "12:00"),
    ("Sunday", "14:00", "20:00"),
]


@dataclass(frozen=True)
class DemoCaregiverPayload:
    first_name: str
    last_name: str
    phone: str
    picture: str
    birth_date: date
    pronouns: str
    gender_identity: str
    ethnicity: str
    languages: list[str]
    line_1: str
    line_2: str
    city: str
    state: str
    zip_code: str
    headline: str
    bio: str
    hourly_rate_cents: int
    years_experience: int
    availability: list[dict[str, str]]
    services: list[str]
    skills: list[tuple[str, str]]


class Command(BaseCommand):
    help = "Seed demo caregivers for the care seeker dashboard."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help="Number of demo caregivers to seed (20-30, default: 24).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously seeded demo caregivers before recreating them.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        if count < MIN_COUNT or count > MAX_COUNT:
            raise CommandError(
                f"--count must be between {MIN_COUNT} and {MAX_COUNT}."
            )

        if options["clear"]:
            deleted = self.clear_demo_caregivers()
            self.stdout.write(
                self.style.WARNING(
                    f"Cleared {deleted} previously seeded demo caregivers."
                )
            )

        caregiver_role, _ = Role.objects.get_or_create(code="caregiver")
        services = self.ensure_services()
        skills = self.ensure_skills()

        created = 0
        updated = 0

        for index in range(1, count + 1):
            payload = self.build_payload(index)
            _, was_created = self.seed_caregiver(
                index=index,
                payload=payload,
                caregiver_role=caregiver_role,
                services=services,
                skills=skills,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {count} demo caregivers ({created} created, {updated} updated)."
            )
        )

    def clear_demo_caregivers(self) -> int:
        demo_users = User.objects.filter(email__startswith=DEMO_EMAIL_PREFIX)
        deleted_count = demo_users.count()

        ScreeningOrder.objects.filter(caregiver__user__in=demo_users).delete()
        Payment.objects.filter(
            user__in=demo_users,
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
        ).delete()
        demo_users.delete()

        return deleted_count

    def ensure_services(self) -> list[Service]:
        services: list[Service] = []
        for category_name, service_names in SERVICE_BLUEPRINTS:
            category, _ = ServiceCategory.objects.get_or_create(
                name=category_name,
                defaults={"is_new": False, "is_active": True},
            )
            for service_name in service_names:
                service, _ = Service.objects.get_or_create(
                    service_category=category,
                    name=service_name,
                    defaults={
                        "description": f"Demo service for {service_name.lower()}.",
                        "is_new": False,
                        "is_active": True,
                    },
                )
                services.append(service)
        return services

    def ensure_skills(self) -> list[Skill]:
        skills: list[Skill] = []
        for skill_name in SKILL_NAMES:
            skill, _ = Skill.objects.get_or_create(
                name=skill_name,
                defaults={"is_active": True},
            )
            skills.append(skill)
        return skills

    def build_payload(self, index: int) -> DemoCaregiverPayload:
        local_fake = Faker("en_US")
        local_fake.seed_instance(BASE_RANDOM_SEED + index)
        year_span = local_fake.random_int(min=4, max=18)
        years_experience = min(18, max(2, year_span))
        first_name = local_fake.first_name()
        last_name = local_fake.last_name()
        phone = f"+1{2025550000 + index:010d}"
        rate = 2500 + (years_experience * 175)
        languages = self.pick_languages(local_fake, minimum=2, maximum=3)
        services = self.pick_services(local_fake, minimum=3, maximum=5)
        skills = self.pick_skills(local_fake, minimum=3, maximum=5)
        availability = self.build_availability(local_fake)

        headline = f"{local_fake.word().title()} caregiver with {years_experience} years of experience"
        bio = " ".join(
            [
                f"{first_name} is a reliable caregiver who supports daily routines, companionship, and thoughtful communication.",
                f"Comfortable with {', '.join(languages[:-1]) if len(languages) > 1 else languages[0]} households and flexible scheduling.",
                f"Focuses on calm care, safety, and consistent follow-through.",
            ]
        )

        return DemoCaregiverPayload(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            picture=DEMO_PICTURE_PATH,
            birth_date=local_fake.date_of_birth(minimum_age=24, maximum_age=58),
            pronouns=local_fake.random_element(["she/her", "he/him", "they/them"]),
            gender_identity=local_fake.random_element(
                ["woman", "man", "non-binary", "prefer not to say"]
            ),
            ethnicity=local_fake.random_element(
                ["Black", "Latina", "South Asian", "White", "Middle Eastern", "Mixed"]
            ),
            languages=languages,
            line_1=local_fake.street_address(),
            line_2=local_fake.secondary_address(),
            city=local_fake.city(),
            state=local_fake.state_abbr(),
            zip_code=f"{local_fake.random_int(min=10000, max=99999)}",
            headline=headline,
            bio=bio,
            hourly_rate_cents=rate,
            years_experience=years_experience,
            availability=availability,
            services=services,
            skills=skills,
        )

    def pick_languages(self, fake: Faker, *, minimum: int, maximum: int) -> list[str]:
        count = fake.random_int(min=minimum, max=maximum)
        return fake.random_elements(LANGUAGE_POOL, length=count, unique=True)

    def pick_services(self, fake: Faker, *, minimum: int, maximum: int) -> list[str]:
        service_names = [name for _, names in SERVICE_BLUEPRINTS for name in names]
        count = fake.random_int(min=minimum, max=maximum)
        return fake.random_elements(service_names, length=count, unique=True)

    def pick_skills(self, fake: Faker, *, minimum: int, maximum: int) -> list[tuple[str, str]]:
        count = fake.random_int(min=minimum, max=maximum)
        levels = ["basic", "intermediate", "advanced"]
        selected = fake.random_elements(SKILL_NAMES, length=count, unique=True)
        return [
            (skill_name, levels[(index + fake.random_int(min=0, max=2)) % len(levels)])
            for index, skill_name in enumerate(selected)
        ]

    def build_availability(self, fake: Faker) -> list[dict[str, str]]:
        count = fake.random_int(min=3, max=5)
        slots = fake.random_elements(AVAILABILITY_BLOCKS, length=count, unique=True)
        return [
            {"day": day, "start": start, "end": end}
            for day, start, end in slots
        ]

    @transaction.atomic
    def seed_caregiver(
        self,
        *,
        index: int,
        payload: DemoCaregiverPayload,
        caregiver_role: Role,
        services: Iterable[Service],
        skills: Iterable[Skill],
    ) -> tuple[Caregiver, bool]:
        email = f"{DEMO_EMAIL_PREFIX}{index:02d}{DEMO_EMAIL_DOMAIN}"
        now = timezone.now()

        user_defaults = {
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "phone": payload.phone,
            "picture": payload.picture,
            "is_verified": True,
            "phone_verified_at": now,
        }
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults=user_defaults,
        )
        changed_fields = []
        for field, value in user_defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed_fields.append(field)
        if changed_fields:
            user.save(update_fields=changed_fields)
        if user_created:
            user.set_password("DemoCaregiver123!")
            user.save(update_fields=["password"])

        UserRole.objects.get_or_create(user=user, role=caregiver_role)
        UserRole.objects.filter(user=user).exclude(role=caregiver_role).delete()

        profile_defaults = {
            "date_of_birth": payload.birth_date,
            "pronouns": payload.pronouns,
            "gender_identity": payload.gender_identity,
            "ethnicity": payload.ethnicity,
            "languages": payload.languages,
        }
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults=profile_defaults)
        self.update_object(profile, profile_defaults, update_fields=profile_defaults.keys())

        address_defaults = {
            "line_1": payload.line_1,
            "line_2": payload.line_2,
            "city": payload.city,
            "state": payload.state,
            "zip": payload.zip_code,
            "lat": None,
            "lng": None,
        }
        address, _ = UserAddress.objects.get_or_create(
            user=user,
            line_1=payload.line_1,
            defaults=address_defaults,
        )
        self.update_object(address, address_defaults, update_fields=address_defaults.keys())
        if address.user_id != user.id:
            address.user = user
            address.save(update_fields=["user"])

        caregiver_defaults = {
            "headline": payload.headline,
            "bio": payload.bio,
            "hourly_rate_cents": payload.hourly_rate_cents,
            "years_experience": payload.years_experience,
            "availability": payload.availability,
            "onboarding_resume": {
                "status": "completed",
                "completed_steps": [
                    "account",
                    "verification",
                    "personal-details",
                    "skills-availability",
                    "screening-payment",
                    "submitted",
                ],
                "next_step": "submitted",
            },
            "screening_status": Caregiver.ScreeningStatus.APPROVED,
            "account_status": Caregiver.AccountStatus.APPROVED,
            "checkr_candidate_id": f"cand_demo_{index:02d}",
        }
        caregiver, caregiver_created = Caregiver.objects.get_or_create(
            user=user,
            defaults=caregiver_defaults,
        )
        self.update_object(
            caregiver,
            caregiver_defaults,
            update_fields=caregiver_defaults.keys(),
        )

        selected_services = list(services)[:]
        service_count = 3 + (index % 3)
        caregiver.services.set(selected_services[:service_count])

        CaregiverSkill.objects.filter(caregiver=caregiver).delete()
        skill_level_cycle = ["basic", "intermediate", "advanced"]
        for skill_index, skill in enumerate(list(skills)[: 3 + (index % 3)]):
            CaregiverSkill.objects.create(
                caregiver=caregiver,
                skill=skill,
                level=skill_level_cycle[(skill_index + index) % len(skill_level_cycle)],
            )

        payment_defaults = {
            "amount": caregiver.hourly_rate_cents or 0,
            "currency": "usd",
            "purpose": Payment.Purpose.CAREGIVER_SCREENING,
            "provider": Payment.Provider.STRIPE,
            "status": Payment.Status.CAPTURED,
            "stripe_checkout_session_id": f"cs_demo_{index:02d}",
            "stripe_payment_intent_id": f"pi_demo_{index:02d}",
            "stripe_payment_method_id": f"pm_demo_{index:02d}",
            "stripe_charge_id": f"ch_demo_{index:02d}",
            "stripe_status": "succeeded",
            "amount_capturable": 0,
            "amount_received": caregiver.hourly_rate_cents or 0,
            "authorized_at": now - timedelta(days=7),
            "captured_at": now - timedelta(days=6),
            "canceled_at": None,
            "expires_at": None,
            "failure_code": None,
            "failure_message": None,
            "metadata": {"demo_seed": True, "seed_index": index},
        }
        payment, _ = Payment.objects.get_or_create(
            user=user,
            purpose=Payment.Purpose.CAREGIVER_SCREENING,
            defaults=payment_defaults,
        )
        self.update_object(payment, payment_defaults, update_fields=payment_defaults.keys())

        order_defaults = {
            "payment": payment,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": ScreeningOrder.Status.PAYMENT_CAPTURED,
            "invitation_url": f"https://checkr.example/demo/{index:02d}",
            "checkr_invitation_id": f"inv_demo_{index:02d}",
        }
        order, _ = ScreeningOrder.objects.get_or_create(
            caregiver=caregiver,
            defaults=order_defaults,
        )
        self.update_object(order, order_defaults, update_fields=order_defaults.keys())
        if order.payment_id != payment.id:
            order.payment = payment
            order.save(update_fields=["payment"])

        return caregiver, caregiver_created

    def update_object(self, instance, values: dict, *, update_fields: Iterable[str]):
        changed_fields = []
        for field in update_fields:
            value = values[field]
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed_fields.append(field)
        if changed_fields:
            instance.save(update_fields=changed_fields)
