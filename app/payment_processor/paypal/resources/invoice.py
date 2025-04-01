import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from seamless_payments.app.exceptions.core import InvoiceGenerationError
from seamless_payments.app.schemas.core import InvoiceRequest, InvoiceResponse

logger = logging.getLogger(__name__)


class PayPalInvoice:

    def __init__(self, client):
        self.client = client

    async def create(self, invoice_data: InvoiceRequest) -> InvoiceResponse:
        """Create a PayPal invoice"""
        self._validate_invoice_data(invoice_data)

        try:
            payload = self._build_payload(invoice_data)
            response = await self.client.request(
                "POST",
                "/v2/invoicing/invoices",
                payload,
                idempotency_key=f"INV-{int(datetime.now().timestamp())}")

            if not response or "id" not in response:
                raise InvoiceGenerationError("Failed to create PayPal invoice")

            return self._parse_response(response)

        except Exception as e:
            logger.error("Invoice creation failed", exc_info=True)
            raise InvoiceGenerationError("Failed to create invoice") from e

    def _validate_invoice_data(self, invoice_data: InvoiceRequest):
        """Validate invoice data before processing"""
        if invoice_data.due_date and invoice_data.due_date <= datetime.now():
            raise ValueError("Due date must be in the future")

    def _build_payload(self, invoice_data: InvoiceRequest) -> Dict[str, Any]:
        """Build the request payload for invoice creation"""
        name_parts = invoice_data.customer.name.strip().split(' ', 1)
        given_name = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else given_name

        invoice_date = datetime.now()
        due_date = invoice_data.due_date or invoice_date + timedelta(days=10)
        term_type = "NET_10" if (
            due_date - invoice_date).days == 10 else "DUE_ON_DATE_SPECIFIED"

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
            "items": [{
                "name": item.name,
                "description": item.description or "",
                "quantity": str(item.quantity),
                "unit_amount": {
                    "currency_code": invoice_data.currency.value,
                    "value": f"{item.price:.2f}"
                },
                "unit_of_measure": "QUANTITY"
            } for item in invoice_data.items]
        }

        if payload["primary_recipients"][0]["billing_info"]["phones"] is None:
            del payload["primary_recipients"][0]["billing_info"]["phones"]

        return payload

    def _format_phone_numbers(self, phone: str) -> Optional[list]:
        """Format phone numbers according to PayPal's requirements"""
        if not phone:
            return None

        try:
            digits = ''.join(c for c in phone if c.isdigit())
            return [{
                "country_code": "1",
                "national_number": digits[-10:],
                "phone_type": "MOBILE"
            }]
        except Exception:
            logger.warning("Failed to format phone number")
            return None

    def _parse_response(self, response: Dict[str, Any]) -> InvoiceResponse:
        """Convert PayPal API response to our schema"""
        return InvoiceResponse(invoice_id=response["id"],
                               status=response["status"],
                               amount_due=float(response["amount"]["value"]),
                               currency=response["amount"]["currency_code"],
                               due_date=datetime.strptime(
                                   response["payment_term"]["due_date"],
                                   "%Y-%m-%d"))
