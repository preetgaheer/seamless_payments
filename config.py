from enum import Enum
from pydantic import Field, AnyUrl, BaseModel


class EnvironmentChoice(Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class PayPalConfig(BaseModel):
    # PayPal Config
    PAYPAL_CLIENT_ID: str = Field(...)
    PAYPAL_CLIENT_SECRET: str = Field(...)
    PAYPAL_ENVIRONMENT: str = Field(EnvironmentChoice.SANDBOX)
    PAYPAL_RETURN_URL: AnyUrl = Field("https://yourdomain.com/payment/return")
    PAYPAL_CANCEL_URL: AnyUrl = Field("https://yourdomain.com/payment/cancel")


class StripeConfig(BaseModel):

    # Stripe Config
    STRIPE_ENVIRONMENT: str = Field(EnvironmentChoice.SANDBOX.value)
    STRIPE_API_KEY: str = Field(...)
    STRIPE_WEBHOOK_SECRET: str = Field(...)


class GlobalConfig(BaseModel):
    TIMEOUT: int = Field(30)
    MAX_RETRIES: int = Field(3)


class MetaConfig(BaseModel):
    BRAND_NAME: str = Field("My Online Store")
    RETURN_URL: AnyUrl = Field("https://yourdomain.com/payment/return")
    CANCEL_URL: AnyUrl = Field("https://yourdomain.com/payment/cancel")
