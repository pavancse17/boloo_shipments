import base64
from datetime import timedelta

import requests
from celery import task
from django.utils.timezone import now

from .models import SellerShop, Shipment, ShipmentDetailSync, ShipmentSync


@task
def refresh_access_token(shop_sellar_id):
    """
    This is the child task of the refresh_access_tokens.
    """
    shop_sellar = SellerShop.objects.get(id=shop_sellar_id)
    base64_credentials = base64.b64encode(
        bytes("%s:%s" % (shop_sellar.client_id, shop_sellar.client_secret), encoding="utf8",)
    )
    response = requests.post(
        url=SellerShop.BOL_AUTH_URL,
        headers={
            "Accept": "application/json",
            "Authorization": "Basic %s" % base64_credentials.decode(),
        },
    )
    if response.status_code == 200:
        shop_sellar.access_token = response.json()["access_token"]
        shop_sellar.token_expires_at = now() + timedelta(
            seconds=int(response.json()["expires_in"])
        )
        shop_sellar.save()


@task
def refresh_access_tokens():
    """
    This task will trigger for every 1 minute.
    This will internally trigger many sub tasks to refresh all the expired credentials. 
    """
    for shop_sellar_id in SellerShop.objects.token_expiered_sellar_shops().values_list(
        "id", flat=True
    ):
        refresh_access_token.delay(shop_sellar_id)


def get_shipments(token, page, fulfilment_method):
    response = requests.get(
        url=ShipmentSync.SHIPMENTS_URL,
        params={"page": page, "fulfilment-method": fulfilment_method},
        headers={
            "Accept": "application/vnd.retailer.v3+json",
            "Authorization": "Bearer %s" % token,
        },
    )
    return response


@task
def sync_sellar_shipments(shipment_sync_id, page, fulfilment_method):
    """
    This is the child task of the sync shipments.
    This will create Shipment record with Not Started status.
    So that Shipment detail job will process those records.
    """
    shipment_sync = ShipmentSync.objects.get(id=shipment_sync_id)
    sellar = shipment_sync.sellar
    response = get_shipments(sellar.access_token, page, fulfilment_method)

    if response.status_code == 200:
        shipments = response.json().get("shipments", [])
        shipment_sync.remaining_req_limit = int(response.headers["x-ratelimit-remaining"])
        shipment_sync.limit_reset_at = now() + timedelta(
            seconds=int(response.headers["x-ratelimit-reset"])
        )

        # last page reached
        if not shipments:
            shipment_sync.initial_scan_completed = True
            shipment_sync.save()
            return

        shipment_sync.save()

        for shipment in shipments:
            shipment, created = Shipment.objects.get_or_create(
                shipment_id=shipment["shipmentId"],
                sellar=sellar,
                fulfilment_method=fulfilment_method,
            )

            # if all pages already scanned and shipment exists then it means no new shipments.
            if not created and shipment_sync.initial_scan_completed:
                break

        sync_sellar_shipments(shipment_sync_id, page + 1, fulfilment_method)
    elif response.status_code == 429:
        sync_sellar_shipments.apply_async(
            args=[shipment_sync_id, page, fulfilment_method],
            eta=now() + timedelta(seconds=int(response.headers["retry-after"])),
        )


@task
def sync_shipments():
    """
    This task is triggered for every one minute.
    This will trigger many sub stasks to fetch and store shipment ids.
    """
    for shipment_sync_id in ShipmentSync.objects.elegible_to_sync().values_list("id", flat=True):
        sync_sellar_shipments.delay(shipment_sync_id, 1, Shipment.FBR)
        sync_sellar_shipments.delay(shipment_sync_id, 1, Shipment.FBB)


def get_shipment(token, shipment_id):
    response = requests.get(
        url=ShipmentDetailSync.SHIPMENT_URL.format(shipment_id),
        headers={
            "Accept": "application/vnd.retailer.v3+json",
            "Authorization": "Bearer %s" % token,
        },
    )
    return response


@task
def sync_detail_shipment(sync_detail_id, shipment_id):
    shipment = Shipment.objects.get(id=shipment_id)
    sync_detail = ShipmentDetailSync.objects.get(id=sync_detail_id)

    shipment.state = Shipment.STARTED
    shipment.save()

    response = get_shipment(shipment.sellar.access_token, shipment.shipment_id)

    if response.status_code == 200:
        sync_detail.remaining_req_limit = int(response.headers["x-ratelimit-remaining"])
        sync_detail.limit_reset_at = now() + timedelta(
            seconds=int(response.headers["x-ratelimit-reset"])
        )
        sync_detail.save()
        shipment.data = response.text
        shipment.state = Shipment.FINISHED
        shipment.save()

    elif response.status_code == 429:
        sync_detail.remaining_req_limit = 0
        sync_detail.limit_reset_at = now() + timedelta(
            seconds=int(response.headers["x-ratelimit-reset"])
        )
        sync_detail.save()


@task
def sync_detail_shipments():
    """
    This job runs for every 1 minute and triggers sub task to fetch the details of the shipments.
    It will trigger as many detail requests possible as per the rate limit.
    """
    for sync_detail in ShipmentDetailSync.objects.elegible_to_sync():
        # If this job triggered with remainig limit 0 then it means limit reset time reached.
        # So it will have 14 requests as max limit.
        slice_limit = sync_detail.remaining_req_limit or 14

        for shipment_id in Shipment.objects.filter(state=Shipment.NOT_STARTED).values_list(
            "id", flat=True
        )[:slice_limit]:
            sync_detail_shipment.delay(sync_detail.id, shipment_id)
