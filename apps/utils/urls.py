from rest_framework.routers import DefaultRouter
from apps.utils.views.home_viewset import HomeViewSet

router = DefaultRouter()
router.register("", HomeViewSet, basename="home")
app_name = "utils"

urlpatterns = []

urlpatterns = urlpatterns + router.urls
