import base64
from datetime import timedelta

import requests
from django.utils.timezone import now
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from requests.exceptions import HTTPError
from rest_framework import serializers

from .models import Seller, Shipment, ShipmentItem, Transport, UserData
from .utils import AccessToken


class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = ["id", "name", "client_id", "client_secret"]

    def did_credentials_changed(self, attrs):
        return (
            self.instance.client_id != attrs["client_id"]
            or self.instance.client_secret != attrs["client_secret"]
        )

    def validate_credentials(self, attrs):
        try:
            response = AccessToken.fetch(attrs["client_id"], attrs["client_secret"])
        except HTTPError as e:
            raise serializers.ValidationError(e.response.reason)

        data = response.json()
        attrs["access_token"] = data["access_token"]
        attrs["token_expires_at"] = now() + timedelta(seconds=int(data["expires_in"]))
        return attrs

    def validate(self, attrs):
        if not self.instance or self.did_credentials_changed(attrs):
            return self.validate_credentials(attrs)

        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.MINUTES)
        PeriodicTask.objects.get_or_create(
            interval=schedule, name="Refresh Access Tokens", task="shipments.tasks.RefreshAccessTokens",
        )
        return instance


class ShipmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentItem
        exclude = ["id", "shipment"]


class TransportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transport
        exclude = [
            "id",
        ]


class UserDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserData
        exclude = [
            "id",
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    shipment_items = ShipmentItemSerializer(source="items", many=True)
    transport = TransportSerializer()
    customer_details = UserDataSerializer(source="customer")
    billing_details = UserDataSerializer(source="billing", required=False)

    class Meta:
        model = Shipment
        fields = [
            "shipment_id",
            "pick_up_point",
            "shipment_date",
            "shipment_reference",
            "shipment_items",
            "transport",
            "customer_details",
            "billing_details",
        ]

    def create(self, validated_data):
        shipment_items = validated_data.pop("items")
        validated_data["seller"] = self.context["seller"]
        validated_data["transport"] = Transport.objects.create(**validated_data["transport"])
        validated_data["customer"], _ = UserData.objects.get_or_create(**validated_data["customer"])

        if validated_data.get("billing"):
            validated_data["billing"], _ = UserData.objects.get_or_create(**validated_data["billing"])

        shipment_instance = super().create(validated_data)

        shipment_item_instances = []
        for shipment_item in shipment_items:
            shipment_item["shipment"] = shipment_instance
            shipment_item_instances.append(ShipmentItem(**shipment_item))

        ShipmentItem.objects.bulk_create(shipment_item_instances)

        return shipment_instance
