from requests import HTTPError

from boloo_shop import celery_app
from shipments.utils import AccessToken

from .models import Seller


class RefreshAccessToken(celery_app.Task):
    def run(self, seller_id):
        seller = Seller.objects.get(id=seller_id)
        response = AccessToken.fetch(seller.client_id, seller.client_secret)
        AccessToken.save(seller, response)


class RefreshAccessTokens(celery_app.Task):
    def run(self):
        for seller_id in Seller.objects.token_expired_sellers().values_list("id", flat=True):
            RefreshAccessToken.apply_async(args=[seller_id,], retry=True, retry_policy={"max_retries": 3})


RefreshAccessToken = celery_app.register_task(RefreshAccessToken())
RefreshAccessTokens = celery_app.register_task(RefreshAccessTokens())
