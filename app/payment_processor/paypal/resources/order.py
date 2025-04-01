# payment_processor/paypal/resources/order.py
import logging
from datetime import datetime
from typing import Dict, Any

from seamless_payments.app.exceptions.core import PaymentCaptureError
from seamless_payments.app.schemas.core import PaymentResponse

logger = logging.getLogger(__name__)


class PayPalOrder:

    def __init__(self, client, brand_name: str, return_url: str,
                 cancel_url: str):
        self.client = client
        self.brand_name = brand_name
        self.return_url = return_url
        self.cancel_url = cancel_url

    async def create(self, invoice_id: str, amount: float,
                     currency: str) -> Dict[str, Any]:
        """Create a PayPal order for payment"""
        payload = {
            "intent":
            "CAPTURE",
            "purchase_units": [{
                "reference_id": invoice_id,
                "description": f"Payment for invoice {invoice_id}",
                "amount": {
                    "currency_code": currency,
                    "value": str(amount)
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

        response = await self.client.request("POST",
                                             "/v2/checkout/orders",
                                             payload,
                                             idempotency_key=invoice_id)

        approval_url = next(link["href"] for link in response["links"]
                            if link["rel"] == "payer-action")

        return {
            "order_id": response["id"],
            "approval_url": approval_url,
            "status": response["status"]
        }

    async def capture(self, order_id: str, invoice_id: str) -> PaymentResponse:
        """Capture an approved PayPal payment"""
        response = await self.client.request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            idempotency_key=invoice_id)

        if response.get("status") != "COMPLETED":
            raise PaymentCaptureError("Payment not completed")

        return PaymentResponse(
            payment_id=response["id"],
            invoice_id=invoice_id,
            amount=float(response["purchase_units"][0]["payments"]["captures"]
                         [0]["amount"]["value"]),
            currency=response["purchase_units"][0]["payments"]["captures"][0]
            ["amount"]["currency_code"],
            status="COMPLETED",
            captured_at=datetime.now())
