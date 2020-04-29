from django.db import models
from django.utils.timezone import now


class SellerManager(models.Manager):
    def token_expired_sellers(self):
        return self.filter(token_expires_at__lte=now())


class Seller(models.Model):
    name = models.CharField(max_length=255)
    client_id = models.CharField(unique=True, max_length=255)
    client_secret = models.CharField(max_length=255)
    access_token = models.TextField()
    token_expires_at = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = SellerManager()

    class Meta:
        ordering = ("-updated",)


class Transport(models.Model):
    transport_id = models.IntegerField()
    transporter_code = models.CharField(max_length=255)
    track_and_trace = models.CharField(max_length=255)
    shipping_label_id = models.IntegerField(null=True)
    shipping_label_code = models.CharField(max_length=255, blank=True)


class UserData(models.Model):
    pick_up_point_name = models.CharField(max_length=255, blank=True)
    saluation_code = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    surname = models.CharField(max_length=255, blank=True)
    street_name = models.CharField(max_length=255, blank=True)
    house_number = models.CharField(max_length=255, blank=True)
    house_number_extended = models.CharField(max_length=255, blank=True)
    address_supplement = models.CharField(max_length=255, blank=True)
    extra_address_information = models.CharField(max_length=255, blank=True)
    zip_code = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country_code = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=255, blank=True)
    vat_number = models.CharField(max_length=255, blank=True)
    chamber_of_commerce_number = models.CharField(max_length=255, blank=True)
    order_reference = models.CharField(max_length=255, blank=True)
    delivery_phone_number = models.CharField(max_length=255, blank=True)


class Shipment(models.Model):
    seller = models.ForeignKey("shipments.seller", on_delete=models.CASCADE, related_name="shipments")
    shipment_id = models.IntegerField()
    pick_up_point = models.BooleanField()
    shipment_date = models.DateTimeField()
    shipment_reference = models.CharField(max_length=255, blank=True)
    transport = models.ForeignKey("shipments.transport", related_name="transported_shipments", null=True, on_delete=models.SET_NULL)
    customer = models.ForeignKey("shipments.userdata", null=True, on_delete=models.SET_NULL)
    billing = models.ForeignKey("shipments.userdata", related_name="billed_shipments", null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-shipment_date",)


class ShipmentItem(models.Model):
    shipment = models.ForeignKey("shipments.shipment", related_name="items", on_delete=models.CASCADE)
    order_item_id = models.CharField(max_length=255)
    order_id = models.CharField(max_length=255)
    order_date = models.DateTimeField()
    latest_delivery_date = models.DateTimeField()
    ean = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    quantity = models.IntegerField()
    offer_price = models.DecimalField(decimal_places=2, max_digits=5)
    offer_condition = models.CharField(max_length=255)
    offer_reference = models.CharField(max_length=255, blank=True)
    fulfilment_method = models.CharField(max_length=3)

    class Meta:
        ordering = ("-order_date", )
