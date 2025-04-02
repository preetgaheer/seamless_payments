from enum import Enum
from pydantic import Field, AnyUrl, field_validator, BaseModel


class ProcessorChoice(str, Enum):
    PAYPAL = "paypal"
    STRIPE = "stripe"


class EnvironmentChoice(Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PayPalConfig(BaseModel):
    ACTIVE_PROCESSOR: ProcessorChoice = Field(ProcessorChoice.PAYPAL.value)

    # PayPal Config
    PAYPAL_CLIENT_ID: str = Field(...)
    PAYPAL_CLIENT_SECRET: str = Field(...)
    PAYPAL_ENVIRONMENT: str = Field(EnvironmentChoice.SANDBOX)
    PAYPAL_RETURN_URL: AnyUrl = Field("https://yourdomain.com/payment/return")
    PAYPAL_CANCEL_URL: AnyUrl = Field("https://yourdomain.com/payment/cancel")

    # @field_validator('PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET')
    # def validate_paypal_fields(cls, v, values, field):
    #     if values.get(
    #             'ACTIVE_PROCESSOR') == ProcessorChoice.PAYPAL and v is None:
    #         raise ValueError(f"{field.name} is required when using PayPal")
    #     return v


class StripeConfig(BaseModel):
    ACTIVE_PROCESSOR: ProcessorChoice = Field(ProcessorChoice.STRIPE.value)

    # Stripe Config
    STRIPE_ENVIRONMENT: str = Field(EnvironmentChoice.SANDBOX.value)
    STRIPE_API_KEY: str = Field(...)
    STRIPE_WEBHOOK_SECRET: str = Field(...)

    # @field_validator('STRIPE_API_KEY', 'STRIPE_WEBHOOK_SECRET')
    # def validate_stripe_fields(cls, v, values, field):
    #     if values.get(
    #             'ACTIVE_PROCESSOR') == ProcessorChoice.STRIPE and v is None:
    #         raise ValueError(f"{field.name} is required when using Stripe")
    #     return v


class GlobalConfig(BaseModel):
    TIMEOUT: int = Field(30)
    MAX_RETRIES: int = Field(3)


class MetaConfig(BaseModel):
    BRAND_NAME: str = Field("My Online Store")
    RETURN_URL: AnyUrl = Field("https://yourdomain.com/payment/return")
    CANCEL_URL: AnyUrl = Field("https://yourdomain.com/payment/cancel")
