# seamless_payments/db_integration.py
from typing import Optional
from seamless_payments.db.base import DatabaseInterface
from .schemas import DatabaseType, TransactionBase, TransactionStatus
from .factory import DatabaseFactory
from .event_tracking import PaymentEvent, PaymentEventType, event_tracker
import logging

logger = logging.getLogger(__name__)


class DatabaseIntegration:

    def __init__(self):
        self._db: Optional[DatabaseInterface] = None
        self._initialized = False

    async def initialize(self,
                         db_type: DatabaseType = DatabaseType.SQLITE,
                         **kwargs):
        if self._initialized:
            return

        self._db = DatabaseFactory.create_database(db_type, **kwargs)
        await self._db.initialize()

        # Register our handler with the event tracker
        event_tracker.add_handler(self.handle_payment_event)
        event_tracker.enable_tracking()

        self._initialized = True
        logger.info("Database integration initialized")

    async def handle_payment_event(self, event: PaymentEvent):
        if not self._db:
            logger.warning(
                "Database not initialized - skipping event tracking")
            return

        # Map event to transaction record
        transaction_data = {
            "transaction_id": event.transaction_id,
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "payment_processor": event.processor,
            "resource_id": event.resource_id,
            "amount": event.amount,
            "currency": event.currency,
            "status": self._map_event_to_status(event),
            "customer_id": event.customer_id,
            "processor_metadata": {
                "event_type": event.event_type.value,
                **event.metadata
            },
            "parent_event_id": event.parent_event_id,
            "metadata": {}
        }
        transaction_data = TransactionBase(**transaction_data)

        try:
            await self._db.create_transaction(transaction_data)
        except Exception as e:
            logger.error(f"Failed to record payment event: {e}", exc_info=True)

    def _map_event_to_status(self, event: PaymentEvent) -> TransactionStatus:
        if "failed" in event.status.lower():
            return TransactionStatus.FAILED
        if event.event_type == PaymentEventType.PAYMENT_CAPTURED:
            return TransactionStatus.SUCCEEDED
        if event.event_type == PaymentEventType.PAYMENT_INTENT_CREATED:
            return TransactionStatus.PENDING
        if event.event_type == PaymentEventType.PAYMENT_CONFIRMED:
            return TransactionStatus.PENDING  # Still pending until captured
        return TransactionStatus.PENDING


# Global instance
db_integration = DatabaseIntegration()
