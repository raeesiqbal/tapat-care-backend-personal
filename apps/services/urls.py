from rest_framework.routers import DefaultRouter
from apps.services.views.services_viewset import ServiceViewSet
from apps.services.views.services_category_viewset import ServiceCategoriesViewSet

app_name = "services"

router = DefaultRouter()
router.register("services", ServiceViewSet, basename="services")
router.register("categories", ServiceCategoriesViewSet, basename="service-categories")

urlpatterns = router.urls