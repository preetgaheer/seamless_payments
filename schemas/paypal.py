from decimal import Decimal
from enum import Enum
from typing import Annotated, Optional, List, Dict
from datetime import datetime
from pydantic import (BaseModel, Field, EmailStr, PositiveInt, field_validator,
                      condecimal)


class PayPalCurrency(str, Enum):
    USD = "USD"
    INR = "INR"


class PayPalAddress(BaseModel):
    """Address schema for PayPal"""
    line1: str = Field(..., max_length=100)
    line2: Optional[str] = Field(None, max_length=100)
    city: str = Field(..., max_length=50)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: str = Field(..., max_length=20)
    country_code: str = Field(..., min_length=2, max_length=2)


class PayPalCustomer(BaseModel):
    """Customer schema for PayPal operations"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None,
                                 pattern=r'^\+?[1-9]\d{1,14}$',
                                 description="Phone number in E.164 format")
    address: Optional[PayPalAddress] = None
    tax_id: Optional[str] = Field(
        None, description="Tax ID/VAT number for the customer", max_length=20)
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata about the customer")


class PayPalItem(BaseModel):
    """Line item for PayPal invoices/orders"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    quantity: PositiveInt = Field(1, le=1000)
    price: Annotated[Decimal,
                     condecimal(ge=0,
                                decimal_places=2)]  # Ensures 2 decimal places
    sku: Optional[str] = Field(None, max_length=50)
    tax: Optional[Annotated[Decimal,
                            condecimal(ge=0, decimal_places=2)]] = None


class PayPalInvoiceRequest(BaseModel):
    """Request schema for creating PayPal invoices"""
    customer: PayPalCustomer
    items: List[PayPalItem] = Field(..., min_items=1)
    currency: PayPalCurrency = PayPalCurrency.USD
    due_date: Optional[datetime] = Field(
        None,
        description="When the invoice is due (defaults to 10 days if not set)")
    notes: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata about the invoice")
    allow_partial_payment: bool = Field(
        False, description="Whether to allow partial payments")
    minimum_amount_due: Optional[Annotated[
        Decimal, condecimal(ge=0, decimal_places=2)]] = Field(
            None, description="Minimum amount required for partial payments")

    @field_validator('due_date')
    def validate_due_date(cls, v):
        if v and v <= datetime.now():
            raise ValueError("Due date must be in the future")
        return v


class PayPalOrderRequest(BaseModel):
    """Request schema for creating PayPal orders"""
    invoice_id: Optional[str] = Field(
        None, description="Associated invoice ID if applicable")
    amount: Annotated[Decimal, condecimal(ge=0, decimal_places=2)]
    currency: PayPalCurrency
    items: Optional[List[PayPalItem]] = Field(
        None, description="Items included in this order")
    return_url: str = Field(...,
                            description="URL to return after payment approval")
    cancel_url: str = Field(...,
                            description="URL to return if payment is canceled")
    custom_id: Optional[str] = Field(None,
                                     max_length=127,
                                     description="Custom ID for tracking")


class PayPalInvoiceResponse(BaseModel):
    """Response schema for PayPal invoices"""
    # id: str = Field(..., description="PayPal invoice ID")
    # number: str = Field(..., description="Invoice number")
    # status: str = Field(..., description="Invoice status")
    # amount: Annotated[Decimal, condecimal(ge=0, decimal_places=2)]
    # currency: PayPalCurrency
    # due_date: Optional[datetime]
    # links: List[Dict[str, str]] = Field(
    #     ..., description="HATEOAS links for invoice actions")
    # created_at: datetime
    # metadata: Dict[str, str] = Field(
    #     default_factory=dict,
    #     description="Metadata associated with the invoice")

    invoice_id: str
    payment_url: Optional[str] = None
    status: str
    amount_due: Annotated[Decimal, condecimal(ge=0, decimal_places=2)]
    currency: str
    due_date: Optional[datetime] = None


class PayPalOrderResponse(BaseModel):
    """Response schema for PayPal orders"""
    id: str = Field(..., description="PayPal order ID")
    status: str = Field(..., description="Order status")
    amount: Annotated[Decimal, condecimal(ge=0, decimal_places=2)]
    currency: PayPalCurrency
    create_time: datetime
    links: List[Dict[str, str]] = Field(
        ..., description="HATEOAS links for order actions")
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Metadata associated with the order")

    # payment_id: str
    # invoice_id: str
    # amount: float
    # currency: str
    # status: str
    # captured_at: datetime


class PayPalPaymentResponse(BaseModel):
    """Response schema for completed PayPal payments"""
    # id: str = Field(..., description="Payment ID")
    # order_id: str = Field(..., description="Associated order ID")
    # invoice_id: Optional[str] = Field(
    #     None, description="Associated invoice ID if applicable")
    # amount: Annotated[Decimal, condecimal(ge=0, decimal_places=2)]
    # currency: PayPalCurrency
    # status: str = Field(..., description="Payment status")
    # payer_email: Optional[EmailStr] = Field(None,
    #                                         description="Email of the payer")
    # captured_at: datetime
    # links: List[Dict[str, str]] = Field(
    #     default_factory=list, description="HATEOAS links for payment actions")

    payment_id: str
    invoice_id: str
    amount: float
    currency: str
    status: str
    captured_at: datetime
