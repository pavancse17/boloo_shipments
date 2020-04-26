import base64
from datetime import timedelta

import requests
from django.utils.timezone import now
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from rest_framework import serializers

from .models import SellerShop


class SellerShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerShop
        fields = [
            "id",
            "name",
            "client_id",
            "client_secret",
        ]

    def did_credentials_changed(self, attrs):
        return (
            self.instance.client_id != attrs["client_id"]
            or self.instance.client_secret != attrs["client_secret"]
        )

    def validate_credentials(self, attrs):
        base64_credentials = base64.b64encode(
            bytes("%s:%s" % (attrs["client_id"], attrs["client_secret"]), encoding="utf8")
        )
        response = requests.post(
            url=SellerShop.BOL_AUTH_URL,
            headers={
                "Accept": "application/json",
                "Authorization": "Basic %s" % base64_credentials.decode(),
            },
        )
        if response.status_code == 200:
            attrs["access_token"] = response.json()["access_token"]
            attrs["token_expires_at"] = now() + timedelta(
                seconds=int(response.json()["expires_in"])
            )
            return attrs

        raise serializers.ValidationError("Invalid Credentials")

    def validate(self, attrs):
        if not self.instance or self.did_credentials_changed(attrs):
            return self.validate_credentials(attrs)

        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=1, period=IntervalSchedule.MINUTES
        )
        PeriodicTask.objects.get_or_create(
            interval=schedule,
            name="Refresh Access Tokens",
            task="shipments.tasks.refresh_access_tokens",
        )
        return instance
