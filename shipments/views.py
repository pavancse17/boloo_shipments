from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView 
from sync import constants
from sync.models import SellerEndPointTracker

from .models import Seller
from .serializers import SellerSerializer, ShipmentSerializer


class SellerViewSet(viewsets.ModelViewSet):
    serializer_class = SellerSerializer
    queryset = Seller.objects.all()

    @action(detail=True, methods=["post"])
    def sync(self, request, *args, **kwargs):
        seller = self.get_object()

        _, shipment_sync_created = SellerEndPointTracker.objects.get_or_create(
            seller=seller,
            end_point_name=constants.SHIPMENT_LIST_ENDPOINT_NAME,
            defaults={"remaining_req_limit": 7, "limit_reset_at": now()},
        )
        SellerEndPointTracker.objects.get_or_create(
            seller=seller,
            end_point_name=constants.SHIPMENT_DETAIL_ENDPOINT_NAME,
            defaults={"remaining_req_limit": 14, "limit_reset_at": now()},
        )
        schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.MINUTES)
        PeriodicTask.objects.get_or_create(
            interval=schedule, name="Sync End Points", task="sync.tasks.SyncEndPoints"
        )

        if shipment_sync_created:
            return Response({"message": "Shipments Sync Will Start within 1 minute."})

        return Response({"message": "Shipments Sync already started. Please wait for 1 minute"})

    @action(detail=True, methods=["get"])
    def shipments(self, request, *args, **kwargs):
        seller = self.get_object()
        queryset = seller.shipments.all()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ShipmentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ShipmentSerializer(queryset, many=True)
        return Response(serializer.data)


class ShipmentCreateView(CreateAPIView):
    serializer_class = ShipmentSerializer
