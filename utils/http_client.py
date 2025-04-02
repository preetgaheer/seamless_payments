import httpx
from typing import Optional, Dict, Any
import logging

# local imports
from seamless_payments.exceptions.paypal import PaymentProcessorError

logger = logging.getLogger(__name__)


class HttpClient:

    def __init__(self,
                 base_url: str,
                 auth_token: Optional[str] = None,
                 timeout: int = 30,
                 headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.default_headers = headers or {}
        if auth_token:
            self.default_headers["Authorization"] = f"Bearer {auth_token}"

    async def request(
            self,
            method: str,
            endpoint: str,
            payload: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = {**self.default_headers, **(headers or {})}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method,
                                                url,
                                                json=payload,
                                                headers=request_headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            raise PaymentProcessorError(error_msg)
        except httpx.RequestError as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise PaymentProcessorError(error_msg)

    async def post(self,
                   endpoint: str,
                   payload: Dict[str, Any],
                   headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self.request("POST", endpoint, payload, headers)

    async def get(self,
                  endpoint: str,
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self.request("GET", endpoint, None, headers)
