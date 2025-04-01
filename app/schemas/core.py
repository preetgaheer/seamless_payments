from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, PositiveInt, field_validator
from datetime import datetime


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"


class CustomerDetails(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(
        None,
        pattern=r'^\+?[1-9]\d{1,14}$',  # Changed from regex to pattern
        examples=["+1234567890", "1234567890"],
        description="Phone number in E.164 format")


class Item(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    quantity: PositiveInt = 1
    price: float = Field(..., gt=0)

    @field_validator('price')
    def round_price(cls, v):
        return round(v, 2)


class InvoiceRequest(BaseModel):
    customer: CustomerDetails
    items: list[Item] = Field(..., min_items=1)
    currency: Currency = Currency.USD
    due_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('due_date')
    def validate_due_date(cls, v):
        if v and v <= datetime.now():
            raise ValueError("Due date must be in the future")
        return v


class PaymentCaptureRequest(BaseModel):
    invoice_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)

    @field_validator('amount')
    def round_amount(cls, v):
        return round(v, 2)


class InvoiceResponse(BaseModel):
    invoice_id: str
    payment_url: Optional[str] = None
    status: str
    amount_due: float
    currency: str
    due_date: Optional[datetime] = None


class PaymentResponse(BaseModel):
    payment_id: str
    invoice_id: str
    amount: float
    currency: str
    status: str
    captured_at: datetime
