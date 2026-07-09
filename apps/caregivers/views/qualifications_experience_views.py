from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.caregivers.models import Caregiver
from apps.caregivers.permissions import IsCaregiver
from apps.caregivers.serializers.qualifications_experience import (
    QualificationsExperienceSerializer,
    qualifications_experience_options,
    serialize_qualifications_experience,
)
from apps.caregivers.views.caregiver_viewset import _normalize_resume_state
from apps.users.permissions import IsEmailVerified, IsPhoneVerified
from apps.utils.views.base import ResponseInfo


class CaregiverQualificationsExperienceView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsEmailVerified,
        IsPhoneVerified,
        IsCaregiver,
    ]

    def get(self, request, *args, **kwargs):
        caregiver = self._get_caregiver(request)
        if caregiver is None:
            return self._not_found_response()

        return self._success_response(
            data=self._response_payload(caregiver),
            message="Qualifications and experience fetched successfully.",
        )

    def put(self, request, *args, **kwargs):
        return self._save(request)

    def patch(self, request, *args, **kwargs):
        return self._save(request)

    def _save(self, request):
        caregiver = self._get_caregiver(request)
        if caregiver is None:
            return self._not_found_response()

        serializer = QualificationsExperienceSerializer(
            data=request.data,
            context={"caregiver": caregiver},
        )
        serializer.is_valid(raise_exception=True)
        caregiver = serializer.save()
        caregiver = self._get_caregiver(request)

        return self._success_response(
            data=self._response_payload(caregiver),
            message="Qualifications and experience saved successfully.",
        )

    def _get_caregiver(self, request):
        return (
            Caregiver.objects.select_related("user")
            .prefetch_related(
                "caregiver_certifications__certification",
                "caregiver_conditions__condition",
                "caregiver_equipments__equipment",
            )
            .filter(user=request.user)
            .first()
        )

    def _response_payload(self, caregiver):
        state = _normalize_resume_state(caregiver)
        if caregiver.onboarding_resume != state:
            caregiver.onboarding_resume = state
            caregiver.save(update_fields=["onboarding_resume", "updated_at"])

        return {
            **serialize_qualifications_experience(caregiver),
            "onboarding": state,
            "options": qualifications_experience_options(),
        }

    def _success_response(self, data, message):
        return Response(
            ResponseInfo().format_response(
                data=data,
                status_code=status.HTTP_200_OK,
                message=message,
            ),
            status=status.HTTP_200_OK,
        )

    def _not_found_response(self):
        return Response(
            ResponseInfo().format_response(
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
                message="Caregiver profile not found.",
            ),
            status=status.HTTP_404_NOT_FOUND,
        )


class CaregiverQualificationsExperienceOptionsView(APIView):
    permission_classes = [IsAuthenticated, IsCaregiver]

    def get(self, request, *args, **kwargs):
        return Response(
            ResponseInfo().format_response(
                data=qualifications_experience_options(),
                status_code=status.HTTP_200_OK,
                message="Qualifications and experience options fetched successfully.",
            ),
            status=status.HTTP_200_OK,
        )
