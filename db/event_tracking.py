# seamless_payments/event_tracking.py
from typing import Optional, Dict, Any, AsyncGenerator
import uuid
from pydantic import BaseModel, Field
from enum import Enum
import logging
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger("stripe")


class PaymentEventType(str, Enum):
    # Expanded event types
    TRANSACTION_STARTED = "transaction_started"
    INVOICE_DRAFT_CREATED = "invoice_draft_reated"
    INVOICE_FINALISED = "invoice_finalised"
    INVOICE_ITEM_CREATED = "invoice_item_created"
    PAYMENT_INTENT_CREATED = "payment_intent_created"
    PAYMENT_INTENT_UPDATED = "payment_intent_updated"
    PAYMENT_INTENT_CANCELED = "payment_intent_canceled"
    PAYMENT_METHOD_ATTACHED = "payment_method_attached"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_FAILED = "payment_failed"
    REFUND_INITIATED = "refund_initiated"
    REFUND_COMPLETED = "refund_completed"
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"
    CUSTOMER_DELETED = "customer_deleted"
    CUSTOMER_RETRIEVED = "customer_retrieved"
    TRANSACTION_COMPLETED = "transaction_completed"

    PAYPAL_ORDER_CREATED = "paypal_order_created"
    PAYPAL_INVOICE_CREATED = "paypal_invoice_created"


class PaymentEvent(BaseModel):
    transaction_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the entire transaction session",
    )
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this specific event",
    )
    event_type: PaymentEventType
    processor: str  # "stripe" or "paypal"
    resource_id: str = Field(
        ...,
        description="ID of the specific resource (invoice_id, payment_intent_id, etc.)",
    )
    status: str
    payment_status: Optional[str] = "pending"
    amount: Optional[float] = None
    currency: Optional[str] = None
    customer_id: Optional[str] = None
    processor_metadata: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    created_at: datetime = datetime.now()
    parent_event_id: Optional[str] = Field(
        None, description="Reference to previous event in this transaction"
    )


class PaymentEventTracker:

    def __init__(self):
        self._tracking_enabled = False
        self._handlers = []

    async def enable_tracking(self):
        self._tracking_enabled = True
        logger.info("Event tracking enabled successfully")

    async def disable_tracking(self):
        self._tracking_enabled = False
        logger.info("Event tracking disabled successfully")

    async def add_handler(self, handler):
        logger.info(f"Adding handler: {handler.__name__}")
        self._handlers.append(handler)
        logger.info("Handlers added successfully")
        logger.info(f"Handlers: {self._handlers}")

    async def track_event(self, event: PaymentEvent):
        logger.info("TRACK EVENT RECIEVED")
        logger.info(f"Tracking event: {event.event_type} for {event.resource_id}")
        logger.info(f"Tracking is enbaled or not: {self._tracking_enabled}")

        if not self._tracking_enabled:
            return

        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__}: {e}")

    def start_transaction(self, resource_id: str, transaction_id: str):
        self._current_transactions[resource_id] = transaction_id

    def end_transaction(self, resource_id: str):
        self._current_transactions.pop(resource_id, None)


# Global event tracker instance
event_tracker = PaymentEventTracker()


@asynccontextmanager
async def track_payment_event(
    event_type: PaymentEventType,
    transaction_id: str,
    processor: str,
    resource_id: str,
    status: str,
    parent_resource_id: Optional[str] = None,
    **kwargs,
) -> AsyncGenerator[PaymentEvent, None]:
    """Context manager for payment events with transaction tracking"""
    # Get or create transaction ID

    parent_event_id = None

    if parent_resource_id:
        parent_event_id = f"{parent_resource_id}-{event_type.value}"

    # if not transaction_id:
    #     transaction_id = str(uuid.uuid4())
    #     event_tracker.start_transaction(resource_id, transaction_id)

    event = PaymentEvent(
        transaction_id=transaction_id,
        event_type=event_type,
        processor=processor,
        resource_id=resource_id,
        status=status,
        parent_event_id=parent_event_id,
        **kwargs,
    )

    try:
        await event_tracker.track_event(event)
        yield event
    except Exception as e:
        # Track failure
        failure_event = PaymentEvent(
            transaction_id=transaction_id,
            event_type=event_type,
            processor=processor,
            resource_id=resource_id,
            status="failed",
            parent_event_id=event.event_id,
            procesor_metadata={"error": str(e), "original_event": event.dict()},
            metadata={},
        )
        await event_tracker.track_event(failure_event)
        raise
    finally:
        if event_type == PaymentEventType.TRANSACTION_COMPLETED:
            event_tracker.end_transaction(resource_id)
