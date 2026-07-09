from rest_framework.routers import DefaultRouter
from apps.users.views import UserViewSet

router = DefaultRouter()
router.register("", UserViewSet, basename="user")
app_name = "users"

urlpatterns = []

urlpatterns = urlpatterns + router.urls
