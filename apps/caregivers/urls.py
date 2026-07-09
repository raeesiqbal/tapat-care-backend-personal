from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.caregivers.views.caregiver_skill_viewset import CaregiverSkillViewSet
from apps.caregivers.views.caregiver_viewset import CaregiverViewSet
from apps.caregivers.views.screening_views import (
    CheckrWebhookView,
    CurrentScreeningOrderView,
    ManualScreeningCompletionView,
)

app_name = "caregivers"

router = DefaultRouter()
router.register("caregiver-skills", CaregiverSkillViewSet, basename="caregiver-skills")
router.register("", CaregiverViewSet, basename="caregiver")

urlpatterns = [
    path(
        "screening-order/current/",
        CurrentScreeningOrderView.as_view(),
        name="screening-order-current",
    ),
    path(
        "screening-order/manual-complete/",
        ManualScreeningCompletionView.as_view(),
        name="screening-order-manual-complete",
    ),
    path(
        "checkr/webhook/",
        CheckrWebhookView.as_view(),
        name="checkr-webhook",
    ),
] + router.urls
