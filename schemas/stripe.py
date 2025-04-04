from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, computed_field


class StripeCurrency(str, Enum):
    USD = "usd"
    INR = "inr"


class StripeCustomer(BaseModel):
    """Customer schema for Stripe operations"""
    id: Optional[str] = Field(
        None, description="Stripe customer ID if already exists")
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    tax_id: Optional[str] = Field(
        None, description="Tax ID/VAT number for the customer")
    metadata: Optional[Dict[str,
                            str]] = Field(None,
                                          description="Additional metadata")


class StripeCustomerRequest(BaseModel):
    """Request schema for creating Stripe customers"""
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    tax_id: Optional[str] = Field(
        None, description="Tax ID/VAT number for the customer")
    metadata: Optional[Dict[str,
                            str]] = Field(None,
                                          description="Additional metadata")


class StripeItem(BaseModel):
    """Line item for Stripe invoices"""
    name: str
    description: Optional[str] = None
    price: float = Field(..., gt=0, description="Price per unit")
    quantity: int = Field(1, gt=0)
    tax_rates: Optional[List[str]] = Field(
        None, description="List of tax rate IDs to apply")


class StripeInvoiceRequest(BaseModel):
    """Request schema for creating Stripe invoices"""
    customer: StripeCustomer
    items: List[StripeItem]
    currency: StripeCurrency = StripeCurrency.USD.value
    due_date: Optional[datetime] = Field(None,
                                         description="When the invoice is due")
    description: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    auto_advance: bool = Field(
        True, description="Whether to automatically advance the invoice")
    collection_method: str = Field(
        "charge_automatically",
        description="'charge_automatically' or 'send_invoice'")
    days_until_due: int = Field(
        30, description="Number of days until invoice is due")

    @computed_field
    @property
    def total_amount(self) -> float:
        """Sum of all item prices multiplied by their quantities"""
        return sum(item.price * item.quantity for item in self.items)

    # @validator('days_until_due')
    # def validate_days_until_due(cls, v):
    #     if v < 1 or v > 365:
    #         raise ValueError("Days until due must be between 1 and 365")
    #     return v


class StripeInvoiceResponse(BaseModel):
    """Response schema for Stripe invoices"""
    id: str = Field(..., description="Stripe invoice ID")
    number: str = Field(..., description="Human-readable invoice number")
    status: str = Field(..., description="Invoice status")
    amount_due: float = Field(..., description="Amount due in currency units")
    amount_paid: float = Field(0, description="Amount paid in currency units")
    currency: StripeCurrency
    due_date: Optional[datetime]
    hosted_invoice_url: Optional[str] = Field(
        None, description="URL for the hosted invoice page")
    invoice_pdf: Optional[str] = Field(None,
                                       description="URL for the PDF version")
    created_at: datetime
    metadata: Dict[str, str] = Field(default_factory=dict)
    # customer: StripeCustomer


class StripePaymentIntentRequest(BaseModel):
    """Request schema for creating PaymentIntents"""
    amount: float = Field(..., gt=0, description="Amount in currency units")
    currency: StripeCurrency
    invoice_id: Optional[str] = Field(None,
                                      description="Associated invoice ID")
    customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    payment_method_id: Optional[str] = Field(
        None, description="Saved payment method ID")
    metadata: Dict[str, str] = Field(default_factory=dict)


class StripePaymentIntentResponse(BaseModel):
    """Response schema for PaymentIntents"""
    id: str = Field(..., description="PaymentIntent ID")
    client_secret: str = Field(
        ..., description="Client secret for client-side confirmation")
    amount: float = Field(..., description="Amount in currency units")
    currency: StripeCurrency
    status: str = Field(..., description="PaymentIntent status")
    invoice_id: Optional[str] = Field(None,
                                      description="Associated invoice ID")
    created_at: datetime
    next_action: Optional[Dict[str, Any]] = Field(
        None, description="Next action required for payment")


class StripePaymentResponse(BaseModel):
    """Response schema for completed payments"""
    id: str = Field(..., description="Payment ID")
    amount: float = Field(..., description="Amount captured in currency units")
    currency: StripeCurrency
    status: str = Field(..., description="Payment status")
    # invoice_id: Optional[str]
    # payment_method: str = Field(..., description="Type of payment method used")
    receipt_url: Optional[str] = Field(
        None, description="URL for the payment receipt")
    captured_at: datetime


class StripeInvoiceItemRequest(BaseModel):
    """
    Schema for creating a Stripe invoice item.
    
    Can be used for both standalone invoice items and items attached to invoices.
    """
    customer_id: str = Field(
        ...,
        description="The ID of the customer who will be billed",
        example="cus_ABC123456789")

    # Price reference (either price_id or amount+currency+product info must be provided)
    price_id: Optional[str] = Field(
        None,
        description="The ID of an existing price to use",
        example="price_ABC123456789")

    # Ad-hoc pricing fields (used when price_id is not provided)
    amount: Optional[float] = Field(
        None,
        description=
        "The unit amount in the currency's smallest unit (e.g. cents for USD)",
        gt=0,
        example=1000.00)
    currency: Optional[StripeCurrency] = Field(
        None,
        description="Three-letter ISO currency code",
        example=StripeCurrency.USD)
    product_name: Optional[str] = Field(
        None,
        description="The product's name for ad-hoc items",
        max_length=300,
        example="Premium Subscription")
    product_description: Optional[str] = Field(
        None,
        description="The product's description for ad-hoc items",
        max_length=1000,
        example="Annual subscription plan")

    # Common fields
    quantity: int = Field(1,
                          description="Quantity of this item",
                          gt=0,
                          example=2)
    description: Optional[str] = Field(
        None,
        description="A description of this invoice item",
        max_length=1000,
        example="Annual subscription for 2023")
    period_start: Optional[datetime] = Field(
        None, description="Start of the billing period for this item")
    period_end: Optional[datetime] = Field(
        None, description="End of the billing period for this item")
    metadata: Optional[Dict[str, str]] = Field(
        None,
        description="Key-value pairs for storing additional information",
        example={
            "project_id": "proj_123",
            "department": "marketing"
        })
    tax_rates: Optional[List[str]] = Field(
        None,
        description="List of tax rate IDs to apply to this item",
        example=["txr_123", "txr_456"])
    discountable: Optional[bool] = Field(
        None, description="Whether discounts apply to this item", example=True)

    # # Validators
    # @validator('amount')
    # def validate_amount(cls, v, values):
    #     if v is not None and 'currency' not in values:
    #         raise ValueError("Currency must be provided when specifying amount")
    #     return v

    # @validator('product_name')
    # def validate_product_name(cls, v, values):
    #     if v is not None and 'price_id' in values and values['price_id'] is not None:
    #         raise ValueError("Cannot specify both price_id and product_name")
    #     return v

    # class Config:
    #     use_enum_values = True
    #     extra = "forbid"
    #     json_encoders = {
    #         datetime: lambda v: int(v.timestamp()) if v else None
    #     }

    # def dict(self, **kwargs):
    #     """Override dict to handle special cases"""
    #     data = super().dict(**kwargs)

    #     # Convert amount to cents if present
    #     if 'amount' in data and data['amount'] is not None:
    #         data['amount'] = int(data['amount'] * 100)

    #     # Remove None values
    #     return {k: v for k, v in data.items() if v is not None}
