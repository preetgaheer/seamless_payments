import logging
from enum import Enum
from typing import Optional, Dict, Any
import httpx
from urllib.parse import urljoin
import asyncio

from seamless_payments.exceptions.paypal import (PayPalConfigurationError,
                                                 PayPalAuthenticationError,
                                                 PayPalAPIError)

logger = logging.getLogger(__name__)


class PayPalEnvironment(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PayPalClient:
    """Modernized PayPal client with Stripe-like patterns"""

    BASE_URLS = {
        PayPalEnvironment.SANDBOX: "https://api.sandbox.paypal.com",
        PayPalEnvironment.PRODUCTION: "https://api.paypal.com"
    }

    # Class-level configuration (like Stripe)
    _environment: PayPalEnvironment = PayPalEnvironment.SANDBOX
    _client_id: Optional[str] = None
    _client_secret: Optional[str] = None
    _timeout: int = 30
    _max_retries: int = 3
    _session: Optional[httpx.AsyncClient] = None
    _access_token: Optional[str] = None

    @classmethod
    def configure(cls,
                  client_id: str,
                  client_secret: str,
                  environment: PayPalEnvironment = PayPalEnvironment.SANDBOX,
                  timeout: int = 30,
                  max_retries: int = 3):
        """Configure the PayPal client (similar to stripe.api_key)"""
        cls._client_id = client_id
        cls._client_secret = client_secret
        cls._environment = environment
        cls._timeout = timeout
        cls._max_retries = max_retries
        cls._session = httpx.AsyncClient(timeout=timeout)
        cls._access_token = None  # Reset any existing token

    @classmethod
    def _ensure_configured(cls):
        """Verify client is properly configured"""
        if not cls._client_id or not cls._client_secret:
            raise PayPalConfigurationError(
                "PayPal not configured. Call PayPalClient.configure() first")

    @classmethod
    async def _get_access_token(cls) -> str:
        """Get OAuth2 token with retry logic"""
        cls._ensure_configured()

        auth = (cls._client_id, cls._client_secret)
        data = {"grant_type": "client_credentials"}
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        url = urljoin(cls.BASE_URLS[cls._environment], "/v1/oauth2/token")

        for attempt in range(cls._max_retries):
            try:
                response = await cls._session.post(url,
                                                   data=data,
                                                   auth=auth,
                                                   headers=headers)
                response.raise_for_status()
                token_data = response.json()
                cls._access_token = token_data["access_token"]
                return cls._access_token
            except httpx.HTTPStatusError as e:
                if attempt == cls._max_retries - 1:
                    logger.error(
                        "Failed to get PayPal access token after retries")
                    raise PayPalAuthenticationError(
                        f"PayPal authentication failed: {e.response.text}"
                    ) from e
                await asyncio.sleep(1 * (attempt + 1))
            except Exception as e:
                if attempt == cls._max_retries - 1:
                    raise PayPalAuthenticationError(
                        "PayPal authentication failed") from e
                await asyncio.sleep(1 * (attempt + 1))

    @classmethod
    async def _make_request(
            cls,
            method: str,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Make authenticated request with retry and error handling"""
        cls._ensure_configured()

        if cls._access_token is None:
            cls._access_token = await cls._get_access_token()

        headers = {
            "Authorization": f"Bearer {cls._access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        url = urljoin(cls.BASE_URLS[cls._environment], endpoint)

        for attempt in range(cls._max_retries):
            try:
                response = await cls._session.request(method,
                                                      url,
                                                      json=payload,
                                                      headers=headers)

                # Handle token expiration
                if response.status_code == 401:
                    cls._access_token = await cls._get_access_token()
                    headers["Authorization"] = f"Bearer {cls._access_token}"
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_data = e.response.json()
                logger.error(f"PayPal API error: {error_data}")
                if attempt == cls._max_retries - 1:
                    raise PayPalAPIError(message=error_data.get(
                        "message", "PayPal API request failed"),
                                         http_status=e.response.status_code,
                                         json_body=error_data) from e
                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                if attempt == cls._max_retries - 1:
                    logger.error("PayPal request failed after retries",
                                 exc_info=True)
                    raise PayPalAPIError("PayPal request failed") from e
                await asyncio.sleep(1 * (attempt + 1))

    @classmethod
    def switch_environment(cls, new_environment: PayPalEnvironment):
        """Switch between sandbox and production environments"""
        if new_environment not in PayPalEnvironment:
            raise ValueError(f"Invalid environment: {new_environment}")
        cls._environment = new_environment
        cls._access_token = None  # Invalidate existing token
