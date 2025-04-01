import os
from datetime import datetime, timedelta
import logging
from enum import Enum
from typing import Optional, Dict, Any
# 3rd party libraries
import httpx
from urllib.parse import urljoin
import asyncio

# local imports
from seamless_payments.app.exceptions.core import (InvoiceGenerationError,
                                                   PaymentCaptureError,
                                                   PaymentProcessorError)
from seamless_payments.app.payment_processor.base import BasePaymentProcessor
from seamless_payments.app.schemas.core import (InvoiceRequest,
                                                InvoiceResponse,
                                                PaymentResponse)

logger = logging.getLogger(__name__)


class PayPalEnvironment(Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PayPalClient:
    """Production-ready PayPal client with environment switching"""

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
        """
        Initialize PayPal client.
        
        Args:
            environment: PayPalEnvironment.SANDBOX or PayPalEnvironment.PRODUCTION
            client_id: Optional client ID (will try env vars if not provided)
            client_secret: Optional client secret (will try env vars if not provided)
        """
        self.environment = environment
        self.base_url = self.BASE_URLS[environment]
        self.timeout = timeout
        self.max_retries = max_retries

        # Get credentials from parameters or environment variables
        self.client_id = client_id or os.getenv(
            "PAYPAL_CLIENT_ID_SANDBOX" if environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv(
            "PAYPAL_SECRET_SANDBOX" if environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("PayPal credentials not provided and not found "
                             "in environment variables")

        self.access_token = None
        self.session = httpx.AsyncClient(timeout=timeout)

    def switch_environment(self, new_environment: PayPalEnvironment):
        """Switch between sandbox and production environments"""
        if new_environment not in PayPalEnvironment:
            raise ValueError(f"Invalid environment: {new_environment}")

        self.environment = new_environment
        self.base_url = self.BASE_URLS[new_environment]

        # Clear existing token when switching environments
        self.access_token = None

        # Update credentials based on new environment
        self.client_id = os.getenv(
            "PAYPAL_CLIENT_ID_SANDBOX" if new_environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv(
            "PAYPAL_SECRET_SANDBOX" if new_environment ==
            PayPalEnvironment.SANDBOX else "PAYPAL_SECRET")

    async def _get_access_token(self) -> str:
        """Get OAuth2 token with retry logic"""
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
                token_data = response.json()
                return token_data["access_token"]
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(
                        "Failed to get PayPal access token after retries")
                    raise PaymentProcessorError(
                        "PayPal authentication failed") from e
                await asyncio.sleep(1 * (attempt + 1))

    async def _make_request(
            self,
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
                print('payload: '*50, payload)
                response = await self.session.request(method,
                                                      url,
                                                      json=payload,
                                                      headers=headers)

                # Handle 401 Unauthorized (token might be expired)
                if response.status_code == 401:
                    self.access_token = await self._get_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                error_data = e.response.json()
                logger.error(f"PayPal API error: {error_data}")
                if attempt == self.max_retries - 1:
                    raise PaymentProcessorError(
                        f"PayPal API request failed: {error_data.get('message', str(e))}"
                    ) from e
                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error("PayPal request failed after retries",
                                 exc_info=True)
                    raise PaymentProcessorError("PayPal request failed") from e
                await asyncio.sleep(1 * (attempt + 1))


class PayPalPaymentProcessor(BasePaymentProcessor):
    """Production-ready PayPal payment processor with invoice generation"""

    def __init__(self, paypal_client: PayPalClient, brand_name: str,
                 return_url: str, cancel_url: str):
        """
        Initialize payment processor.
        
        Args:
            paypal_client: Configured PayPalClient instance
            brand_name: Your business name to show in PayPal UI
            return_url: Where to redirect after successful payment
            cancel_url: Where to redirect after canceled payment
        """
        self.client = paypal_client
        self.brand_name = brand_name
        self.return_url = return_url
        self.cancel_url = cancel_url

    def switch_environment(self, new_environment: PayPalEnvironment):
        """Switch between sandbox and production environments"""
        self.client.switch_environment(new_environment)

    async def create_invoice(self,
                             invoice_data: InvoiceRequest) -> InvoiceResponse:
        """Create PayPal invoice with proper validation"""
        self.validate_invoice_data(invoice_data)

        try:
            payload = self._build_paypal_invoice_request(invoice_data)
            response = await self.client._make_request(
                "POST",
                "/v2/invoicing/invoices",
                payload,
                idempotency_key=f"INV-{int(datetime.now().timestamp())}")

            if not response or "id" not in response:
                raise InvoiceGenerationError("Failed to create PayPal invoice")

            return self._parse_paypal_invoice_response(response)

        except Exception as e:
            logger.error("Invoice creation failed", exc_info=True)
            raise InvoiceGenerationError("Failed to create invoice") from e

    def _build_paypal_invoice_request(
            self, invoice_data: InvoiceRequest) -> Dict[str, Any]:
        """Build PayPal invoice request payload with validated dates"""
        name_parts = invoice_data.customer.name.strip().split(' ', 1)
        given_name = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else given_name

        # Calculate due date based on term type
        invoice_date = datetime.now()
        if invoice_data.due_date:
            # Validate due date is in the future
            if invoice_data.due_date <= invoice_date:
                raise ValueError("Due date must be in the future")
            due_date = invoice_data.due_date
        else:
            # Default to NET_10 (10 days from now)
            due_date = invoice_date + timedelta(days=10)

        # Ensure the date matches the term type
        term_type = "NET_10"
        days_diff = (due_date - invoice_date).days
        if days_diff != 10:
            term_type = "DUE_ON_DATE_SPECIFIED"

        payload = {
            "detail": {
                "invoice_number": f"INV-{int(invoice_date.timestamp())}",
                "currency_code": invoice_data.currency.value,
                "note": invoice_data.notes or "Thank you for your business",
                "terms": "Payment due upon receipt",
                "invoice_date": invoice_date.strftime('%Y-%m-%d'),
                "payment_term": {
                    "term_type": term_type,
                    "due_date": due_date.strftime('%Y-%m-%d')
                }
            },
            "primary_recipients": [{
                "billing_info": {
                    "name": {
                        "given_name": given_name,
                        "surname": surname
                    },
                    "email_address":
                    invoice_data.customer.email,
                    "phones":
                    self._format_phone_numbers(invoice_data.customer.phone)
                }
            }],
            "items": [
                {
                    "name": item.name,
                    "description": item.description or "",
                    "quantity": str(item.quantity),
                    "unit_amount": {
                        "currency_code": invoice_data.currency.value,
                        "value": f"{item.price:.2f}"  # Ensure 2 decimal places
                    },
                    "unit_of_measure": "QUANTITY"
                } for item in invoice_data.items
            ]
        }

        # Remove optional fields if empty
        if payload["primary_recipients"][0]["billing_info"]["phones"] is None:
            del payload["primary_recipients"][0]["billing_info"]["phones"]

        return payload

    def _format_phone_numbers(self, phone: Optional[str]) -> Optional[list]:
        """Format phone numbers for PayPal API"""
        if not phone:
            return None

        try:
            # Simple formatting - in production use a library like phonenumbers
            digits = ''.join(c for c in phone if c.isdigit())
            return [{
                "country_code": "1",  # Default to US
                "national_number": digits[-10:],  # Last 10 digits
                "phone_type": "MOBILE"
            }]
        except Exception:
            logger.warning("Failed to format phone number")
            return None

    def _parse_paypal_invoice_response(
            self, response: Dict[str, Any]) -> InvoiceResponse:
        """Convert PayPal invoice response to our standard format"""
        return InvoiceResponse(
            invoice_id=response["id"],
            status=response["status"],
            amount_due=float(response["amount"]["value"]),
            currency=response["amount"]["currency_code"],
            due_date=datetime.strptime(response["payment_term"]["due_date"],
                                       "%Y-%m-%d")
            if "payment_term" in response else None)

    async def create_and_pay_invoice(
            self, invoice_data: InvoiceRequest) -> PaymentResponse:
        """Complete flow: create invoice and process payment"""
        try:
            # 1. Create invoice
            invoice = await self.create_invoice(invoice_data)

            # 2. Create payment order
            order = await self._create_order_from_invoice(invoice)

            print("\nPayment approval required!")
            print("Please visit this URL to approve the payment:")
            print(order["approval_url"])
            print("\nWaiting for payment approval...")

            await asyncio.sleep(60)

            # 3. Capture payment
            payment = await self._capture_order(order["order_id"],
                                                invoice.invoice_id)

            return payment

        except Exception as e:
            logger.error("Invoice payment failed", exc_info=True)
            raise PaymentProcessorError(
                "Invoice payment processing failed") from e

    async def _create_order_from_invoice(
            self, invoice: InvoiceResponse) -> Dict[str, Any]:
        """Create PayPal order from existing invoice"""
        payload = {
            "intent":
            "CAPTURE",
            "purchase_units": [{
                "reference_id": invoice.invoice_id,
                "description": f"Payment for invoice {invoice.invoice_id}",
                "amount": {
                    "currency_code": invoice.currency,
                    "value": str(invoice.amount_due)
                }
            }],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": self.brand_name,
                        "locale": "en-US",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": self.return_url,
                        "cancel_url": self.cancel_url,
                        "payment_method_preference":
                        "IMMEDIATE_PAYMENT_REQUIRED"
                    }
                }
            }
        }

        response = await self.client._make_request(
            "POST",
            "/v2/checkout/orders",
            payload,
            idempotency_key=invoice.invoice_id)

        approval_url = next(link["href"] for link in response["links"]
                            if link["rel"] == "payer-action")
        return {
            "order_id": response["id"],
            "approval_url": approval_url,
            "status": response["status"]
        }

    async def _capture_order(self, order_id: str,
                             invoice_id: str) -> PaymentResponse:
        """Capture authorized payment and return standardized response"""
        capture = await self.client._make_request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            idempotency_key=invoice_id)

        if capture.get("status") != "COMPLETED":
            raise PaymentCaptureError("Payment not completed")

        return PaymentResponse(
            payment_id=capture["id"],
            invoice_id=invoice_id,
            amount=float(capture["purchase_units"][0]["payments"]["captures"]
                         [0]["amount"]["value"]),
            currency=capture["purchase_units"][0]["payments"]["captures"][0]
            ["amount"]["currency_code"],
            status="COMPLETED",
            captured_at=datetime.now())
