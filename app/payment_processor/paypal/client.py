# payment_processor/paypal/client.py
import os
import asyncio
import httpx
from urllib.parse import urljoin
from typing import Optional, Dict, Any
from enum import Enum
import logging

from seamless_payments.app.exceptions.core import PaymentProcessorError

logger = logging.getLogger(__name__)


class PayPalEnvironment(Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PayPalClient:
    BASE_URLS = {
        PayPalEnvironment.SANDBOX.value: "https://api.sandbox.paypal.com",
        PayPalEnvironment.PRODUCTION.value: "https://api.paypal.com"
    }

    def __init__(
            self,
            environment: PayPalEnvironment = PayPalEnvironment.SANDBOX.value,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            timeout: int = 30,
            max_retries: int = 3):
        self.environment = environment
        self.base_url = self.BASE_URLS[environment]
        self.timeout = timeout
        self.max_retries = max_retries
        self.client_id = client_id or os.getenv(
            "PAYPAL_CLIENT_ID_SANDBOX" if environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv(
            "PAYPAL_SECRET_SANDBOX" if environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_SECRET")
        self.access_token = None
        self.session = httpx.AsyncClient(timeout=timeout)

    async def request(self,
                      method: str,
                      endpoint: str,
                      payload: Optional[Dict[str, Any]] = None,
                      idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Make authenticated request with retry and error handling"""
        if not self.access_token:
            self.access_token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        url = urljoin(self.base_url, endpoint)

        for attempt in range(self.max_retries):
            try:
                response = await self.session.request(method,
                                                      url,
                                                      json=payload,
                                                      headers=headers)

                if response.status_code == 401:
                    self.access_token = await self._get_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue

                response.raise_for_status()
                return response.json()

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error("Request failed after retries", exc_info=True)
                    raise PaymentProcessorError(
                        f"Request failed: {str(e)}") from e
                await asyncio.sleep(1 * (attempt + 1))

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token"""
        auth = (self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}

        for attempt in range(self.max_retries):
            try:
                response = await self.session.post(urljoin(
                    self.base_url, "/v1/oauth2/token"),
                                                   data=data,
                                                   auth=auth,
                                                   headers=headers)
                response.raise_for_status()
                return response.json()["access_token"]
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise PaymentProcessorError(
                        "Failed to get access token") from e
                await asyncio.sleep(1 * (attempt + 1))
