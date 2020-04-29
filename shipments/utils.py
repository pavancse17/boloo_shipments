import base64
from datetime import timedelta

import requests
from requests.exceptions import HTTPError
from django.utils.timezone import now


class AccessToken:
    URL = "https://login.bol.com/token?grant_type=client_credentials"

    @staticmethod
    def fetch(client_id, client_secret):
        encoded_credentials = base64.b64encode(bytes("%s:%s" % (client_id, client_secret), encoding="utf8"))
        response = requests.post(
            url=AccessToken.URL,
            headers={
                "Accept": "application/json",
                "Authorization": "Basic %s" % encoded_credentials.decode(),
            },
        )

        if response.status_code == 200:
            return response
        
        response.raise_for_status()


    @staticmethod
    def save(seller_instance, response):
        data = response.json()
        seller_instance.access_token = data["access_token"]
        seller_instance.token_expires_at = now() + timedelta(seconds=int(data["expires_in"]))
        seller_instance.save()
