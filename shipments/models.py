from django.db import models
from django.db.models import Q
from django.utils.timezone import now


class SellerShopManager(models.Manager):
    def token_expiered_sellar_shops(self):
        return self.filter(token_expires_at__lte=now())


class SellerShop(models.Model):
    BOL_AUTH_URL = "https://login.bol.com/token?grant_type=client_credentials"

    name = models.CharField(max_length=255)
    client_id = models.CharField(unique=True, max_length=255)
    client_secret = models.CharField(max_length=255)
    access_token = models.TextField()
    token_expires_at = models.DateTimeField()
    objects = SellerShopManager()


class SyncBaseManager(models.Manager):
    def elegible_to_sync(self):
        return self.filter(Q(limit_reset_at__lte=now()) | Q(remaining_req_limit__gt=0))


class SyncBase(models.Model):
    sellar = models.OneToOneField(SellerShop, on_delete=models.CASCADE)
    remaining_req_limit = models.IntegerField()
    limit_reset_at = models.DateTimeField()

    objects = SyncBaseManager()

    class Meta:
        abstract = True


class ShipmentSync(SyncBase):
    SHIPMENTS_URL = "https://api.bol.com/retailer/shipments/"
    initial_scan_completed = models.BooleanField(default=False)


class ShipmentDetailSync(SyncBase):
    SHIPMENT_URL = "https://api.bol.com/retailer/shipments/{}"


class Shipment(models.Model):
    # State choices
    NOT_STARTED = 0
    STARTED = 1
    FINISHED = 2

    STATE_CHOICES = (
        (NOT_STARTED, "Not Started"),
        (STARTED, "Started"),
        (FINISHED, "Finished"),
    )

    # fulfilment_method choices
    FBR = "FBR"
    FBB = "FBB"

    sellar = models.ForeignKey(SellerShop, on_delete=models.CASCADE, related_name="shipments")
    shipment_id = models.CharField(max_length=255)
    fulfilment_method = models.CharField(max_length=3)
    state = models.SmallIntegerField(choices=STATE_CHOICES, default=NOT_STARTED)
    data = models.TextField(default='{"message": "Data not yet fetched."}')
