from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

# local imports
from seamless_payments.db.event_tracking import (
    PaymentEvent,
    PaymentEventType,
    event_tracker,
)
from seamless_payments.exceptions.paypal import (
    PayPalInvoiceCreationError,
    PayPalPaymentCaptureError,
)
from seamless_payments.schemas.paypal import (
    PayPalInvoiceRequest,
    PayPalInvoiceResponse,
    PayPalPaymentResponse,
)
from seamless_payments.clients.paypal import PayPalClient

logger = logging.getLogger("paypal")


class _PayPalResource:
    """Base class for PayPal resources with shared configuration"""

    _client: Optional[PayPalClient] = None
    _brand_name: str = "My Online Store"
    _return_url: str = "https://yourdomain.com/payment/return"
    _cancel_url: str = "https://yourdomain.com/payment/cancel"

    @classmethod
    def _ensure_client_initialized(cls):
        """Initialize client if not already done"""
        if cls._client is None:
            from .. import paypal  # Import the main module

            if not paypal.client_id or not paypal.client_secret:
                raise ValueError(
                    "PayPal not configured. Set paypal.client_id and paypal.client_secret"
                )

            logger.info(f"paypal.timeout: {paypal.timeout}")
            cls._client = PayPalClient()
            cls._client.configure(
                client_id=paypal.client_id,
                client_secret=paypal.client_secret,
                environment=paypal.environment,
                timeout=paypal.timeout,
                max_retries=paypal.max_retries,
            )
            cls._brand_name = paypal.brand_name
            cls._return_url = paypal.return_url
            cls._cancel_url = paypal.cancel_url


class Invoice(_PayPalResource):
    """Invoice resource with Stripe-like static methods"""

    _client: PayPalClient = None
    _brand_name: str = None
    _return_url: str = None
    _cancel_url: str = None

    @classmethod
    async def create(
        cls, invoice_data: PayPalInvoiceRequest, transaction_id: str
    ) -> PayPalInvoiceResponse:
        """Create a PayPal invoice"""
        cls._ensure_client_initialized()

        cls._validate_invoice_data(invoice_data)

        try:
            payload = cls._build_payload(invoice_data)
            response = await cls._client._make_request(
                "POST",
                "/v2/invoicing/invoices",
                payload,
                idempotency_key=f"INV-{int(datetime.now().timestamp())}",
            )

            if not response or "id" not in response:
                raise PayPalInvoiceCreationError("Failed to create PayPal invoice")

            res = cls._parse_response(response)
            await event_tracker.track_event(
                PaymentEvent(
                    event_type=PaymentEventType.PAYPAL_INVOICE_CREATED,
                    processor="paypal",
                    transaction_id=transaction_id,
                    resource_id=res.invoice_id,
                    status="succeeded",
                    amount=res.amount_due,
                    currency=res.currency,
                    customer_id="",
                    processor_metadata={"data": response},
                    metadata=response.get("metadata", {}),
                )
            )
            return res

        except Exception as e:
            logger.error("Invoice creation failed", exc_info=True)
            print(str(e))
            raise PayPalInvoiceCreationError("Failed to create invoice") from e

    @classmethod
    def _validate_invoice_data(cls, invoice_data: PayPalInvoiceRequest):
        """Validate invoice data before processing"""
        if invoice_data.due_date and invoice_data.due_date <= datetime.now():
            raise ValueError("Due date must be in the future")

    @classmethod
    def _build_payload(cls, invoice_data: PayPalInvoiceRequest) -> Dict[str, Any]:
        """Build the request payload for invoice creation"""
        name_parts = invoice_data.customer.name.strip().split(" ", 1)
        given_name = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else given_name

        invoice_date = datetime.now()
        due_date = invoice_data.due_date or invoice_date + timedelta(days=10)
        term_type = (
            "NET_10"
            if (due_date - invoice_date).days == 10
            else "DUE_ON_DATE_SPECIFIED"
        )

        payload = {
            "detail": {
                "invoice_number": f"INV-{int(invoice_date.timestamp())}",
                "currency_code": invoice_data.currency.value,
                "note": invoice_data.notes or "Thank you for your business",
                "terms": "Payment due upon receipt",
                "invoice_date": invoice_date.strftime("%Y-%m-%d"),
                "payment_term": {
                    "term_type": term_type,
                    "due_date": due_date.strftime("%Y-%m-%d"),
                },
            },
            "primary_recipients": [
                {
                    "billing_info": {
                        "name": {"given_name": given_name, "surname": surname},
                        "email_address": invoice_data.customer.email,
                        "phones": cls._format_phone_numbers(
                            invoice_data.customer.phone
                        ),
                    }
                }
            ],
            "items": [
                {
                    "name": item.name,
                    "description": item.description or "",
                    "quantity": str(item.quantity),
                    "unit_amount": {
                        "currency_code": invoice_data.currency.value,
                        "value": f"{item.price:.2f}",
                    },
                    "unit_of_measure": "QUANTITY",
                }
                for item in invoice_data.items
            ],
        }

        if payload["primary_recipients"][0]["billing_info"]["phones"] is None:
            del payload["primary_recipients"][0]["billing_info"]["phones"]

        return payload

    @classmethod
    def _format_phone_numbers(cls, phone: str) -> Optional[list]:
        """Format phone numbers according to PayPal's requirements"""
        if not phone:
            return None

        try:
            digits = "".join(c for c in phone if c.isdigit())
            return [
                {
                    "country_code": "1",
                    "national_number": digits[-10:],
                    "phone_type": "MOBILE",
                }
            ]
        except Exception:
            logger.warning("Failed to format phone number")
            return None

    @classmethod
    def _parse_response(cls, response: Dict[str, Any]) -> PayPalInvoiceResponse:
        """Convert PayPal API response to our schema"""
        return PayPalInvoiceResponse(
            invoice_id=response["id"],
            status=response["status"],
            amount_due=float(response["amount"]["value"]),
            currency=response["amount"]["currency_code"],
            due_date=(
                datetime.strptime(response["payment_term"]["due_date"], "%Y-%m-%d")
                if "payment_term" in response
                else None
            ),
        )


class Order(_PayPalResource):
    """Order resource with Stripe-like static methods"""

    _client: PayPalClient = None
    _brand_name: str = None
    _return_url: str = None
    _cancel_url: str = None

    @classmethod
    async def create_from_invoice(
        cls, invoice: PayPalInvoiceResponse, trasaction_id: str
    ) -> Dict[str, Any]:
        """Create order from invoice (Stripe-like pattern)"""
        cls._ensure_client_initialized()

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": invoice.invoice_id,
                    "description": f"Payment for invoice {invoice.invoice_id}",
                    "amount": {
                        "currency_code": invoice.currency,
                        "value": str(invoice.amount_due),
                    },
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": cls._brand_name,
                        "locale": "en-US",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "return_url": cls._return_url,
                        "cancel_url": cls._cancel_url,
                        "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    }
                }
            },
        }

        response = await cls._client._make_request(
            "POST", "/v2/checkout/orders", payload, idempotency_key=invoice.invoice_id
        )

        print("response: cdfaDG", response)
        approval_url = next(
            link["href"] for link in response["links"] if link["rel"] == "payer-action"
        )
        await event_tracker.track_event(
            PaymentEvent(
                event_type=PaymentEventType.PAYPAL_ORDER_CREATED,
                processor="paypal",
                transaction_id=trasaction_id,
                resource_id=response["id"],
                status="succeeded",
                amount=response["purchase_units"][0]["amount"]["value"],
                currency=response["purchase_units"][0]["amount"]["currency_code"],
                customer_id="",
                processor_metadata={"data": response},
                metadata=response.get("metadata", {}),
            )
        )

        return {
            "order_id": response["id"],
            "approval_url": approval_url,
            "status": response["status"],
        }

    @classmethod
    async def capture(
        cls, order_id: str, invoice_id: str, transaction_id: Optional[str]
    ) -> PayPalPaymentResponse:
        """Capture an authorized payment"""
        if cls._client is None:
            raise ValueError(
                "PayPal not configured. Call paypal.set_global_config() first"
            )

        capture = await cls._client._make_request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            idempotency_key=invoice_id,
        )

        if capture.get("status") != "COMPLETED":
            raise PayPalPaymentCaptureError("Payment not completed")

        res = PayPalPaymentResponse(
            payment_id=capture["id"],
            invoice_id=invoice_id,
            amount=float(
                capture["purchase_units"][0]["payments"]["captures"][0]["amount"][
                    "value"
                ]
            ),
            currency=capture["purchase_units"][0]["payments"]["captures"][0]["amount"][
                "currency_code"
            ],
            status="COMPLETED",
            captured_at=datetime.now(),
        )
        await event_tracker.track_event(
            PaymentEvent(
                event_type=PaymentEventType.PAYPAL_ORDER_CAPTURED,
                processor="paypal",
                transaction_id=transaction_id,
                resource_id=res.payment_id,
                status="succeeded",
                amount=res.amount,
                currency=res.currency,
                customer_id="",
                processor_metadata={"data": ""},
                metadata={},
                payment_status="paid",
            )
        )

        return res
