from django.db import models
from django.db.models import Q
from django.utils.timezone import now

from . import constants


class SellerEndPointTrackerManager(models.Manager):
    def eligible_end_points(self):
        return self.filter(Q(limit_reset_at__lte=now()) | Q(remaining_req_limit__gt=0))


class SellerEndPointTracker(models.Model):
    fulfilment_method_mapper = {
        constants.FBB: "initial_fbb_completed",
        constants.FBR: "initial_fbr_completed",
    }
    seller = models.ForeignKey("shipments.seller", on_delete=models.CASCADE)
    end_point_name = models.CharField(max_length=255)
    remaining_req_limit = models.IntegerField()
    limit_reset_at = models.DateTimeField()
    initial_fbb_completed = models.BooleanField(default=False)
    initial_fbr_completed = models.BooleanField(default=False)
    objects = SellerEndPointTrackerManager()

    @property
    def initial_scan_completed(self):
        return self.initial_fbb_completed and self.initial_fbr_completed

    class Meta:
        unique_together = ("seller", "end_point_name")


class ShipmentSyncTracker(models.Model):
    NOT_STARTED = "Not Started"
    STARTED = "Started"
    FINISHED = "Finished"

    STATE_CHOICES = (
        (NOT_STARTED, "Not Started"),
        (STARTED, "Started"),
        (FINISHED,"Finished")
    )

    seller = models.ForeignKey(
        "shipments.seller", related_name="shipments_to_sync", on_delete=models.CASCADE
    )
    shipment_id = models.CharField(unique=True, max_length=255)
    state = models.CharField(max_length=15, choices=STATE_CHOICES, default=NOT_STARTED)
