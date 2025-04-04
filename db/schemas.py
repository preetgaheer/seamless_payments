from typing import Optional, Dict, Any
import uuid
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
    PARTIALLY_REFUNDED = "partially_refunded"
    STARTED = "started"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    COMPLETED = "completed"


class TransactionBase(BaseModel):
    # id: Optional[str] = Field(
    #     default_factory=lambda: str(uuid.uuid4()),
    #     description="Unique ID for this database record"
    # )
    transaction_id: str = Field(
        ...,
        description="Unique ID for the entire transaction session"
    )
    event_id: str = Field(
        ...,
        description="Unique ID for this specific event"
    )
    event_type: str = Field(..., description="Type of payment event")
    payment_processor: str = Field(..., description="Stripe or PayPal")
    resource_id: str = Field(
        ...,
        description="ID of the specific resource (invoice, payment intent, etc.)"
    )
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
    processor_metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Metadata from payment processor")
    parent_event_id: Optional[str] = Field(
        None,
        description="Reference to parent event in this transaction"
    )


    model_config = ConfigDict(
        from_attributes=True,  # Previously orm_mode=True
        populate_by_name=True,  # Previously allow_population_by_field_name=True
        use_enum_values=True)


class TransactionCreate(TransactionBase):
    pass


class TransactionModel(TransactionBase):
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this database record"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    # updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True
        use_enum_values = True
