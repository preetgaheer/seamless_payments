import logging
from typing import Optional, Dict, Any
# external imports
import httpx
from urllib.parse import urljoin
import asyncio
# local imports
from seamless_payments.exceptions.stripe import (StripeConfigurationError,
                                                 StripeAuthenticationError,
                                                 StripeAPIError)

logger = logging.getLogger(__name__)


class StripeClient:
    """Modern Stripe client with class-level configuration"""

    BASE_URL = "https://api.stripe.com/"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    DEFAULT_API_VERSION = "2023-08-16"

    # Class-level configuration
    _api_key: Optional[str] = None
    _api_version: str = DEFAULT_API_VERSION
    _timeout: int = DEFAULT_TIMEOUT
    _max_retries: int = MAX_RETRIES
    _session: Optional[httpx.AsyncClient] = None

    @classmethod
    def configure(cls,
                  api_key: str,
                  api_version: str = DEFAULT_API_VERSION,
                  timeout: int = DEFAULT_TIMEOUT,
                  max_retries: int = MAX_RETRIES):
        """Configure the Stripe client (similar to PayPalClient.configure)"""
        cls._api_key = api_key
        cls._api_version = api_version
        cls._timeout = timeout
        cls._max_retries = max_retries
        cls._session = httpx.AsyncClient(timeout=timeout)

    @classmethod
    def _ensure_configured(cls):
        """Verify client is properly configured"""
        if not cls._api_key:
            raise StripeConfigurationError(
                "Stripe not configured. Call StripeClient.configure() first")

    @classmethod
    async def _make_request(
        cls,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        transction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Stripe API"""
        cls._ensure_configured()
        if payload and hasattr(payload, 'metadata'):
            payload['metadata']['transaction_id'] = transction_id

        headers = {
            "Authorization": f"Bearer {cls._api_key}",
            "Stripe-Version": cls._api_version,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        url = urljoin(cls.BASE_URL, endpoint)

        for attempt in range(cls._max_retries):
            try:
                # Stripe expects form-encoded data for POST requests
                data = None
                if payload and method == "POST":
                    data = cls._form_encode(payload)
                if payload and method == "GET":
                    data = cls._form_encode(payload)

                response = await cls._session.request(
                    method,
                    url,
                    data=data if method == "POST" else None,
                    headers=headers,
                    params=data if method == "GET" else None)
                if response.status_code == 401:
                    raise StripeAuthenticationError(
                        "Invalid API key provided",
                        http_status=response.status_code)

                if response.status_code >= 400:
                    error_data = response.json()
                    raise StripeAPIError(message=error_data.get(
                        "error", {}).get("message", "Stripe API error"),
                                         http_status=response.status_code,
                                         json_body=error_data)

                return response.json()

            except httpx.HTTPStatusError as e:
                if attempt == cls._max_retries - 1:
                    logger.error(f"Stripe API error: {str(e)}")
                    raise StripeAPIError(
                        f"Stripe API request failed: {str(e)}",
                        http_status=e.response.status_code) from e
                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                if attempt == cls._max_retries - 1:
                    logger.error("Stripe request failed after retries",
                                 exc_info=True)
                    raise StripeAPIError("Stripe request failed") from e
                await asyncio.sleep(1 * (attempt + 1))

    @classmethod
    def _form_encode(cls, data: Dict[str, Any]) -> Dict[str, str]:
        """Convert dictionary to form-encoded data for Stripe API"""
        encoded = {}
        for key, value in data.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    encoded[f"{key}[{subkey}]"] = str(subvalue)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for subkey, subvalue in item.items():
                            encoded[f"{key}[{i}][{subkey}]"] = str(subvalue)
                    else:
                        encoded[f"{key}[{i}]"] = str(item)
            else:
                encoded[key] = str(value)
        return encoded
