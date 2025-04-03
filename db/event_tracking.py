# seamless_payments/event_tracking.py
from typing import Optional, Dict, Any, AsyncGenerator
from pydantic import BaseModel
from enum import Enum
import logging
from datetime import datetime
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class PaymentEventType(str, Enum):
    INVOICE_CREATED = "invoice_created"
    PAYMENT_INTENT_CREATED = "payment_intent_created"
    PAYMENT_METHOD_ATTACHED = "payment_method_attached"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_FAILED = "payment_failed"
    REFUND_INITIATED = "refund_initiated"
    REFUND_COMPLETED = "refund_completed"


class PaymentEvent(BaseModel):
    event_type: PaymentEventType
    processor: str  # "stripe" or "paypal"
    resource_id: str
    status: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    customer_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime = datetime.utcnow()


class PaymentEventTracker:

    def __init__(self):
        self._tracking_enabled = False
        self._handlers = []

    def enable_tracking(self):
        self._tracking_enabled = True

    def disable_tracking(self):
        self._tracking_enabled = False

    def add_handler(self, handler):
        self._handlers.append(handler)

    async def track_event(self, event: PaymentEvent):
        if not self._tracking_enabled:
            return

        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__}: {e}")


# Global event tracker instance
event_tracker = PaymentEventTracker()


@asynccontextmanager
async def track_payment_event(event_type: PaymentEventType, processor: str,
                              resource_id: str, status: str,
                              **kwargs) -> AsyncGenerator[None, None]:
    """Context manager for tracking payment events with automatic failure handling"""
    event = PaymentEvent(event_type=event_type,
                         processor=processor,
                         resource_id=resource_id,
                         status=status,
                         **kwargs)

    try:
        await event_tracker.track_event(event)
        yield
    except Exception as e:
        # Track failure if an exception occurs
        failure_event = PaymentEvent(event_type=event_type,
                                     processor=processor,
                                     resource_id=resource_id,
                                     status="failed",
                                     metadata={
                                         "error": str(e),
                                         "original_event": event.dict()
                                     })
        await event_tracker.track_event(failure_event)
        raise
