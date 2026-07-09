"""
URL configuration for tapat_care project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from apps.careseekers.views.careseeker_viewset import CareSeekerViewSet
from apps.users.views import OAuthTokenView
from apps.caregivers.views.qualifications_experience_views import (
    CaregiverQualificationsExperienceOptionsView,
    CaregiverQualificationsExperienceView,
)

schema_view = get_schema_view(
    openapi.Info(
        title="Tapat Care API",
        default_version="v1",
        description="Swagger API docs for Tapat Care project",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path(
        "api/onboarding/careseeker/care-needs/",
        CareSeekerViewSet.as_view(
            {
                "get": "care_needs",
                "put": "care_needs",
                "patch": "care_needs",
            }
        ),
        name="careseeker-care-needs-onboarding",
    ),
    path("api/auth/token/", OAuthTokenView.as_view(), name="auth_token_create"),
    path("api/auth/", include("drf_social_oauth2.urls", namespace="drf")),
    path(
        "api/onboarding/caregiver/qualifications-experience/",
        CaregiverQualificationsExperienceView.as_view(),
        name="caregiver-qualifications-experience",
    ),
    path(
        "api/onboarding/caregiver/qualifications-experience/options/",
        CaregiverQualificationsExperienceOptionsView.as_view(),
        name="caregiver-qualifications-experience-options",
    ),
    path("api/users/", include("apps.users.urls", namespace="users")),
    path("api/services/", include("apps.services.urls", namespace="services")),
    path("api/caregivers/", include("apps.caregivers.urls", namespace="caregivers")),
    path("api/careseekers/",include("apps.careseekers.urls",namespace="careseekers")),
    path("api/payments/", include("apps.payments.urls", namespace="payments")),
    # Password Reset URL
    path(
        "api/password-reset/",
        include("django_rest_passwordreset.urls", namespace="password_reset"),
    ),
]
