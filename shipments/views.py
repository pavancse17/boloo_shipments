from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import SellerShop, ShipmentDetailSync, ShipmentSync
from .serializers import SellerShopSerializer
from .tasks import sync_sellar_shipments


class ListCreateView(generics.ListCreateAPIView):
    serializer_class = SellerShopSerializer
    queryset = SellerShop.objects.all().order_by("id")


class RetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SellerShopSerializer
    queryset = SellerShop.objects.all()


@api_view(["get"])
def start_shipments_sync(request, pk):
    sellar_shop = get_object_or_404(SellerShop, id=pk)

    sync1, sync1_created = ShipmentSync.objects.get_or_create(
        sellar=sellar_shop, defaults={"remaining_req_limit": 7, "limit_reset_at": now()}
    )
    ShipmentDetailSync.objects.get_or_create(
        sellar=sellar_shop, defaults={"remaining_req_limit": 14, "limit_reset_at": now()}
    )

    schedule, created = IntervalSchedule.objects.get_or_create(
        every=1, period=IntervalSchedule.MINUTES
    )
    PeriodicTask.objects.get_or_create(
        interval=schedule, name="Sync Shipments", task="shipments.tasks.sync_shipments"
    )
    PeriodicTask.objects.get_or_create(
        interval=schedule,
        name="Sync Detail Shipments",
        task="shipments.tasks.sync_detail_shipments",
    )

    if sync1_created:
        return Response({"message": "Shipments Sync Will Start within 1 minute."})

    return Response({"message": "Shipments Sync already started. Please wait for 1 minute"})


@api_view(["get"])
def shipments_list_view(request, pk):
    import json

    sellar_shop = get_object_or_404(SellerShop, id=pk)
    shipments_data = []

    for data in sellar_shop.shipments.values_list("data", flat=True):
        shipments_data.append(json.loads(data))

    return Response(data=shipments_data)
