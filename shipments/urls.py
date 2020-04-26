from django.urls import path

from .views import (
    ListCreateView,
    RetrieveUpdateDestroyView,
    shipments_list_view,
    start_shipments_sync,
)

urlpatterns = [
    path("", ListCreateView.as_view(), name="sellar_list_create"),
    path("<int:pk>/", RetrieveUpdateDestroyView.as_view(), name="sellar_update_destory"),
    path("<int:pk>/sync", start_shipments_sync, name="start_shipment_sync"),
    path("<int:pk>/shipments/", shipments_list_view, name="shipments_list"),
]

app_name = "sellars"
