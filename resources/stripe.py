from typing import Optional, Dict, Any
from datetime import datetime
import logging
# local imports
from seamless_payments.db.event_tracking import (PaymentEvent,
                                                 PaymentEventType,
                                                 track_payment_event,
                                                 event_tracker)
from seamless_payments.exceptions.stripe import (
    StripeCustomerCreationError,
    StripeCustomerRetrievalError,
    StripeInvoiceCreationError,
    StripeInvoiceItemCreationError,
    StripePaymentIntentError,
)
from seamless_payments.schemas.stripe import (
    StripeCustomer, StripeCustomerRequest, StripeInvoiceItemRequest,
    StripeInvoiceRequest, StripeInvoiceResponse, StripePaymentResponse)
from seamless_payments.clients.stripe import StripeClient

logger = logging.getLogger(__name__)


class _StripeResource:
    """Base class for Stripe resources with shared configuration"""

    _client: Optional[StripeClient] = None
    _brand_name: str = "My Online Store"

    @classmethod
    def _ensure_client_initialized(cls):
        print("INIT CLINT 😀")
        """Initialize client if not already done"""
        if cls._client is None:
            from .. import stripe  # Import the main module
            if not stripe.api_key:
                raise ValueError("Stripe not configured. Set stripe.api_key")

            cls._client = StripeClient()
            cls._client.configure(api_key=stripe.api_key)
            cls._brand_name = stripe.brand_name


class InvoiceItem(_StripeResource):
    """Handles creation and management of Stripe invoice items"""

    @classmethod
    async def create(cls,
                     invoice_item_data: StripeInvoiceItemRequest,
                     invoice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a Stripe invoice item
        Args:
            invoice_item_data: Data for the invoice item
            invoice_id: Optional invoice ID to attach this item to
        Returns:
            Stripe API response
        """
        cls._ensure_client_initialized()

        try:
            total_amount = invoice_item_data.amount * invoice_item_data.quantity
            payload = {
                "customer": invoice_item_data.customer_id,
                "amount":
                int(round(total_amount, 0)) * 100,  # Convert to cents
                "currency": invoice_item_data.currency.value,
                "description": invoice_item_data.description,
                # "quantity":
                # invoice_item_data.quantity,
                "metadata": invoice_item_data.metadata or {}
            }

            if invoice_id:
                payload["invoice"] = invoice_id

            # if invoice_item_data.price_id:
            #     payload["price"] = invoice_item_data.price_id
            # else:
            #     payload.update({
            #         "price_data": {
            #             "currency": invoice_item_data.currency.value,
            #             "product_data": {
            #                 "name":
            #                 invoice_item_data.product_name,
            #                 "description":
            #                 invoice_item_data.product_description or "",
            #             },
            #             "unit_amount": int(invoice_item_data.amount * 100),
            #         }
            #     })

            response = await cls._client._make_request(
                "POST",
                "/v1/invoiceitems",
                payload,
                idempotency_key=
                f"INVITEM-{datetime.now().timestamp()}-{invoice_item_data.product_name}"
            )

            if not response or "id" not in response:
                raise StripeInvoiceItemCreationError(
                    "Failed to create invoice item")

            return response

        except Exception as e:
            logger.error("Invoice item creation failed", exc_info=True)
            raise StripeInvoiceItemCreationError(
                "Failed to create invoice item") from e


class Invoice(_StripeResource):
    """Handles creation and management of Stripe invoices"""

    @classmethod
    async def create(cls,
                     invoice_data: StripeInvoiceRequest,
                     transction_id: str = None) -> StripeInvoiceResponse:
        """
        Create a Stripe invoice following the correct flow:
        1. Create draft invoice
        2. Add invoice items
        3. Finalize invoice
        """
        cls._ensure_client_initialized()
        invoice_data.metadata = invoice_data.metadata | {
            "transaction_id": transction_id
        }

        try:
            # Step 1: Create draft invoice
            draft_invoice = await cls._create_draft(invoice_data)
            await event_tracker.track_event(
                PaymentEvent(event_type=PaymentEventType.INVOICE_CREATED,
                             processor="stripe",
                             transaction_id=transction_id,
                             resource_id=draft_invoice["id"],
                             status="completed",
                             amount=float(draft_invoice["amount_due"] / 100),
                             currency=draft_invoice["currency"],
                             customer_id=invoice_data.customer.id,
                             processor_metadata={
                                 "invoice_number": draft_invoice.get("number"),
                                 "status": draft_invoice["status"]
                             },
                             metadata={}))

            # Step 2: Add invoice items
            await cls._add_items_to_invoice(draft_invoice["id"],
                                            invoice_data,
                                            invoice=draft_invoice)

            # Step 3: Finalize invoice
            finalized_invoice = await cls._finalize_invoice(draft_invoice["id"]
                                                            )

            # Update the event with the actual invoice ID idempotency keys
            await event_tracker.track_event(
                PaymentEvent(
                    event_type=PaymentEventType.INVOICE_FINALISED,
                    processor="stripe",
                    resource_id=finalized_invoice["id"],
                    status="completed",
                    amount=float(finalized_invoice["amount_due"] / 100),
                    currency=finalized_invoice["currency"],
                    customer_id=invoice_data.customer.id,
                    processor_metadata={
                        "invoice_number": finalized_invoice.get("number"),
                        "status": finalized_invoice["status"]
                    },
                    metadata={}))

            return cls._parse_response(finalized_invoice)

        except Exception as e:
            logger.error("Invoice creation failed", exc_info=True)
            raise StripeInvoiceCreationError("Failed to create invoice") from e

    @classmethod
    async def _create_draft(
            cls, invoice_data: StripeInvoiceRequest) -> Dict[str, Any]:
        """Create a draft invoice without line items"""
        payload = {
            "customer": invoice_data.customer.id,
            "auto_advance": False,  # Important for draft invoices
            "collection_method": invoice_data.collection_method,
            "currency": invoice_data.currency.value,
            "description": invoice_data.description or "Invoice",
            "metadata": invoice_data.metadata or {},
        }

        if invoice_data.due_date and invoice_data.collection_method == "send_invoice":
            payload["due_date"] = int(invoice_data.due_date.timestamp())

        response = await cls._client._make_request(
            "POST",
            "/v1/invoices",
            payload,
            idempotency_key=f"DRAFT-INV-{datetime.now().timestamp()}")

        if not response or "id" not in response:
            raise StripeInvoiceCreationError("Failed to create draft invoice")

        return response

    @classmethod
    async def _add_items_to_invoice(cls, invoice_id: str,
                                    invoice_data: StripeInvoiceRequest,
                                    invoice) -> None:
        """Add all items to the invoice using InvoiceItem resource"""
        for item in invoice_data.items:
            item_request = StripeInvoiceItemRequest(
                customer_id=invoice_data.customer.id,
                amount=item.price,
                currency=invoice_data.currency,
                description=item.description,
                quantity=item.quantity,
                product_name=item.name,
                product_description=item.description,
                metadata=invoice_data.metadata,
                # price_id=item.price_id  # Optional, if using predefined prices
            )
            invoice_item = await InvoiceItem.create(item_request,
                                                    invoice_id=invoice_id)
            await event_tracker.track_event(
                PaymentEvent(
                    event_type=PaymentEventType.INVOICE_ITEM_CREATED,
                    processor="stripe",
                    transaction_id=invoice_data.metadata["transaction_id"],
                    resource_id=invoice_item["id"],
                    status="completed",
                    amount=float(invoice["amount_due"] / 100),
                    currency=invoice_data.currency,
                    customer_id=invoice_data.customer.id,
                    processor_metadata={"data": invoice_data},
                    metadata={}))

    @classmethod
    async def _finalize_invoice(cls, invoice_id: str) -> Dict[str, Any]:
        """Finalize the draft invoice"""
        response = await cls._client._make_request(
            "POST", f"/v1/invoices/{invoice_id}/finalize")

        if not response or "id" not in response:
            raise StripeInvoiceCreationError("Failed to finalize invoice")

        return response

    @classmethod
    def _parse_response(cls, response: Dict[str,
                                            Any]) -> StripeInvoiceResponse:
        """Convert Stripe API response to our schema"""
        return StripeInvoiceResponse(
            id=response["id"],
            number=response.get("number"),
            status=response["status"],
            amount_due=float(response["amount_due"] / 100),
            amount_paid=float(response["amount_paid"] / 100),
            currency=response["currency"],
            due_date=datetime.fromtimestamp(response["due_date"])
            if response.get("due_date") else None,
            created_at=datetime.fromtimestamp(response["created"]),
            invoice_pdf=response.get("invoice_pdf"),
            hosted_invoice_url=response.get("hosted_invoice_url"),
            payment_intent=response.get("payment_intent"),
        )


class PaymentIntent(_StripeResource):
    """PaymentIntent resource with Stripe-like static methods"""

    _client: StripeClient = None
    _brand_name: str = None

    @classmethod
    async def create_from_invoice(cls, invoice: StripeInvoiceResponse,
                                  customer: StripeCustomer) -> Dict[str, Any]:
        """Create PaymentIntent from invoice (Stripe-like pattern)"""
        cls._ensure_client_initialized()
        # get total amount from invoice items
        # and convert to cents

        payload = {
            "amount": int(invoice.amount_due * 100),
            "currency": invoice.currency.value,
            "customer": customer.id,
            "description": f"Payment for invoice {invoice.id}",
            "payment_method_types": ["card"],
            "confirm": False,
            "capture_method": 'manual',
        }

        response = await cls._client._make_request("POST",
                                                   "/v1/payment_intents",
                                                   payload,
                                                   idempotency_key=invoice.id)

        return {
            "payment_intent_id": response["id"],
            "status": response["status"],
            "client_secret": response["client_secret"]
        }

    @classmethod
    async def update(cls, payment_intent_id: str, *args,
                     **kwargs) -> Dict[str, Any]:
        """Attach a payment method to an existing PaymentIntent, or 
        update other attributes dynamically"""
        if cls._client is None:
            raise ValueError(
                "Stripe not configured. Call stripe.configure() first")

        # Prepare the payload
        payload = {}

        # Ensure payment_method_id is passed in the arguments or kwargs
        if 'payment_method_id' in kwargs:
            payload["payment_method"] = kwargs['payment_method_id']

        # Add any additional attributes passed via kwargs to the payload
        for key, value in kwargs.items():
            if key != 'payment_method_id':  # Avoid duplicating the payment_method_id key
                payload[key] = value

        response = await cls._client._make_request(
            "POST", f"/v1/payment_intents/{payment_intent_id}", payload)

        return {
            "payment_intent_id": response["id"],
            "status": response["status"],
            "client_secret": response.get("client_secret"),
        }

    @classmethod
    async def confirm(cls, payment_intent_id: str) -> Dict[str, Any]:
        """Confirm a PaymentIntent"""
        if cls._client is None:
            raise ValueError(
                "Stripe not configured. Call stripe.configure() first")

        response = await cls._client._make_request(
            "POST", f"/v1/payment_intents/{payment_intent_id}/confirm")

        if response.get("status") == "requires_payment_method":
            raise StripePaymentIntentError("Payment method is required")

        return {
            "payment_intent_id": response["id"],
            "status": response["status"],
            "client_secret": response.get("client_secret"),
        }

    @classmethod
    async def capture(cls, payment_intent_id: str) -> StripePaymentResponse:
        """Capture an authorized payment"""
        if cls._client is None:
            raise ValueError(
                "Stripe not configured. Call stripe.configure() first")

        response = await cls._client._make_request(
            "POST", f"/v1/payment_intents/{payment_intent_id}/capture")

        if response.get("status") != "succeeded":
            raise StripePaymentIntentError("Payment not completed")

        return StripePaymentResponse(id=response["id"],
                                     amount=float(response["amount_received"] /
                                                  100),
                                     currency=response["currency"],
                                     status=response["status"],
                                     captured_at=datetime.now())

    @classmethod
    async def confirm_and_capture(
            cls, payment_intent_id: str) -> StripePaymentResponse:
        """Confirm and then capture a PaymentIntent"""
        # First confirm the payment intent
        confirm_response = await cls.confirm(payment_intent_id)
        # Then capture the payment if confirmation was successful
        if confirm_response["status"] == "requires_capture":
            capture_response = await cls.capture(payment_intent_id)
            return capture_response
        else:
            raise StripePaymentIntentError(
                "PaymentIntent not in 'requires_capture' status")


class Customer(_StripeResource):
    """Customer resource for Stripe"""

    _client: StripeClient = None
    _brand_name: str = None

    @classmethod
    async def create_or_get(cls,
                            customer_data: StripeCustomerRequest,
                            transction_id: str = None) -> StripeCustomer:
        """Create a new Stripe customer or retrieve existing one"""
        print('transction_id: RRRRRRRR', transction_id)
        cls._ensure_client_initialized()

        try:
            payload = {
                "name": customer_data.name,
                "email": customer_data.email,
                "phone": customer_data.phone
            }
            response = await cls._client._make_request(
                "POST",
                "/v1/customers",
                payload,
                idempotency_key=f"CUST-{customer_data.email}",
                transction_id=transction_id)
            if not response or "id" not in response:
                raise StripeCustomerCreationError(
                    "Failed to create Stripe customer")

            return StripeCustomer(
                id=response["id"],
                name=response.get("name"),
                email=response.get("email"),
                phone=response.get("phone"),
                created_at=datetime.fromtimestamp(response["created"]),
            )

        except Exception as e:
            error_message = str(e)
            if "already exists" in error_message or "duplicate" in error_message:
                # Customer already exists, retrieve the existing customer
                return await cls.get(email=customer_data.email)

            logger.error("Customer creation failed", exc_info=True)
            raise StripeCustomerCreationError(
                "Failed to create customer") from e

    @classmethod
    async def get(cls,
                  customer_id: Optional[str] = None,
                  email: Optional[str] = None) -> StripeCustomer:
        """Retrieve a customer by ID or email"""
        cls._ensure_client_initialized()

        try:
            if customer_id:
                response = await cls._client._make_request(
                    "GET", f"/v1/customers/{customer_id}")
            elif email:
                search_query = f"email:'{email}'"
                search_response = await cls._client._make_request(
                    "GET", "/v1/customers/search", {"query": search_query})

                if not search_response.get("data"):
                    raise StripeCustomerRetrievalError(
                        f"No customer found with email {email}")

                customer = search_response["data"][
                    0]  # Exact match from search
                return StripeCustomer(
                    id=customer["id"],
                    name=customer.get("name"),
                    email=customer.get("email"),
                    phone=customer.get("phone"),
                    created_at=datetime.fromtimestamp(customer["created"]),
                )
            else:
                raise ValueError(
                    "Either customer_id or email must be provided")

            return StripeCustomer(
                id=response["id"],
                name=response.get("name"),
                email=response.get("email"),
                phone=response.get("phone"),
                created_at=datetime.fromtimestamp(response["created"]),
            )

        except Exception as e:
            logger.error("Customer retrieval failed", exc_info=True)
            raise StripeCustomerRetrievalError(
                "Failed to retrieve customer") from e
