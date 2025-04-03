# seamless_payments/db/core.py
from typing import Optional, List, AsyncGenerator
from datetime import datetime
from sqlalchemy import (MetaData, Table, Column, Integer, String, Float,
                        DateTime, JSON, UniqueConstraint)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.sql import select, insert, update
from seamless_payments.db.schemas import (TransactionCreate, TransactionModel,
                                          TransactionStatus, DatabaseType)
from .base import DatabaseInterface
import logging
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

metadata = MetaData()

transactions = Table(
    "transactions", metadata, Column("id", Integer, primary_key=True),
    Column("transaction_id", String(255), nullable=False),
    Column("payment_processor", String(50), nullable=False),
    Column("amount", Float, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("status", String(20), nullable=False),
    Column("customer_id", String(255)), Column("payment_method", String(50)),
    Column("metadata", JSON), Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    UniqueConstraint("transaction_id",
                     "payment_processor",
                     name="uq_transaction"))


class SQLAlchemyDatabase(DatabaseInterface):

    def __init__(self, database_url: str, db_type: DatabaseType):
        self.database_url = database_url
        self.db_type = db_type
        self._engine: Optional[AsyncEngine] = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database not initialized")
        return self._engine

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(self.engine) as session:
            yield session

    async def initialize(self) -> None:
        """Initialize database connection and create tables"""
        self._engine = create_async_engine(self.database_url,
                                           echo=False,
                                           future=True)

        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    async def create_transaction(
            self, transaction: TransactionCreate) -> TransactionModel:
        now = datetime.utcnow()
        stmt = insert(transactions).values(
            transaction_id=transaction.transaction_id,
            payment_processor=transaction.payment_processor,
            amount=transaction.amount,
            currency=transaction.currency,
            status=transaction.status,
            customer_id=transaction.customer_id,
            payment_method=transaction.payment_method,
            metadata=transaction.metadata,
            created_at=now,
            updated_at=now).returning(transactions)

        async with AsyncSession(self.engine) as session:
            result = await session.execute(stmt)
            await session.commit()
            row = result.fetchone()
            return TransactionModel.from_orm(row)

    async def update_transaction_status(
            self, transaction_id: str, status: str,
            payment_processor: str) -> Optional[TransactionModel]:
        now = datetime.utcnow()
        stmt = (update(transactions).where(
            (transactions.c.transaction_id == transaction_id)
            & (transactions.c.payment_processor == payment_processor)).values(
                status=status, updated_at=now).returning(transactions))

        async with AsyncSession(self.engine) as session:
            result = await session.execute(stmt)
            await session.commit()
            row = result.fetchone()
            if row:
                return TransactionModel.from_orm(row)
            return None

    async def get_transaction(
            self, transaction_id: str,
            payment_processor: str) -> Optional[TransactionModel]:
        stmt = select(transactions).where(
            (transactions.c.transaction_id == transaction_id)
            & (transactions.c.payment_processor == payment_processor))

        async with AsyncSession(self.engine) as session:
            result = await session.execute(stmt)
            row = result.fetchone()
            if row:
                return TransactionModel.from_orm(row)
            return None

    async def get_transactions_by_customer(
            self,
            customer_id: str,
            limit: int = 100,
            offset: int = 0) -> List[TransactionModel]:
        stmt = (select(transactions).where(
            transactions.c.customer_id == customer_id).order_by(
                transactions.c.created_at.desc()).limit(limit).offset(offset))

        async with AsyncSession(self.engine) as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
            return [TransactionModel.from_orm(row) for row in rows]

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
