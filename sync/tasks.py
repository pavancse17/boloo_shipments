import base64
from datetime import timedelta
from io import BytesIO

import requests
from django.utils.timezone import now
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from requests import HTTPError

from boloo_shop import celery_app
from shipments.models import Shipment
from shipments.serializers import ShipmentSerializer
from shipments.utils import AccessToken

from . import constants
from .exceptons import SyncCompletedError
from .models import SellerEndPointTracker, ShipmentSyncTracker


class SyncEndPoints(celery_app.Task):
    def run(self):
        for seller_end_pont in SellerEndPointTracker.objects.eligible_end_points():
            if seller_end_pont.end_point_name == constants.SHIPMENT_LIST_ENDPOINT_NAME:
                SyncShipmentListEndPoint.delay(seller_end_pont.id, 1, constants.FULFILMENT_METHODS[0])
            else:
                SyncShipmentDetailEndPoint.delay(seller_end_pont.id,)


class SyncShipmentListEndPoint(celery_app.Task):
    def run(self, end_point_tracker_id, page, start_method):
        self.page = page
        self.end_point_tracker = SellerEndPointTracker.objects.get(id=end_point_tracker_id)
        self.seller = self.end_point_tracker.seller

        for method in constants.FULFILMENT_METHODS[constants.FULFILMENT_METHODS.index(start_method) :]:
            while True:
                response = self.fetch(method)

                if response.status_code == 200:
                    try:
                        self.save_success(response, method)
                    except SyncCompletedError:
                        break
                    self.page = self.page + 1
                    continue

                if response.status_code == 429:
                    SyncShipmentListEndPoint.apply_async(
                        args=[end_point_tracker_id, self.page, method],
                        eta=now() + timedelta(seconds=int(response.headers["retry-after"])),
                    )
                    return

                response.raise_for_status()
            self.page = 1

    def fetch(self, method):
        return requests.get(
            url=constants.SHIPMENTS_URL,
            params={"page": self.page, "fulfilment-method": method},
            headers={
                "Accept": "application/vnd.retailer.v3+json",
                "Authorization": "Bearer %s" % self.seller.access_token,
            },
        )

    def save_success(self, response, method):
        data = response.json()
        headers = response.headers
        shipments = data.get("shipments", [])
        self.end_point_tracker.remaining_req_limit = int(headers["x-ratelimit-remaining"])
        self.end_point_tracker.limit_reset_at = now() + timedelta(seconds=int(headers["x-ratelimit-reset"]))

        # last page reached
        if not shipments:
            setattr(
                self.end_point_tracker, SellerEndPointTracker.fulfilment_method_mapper[method], True,
            )
            self.end_point_tracker.save()
            raise SyncCompletedError("Last page reached")

        self.end_point_tracker.save()
        self.save_shipments(shipments, method)

    def save_shipments(self, shipments, method):
        for shipment in shipments:
            _, created = ShipmentSyncTracker.objects.get_or_create(
                shipment_id=shipment["shipmentId"], seller=self.seller
            )

            # if all pages already scanned and shipment exists then it means no new shipment.
            if not created and getattr(
                self.end_point_tracker, SellerEndPointTracker.fulfilment_method_mapper[method]
            ):
                raise SyncCompletedError("Reached to already synced shipment")


class SyncShipmentDetailEndPoint(celery_app.Task):
    def run(self, end_point_tracker_id):
        end_point_tracker = SellerEndPointTracker.objects.get(id=end_point_tracker_id)
        slice_limit = end_point_tracker.remaining_req_limit or 14

        for shipment_tracker_id in ShipmentSyncTracker.objects.filter(
            state=ShipmentSyncTracker.NOT_STARTED
        ).values_list("id", flat=True)[:slice_limit]:
            SyncShipmentDetail.apply_async(args=[end_point_tracker.id, shipment_tracker_id])


class SyncShipmentDetail(celery_app.Task):
    def run(self, end_point_tracker_id, shipment_tracker_id):
        shipment_tracker = ShipmentSyncTracker.objects.get(id=shipment_tracker_id)
        end_point_tracker = SellerEndPointTracker.objects.get(id=end_point_tracker_id)
        shipment_tracker.state = ShipmentSyncTracker.STARTED
        shipment_tracker.save()
        response = self.fetch(shipment_tracker.seller.access_token, shipment_tracker.shipment_id)

        if response.status_code == 200:
            end_point_tracker.remaining_req_limit = int(response.headers["x-ratelimit-remaining"])
            end_point_tracker.limit_reset_at = now() + timedelta(
                seconds=int(response.headers["x-ratelimit-reset"])
            )
            end_point_tracker.save()
            stream = BytesIO(bytes(response.text, 'utf-8'))
            serializer = ShipmentSerializer(data=CamelCaseJSONParser().parse(stream=stream), context={"seller": shipment_tracker.seller})
            serializer.is_valid()
            serializer.save()
            shipment_tracker.state = ShipmentSyncTracker.FINISHED
            shipment_tracker.save()

        elif response.status_code == 429:
            end_point_tracker.remaining_req_limit = 0
            end_point_tracker.limit_reset_at = now() + timedelta(
                seconds=int(response.headers["x-ratelimit-reset"])
            )
            end_point_tracker.save()

    def fetch(self, token, shipment_id):
        response = requests.get(
            url=constants.SHIPMENT_URL.format(shipment_id),
            headers={"Accept": "application/vnd.retailer.v3+json", "Authorization": "Bearer %s" % token,},
        )
        return response


SyncEndPoints = celery_app.register_task(SyncEndPoints())
SyncShipmentListEndPoint = celery_app.register_task(SyncShipmentListEndPoint())
SyncShipmentDetailEndPoint = celery_app.register_task(SyncShipmentDetailEndPoint())
SyncShipmentDetail = celery_app.register_task(SyncShipmentDetail())
