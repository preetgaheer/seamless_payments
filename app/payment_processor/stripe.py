import logging
import base64
from datetime import datetime
from typing import Dict, Any

# local imports
from seamless_payments.app.payment_processor.base import BasePaymentProcessor
from seamless_payments.app.utils.http_client import HttpClient
from seamless_payments.app.schemas.core import (InvoiceRequest,
                                                InvoiceResponse,
                                                PaymentCaptureRequest,
                                                PaymentResponse)
from seamless_payments.app.exceptions.core import (PaymentCaptureError,
                                                   InvoiceGenerationError)

logger = logging.getLogger(__name__)


class StripeProcessor(BasePaymentProcessor):
    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key: str, timeout: int = 30):
        """Initialize Stripe processor with API key"""
        self.api_key = api_key
        self.timeout = timeout
        auth_str = f"{self.api_key}:"
        basic_auth = base64.b64encode(auth_str.encode()).decode()

        self.http_client = HttpClient(base_url=self.BASE_URL,
                                      headers={
                                          "Authorization":
                                          f"Basic {basic_auth}",
                                          "Content-Type":
                                          "application/x-www-form-urlencoded"
                                      },
                                      timeout=timeout)

    async def create_invoice(self,
                             invoice_data: InvoiceRequest) -> InvoiceResponse:
        """Create Stripe invoice using raw API"""
        self.validate_invoice_data(invoice_data)

        try:
            # First create a customer
            customer_params = {
                "name": invoice_data.customer.name,
                "email": invoice_data.customer.email,
                "phone": invoice_data.customer.phone or ""
            }
            customer = await self.http_client.post("customers",
                                                   customer_params)

            # Create invoice items
            for item in invoice_data.items:
                item_params = {
                    "customer": customer["id"],
                    "price_data[currency]":
                    invoice_data.currency.value.lower(),
                    "price_data[product_data][name]": item.name,
                    "price_data[product_data][description]": item.description
                    or "",
                    "price_data[unit_amount]":
                    str(int(item.price * 100)),  # Stripe uses cents
                    "quantity": str(item.quantity)
                }
                await self.http_client.post("invoiceitems", item_params)

            # Create the invoice
            invoice_params = {
                "customer": customer["id"],
                "collection_method": "send_invoice",
                "days_until_due": "7",
                "description": invoice_data.notes or "",
                "auto_advance": "true"
            }

            if invoice_data.due_date:
                invoice_params["due_date"] = str(
                    int(invoice_data.due_date.timestamp()))

            invoice = await self.http_client.post("invoices", invoice_params)

            return self._parse_stripe_invoice_response(invoice)

        except Exception as e:
            logger.error(f"Stripe invoice creation failed: {str(e)}")
            raise InvoiceGenerationError(
                f"Stripe invoice creation failed: {str(e)}")

    async def capture_payment(
            self, capture_data: PaymentCaptureRequest) -> PaymentResponse:
        """Capture Stripe payment using raw API"""
        self.validate_capture_data(capture_data)

        try:
            # Finalize the invoice first
            finalized_invoice = await self.http_client.post(
                f"invoices/{capture_data.invoice_id}/finalize")

            # Pay the invoice (in a real scenario, this would charge the customer)
            # For manual payments, we'd typically use a PaymentIntent
            # This is a simplified version
            payment_params = {
                "paid_out_of_band": "true",
                "amount": str(int(capture_data.amount * 100))
            }

            paid_invoice = await self.http_client.post(
                f"invoices/{capture_data.invoice_id}/pay", payment_params)

            return self._parse_stripe_payment_response(paid_invoice)

        except Exception as e:
            logger.error(f"Stripe payment capture failed: {str(e)}")
            raise PaymentCaptureError(
                f"Stripe payment capture failed: {str(e)}")

    async def get_invoice(self, invoice_id: str) -> InvoiceResponse:
        """Retrieve Stripe invoice using raw API"""
        try:
            invoice = await self.http_client.get(f"invoices/{invoice_id}")
            return self._parse_stripe_invoice_response(invoice)

        except Exception as e:
            logger.error(f"Stripe invoice retrieval failed: {str(e)}")
            raise InvoiceGenerationError(
                f"Stripe invoice retrieval failed: {str(e)}")

    def _parse_stripe_invoice_response(
            self, response: Dict[str, Any]) -> InvoiceResponse:
        """Convert Stripe's API response to our schema"""
        return InvoiceResponse(
            invoice_id=response["id"],
            status=response["status"],
            amount_due=float(response["amount_due"]) /
            100,  # Convert from cents
            currency=response["currency"].upper(),
            due_date=datetime.fromtimestamp(response["due_date"])
            if response.get("due_date") else None)

    def _parse_stripe_payment_response(
            self, response: Dict[str, Any]) -> PaymentResponse:
        """Convert Stripe's payment response to our schema"""
        return PaymentResponse(
            payment_id=response["payment_intent"],
            invoice_id=response["id"],
            amount=float(response["amount_paid"]) / 100,  # Convert from cents
            currency=response["currency"].upper(),
            status=response["status"],
            captured_at=datetime.fromtimestamp(
                response["status_transitions"]["paid_at"]) if
            response["status_transitions"].get("paid_at") else datetime.now())
