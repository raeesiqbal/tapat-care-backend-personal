from rest_framework.routers import DefaultRouter
from apps.careseekers.views.careseeker_viewset import CareSeekerViewSet

app_name = "careseekers"

router = DefaultRouter()
router.register("", CareSeekerViewSet,basename="careseeker")
urlpatterns = router.urls
