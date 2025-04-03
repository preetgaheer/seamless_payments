from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import logging
from datetime import datetime
from pydantic import ConfigDict

logger = logging.getLogger(__name__)


class DatabaseType(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    MYSQL = "mysql"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class TransactionBase(BaseModel):
    transaction_id: str = Field(
        ..., description="Unique transaction ID from payment processor")
    payment_processor: str = Field(..., description="Stripe or PayPal")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    status: TransactionStatus = Field(..., description="Transaction status")
    customer_id: Optional[str] = Field(default=None,
                                       description="Customer ID if available")
    payment_method: Optional[str] = Field(default=None,
                                          description="Payment method used")
    metadata: Optional[Dict[str,
                            Any]] = Field(default=None,
                                          description="Additional metadata")

    model_config = ConfigDict(
        from_attributes=True,  # Previously orm_mode=True
        populate_by_name=True,  # Previously allow_population_by_field_name=True
        use_enum_values=True)


class TransactionCreate(TransactionBase):
    pass


class TransactionModel(TransactionBase):
    id: int = Field(..., description="Primary key")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True
        use_enum_values = True
