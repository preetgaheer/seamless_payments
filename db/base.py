# seamless_payments/db/base.py
from abc import ABC, abstractmethod
from typing import Optional, List, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text

from seamless_payments.db.schemas import TransactionCreate, TransactionModel


class DatabaseInterface(ABC):

    @property
    @abstractmethod
    def engine(self) -> AsyncEngine:
        pass

    @abstractmethod
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database and create tables"""
        pass

    @abstractmethod
    async def create_transaction(
            self, transaction: TransactionCreate) -> TransactionModel:
        pass

    @abstractmethod
    async def update_transaction_status(
            self, transaction_id: str, status: str,
            payment_processor: str) -> Optional[TransactionModel]:
        pass

    @abstractmethod
    async def get_transaction(
            self, transaction_id: str,
            payment_processor: str) -> Optional[TransactionModel]:
        pass

    @abstractmethod
    async def get_transactions_by_customer(
            self,
            customer_id: str,
            limit: int = 100,
            offset: int = 0) -> List[TransactionModel]:
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection pool"""
        pass
