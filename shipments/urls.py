from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SellerViewSet

router = DefaultRouter()
router.register(r"", SellerViewSet)

urlpatterns = [
    path("", include(router.urls)),
]

app_name = "sellers"
