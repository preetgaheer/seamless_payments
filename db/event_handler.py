from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import TransactionCreate, TransactionModel
from .base import DatabaseInterface
import logging

logger = logging.getLogger(__name__)


class PaymentEventHandler:

    def __init__(self, database: DatabaseInterface):
        self.db = database

    async def handle_payment_event(
            self, event_data: dict) -> Optional[TransactionModel]:
        """Handle payment event and update database"""
        try:
            # Parse event data into TransactionCreate
            transaction = TransactionCreate(**event_data)

            # Check if transaction already exists
            existing = await self.db.get_transaction(
                transaction_id=transaction.transaction_id,
                payment_processor=transaction.payment_processor)

            if existing:
                # Update existing transaction if status changed
                if existing.status != transaction.status:
                    return await self.db.update_transaction_status(
                        transaction_id=transaction.transaction_id,
                        status=transaction.status.value,
                        payment_processor=transaction.payment_processor)
                return existing
            else:
                # Create new transaction
                return await self.db.create_transaction(transaction)

        except Exception as e:
            logger.error(f"Failed to handle payment event: {e}", exc_info=True)
            return None
