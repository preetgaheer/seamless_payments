import logging
from typing import Optional

from seamless_payments.config import GlobalConfig, MetaConfig, PayPalConfig

# local imports
from seamless_payments.payment_processors.paypal import PayPalClient
from seamless_payments.resources.paypal import Invoice, Order

logger = logging.getLogger(__name__)

# Module-level configuration
client_id: Optional[str] = None
client_secret: Optional[str] = None
environment: str = "sandbox"
timeout: int = 30
max_retries: int = 3
brand_name: str = "My Online Store"
return_url: str = "https://yourdomain.com/payment/return"
cancel_url: str = "https://yourdomain.com/payment/cancel"

# Module-level client instance
_client: Optional[PayPalClient] = None


def _initialize_client():
    """Initialize the client with current module settings"""
    global _client
    if not client_id or not client_secret:
        raise ValueError(
            "PayPal credentials not configured. Set paypal.client_id" /
            "and paypal.client_secret")

    paypal_config = PayPalConfig(
        PAYPAL_CLIENT_ID=client_id,
        PAYPAL_CLIENT_SECRET=client_secret,
        PAYPAL_ENVIRONMENT=environment,
    )
    global_config = GlobalConfig(timeout=timeout, max_retries=max_retries)
    meta_config = MetaConfig(
        BRAND_NAME=brand_name,
        RETURN_URL=return_url,
        CANCEL_URL=cancel_url,
    )

    _client = PayPalClient(environment=paypal_config.PAYPAL_ENVIRONMENT,
                           client_id=paypal_config.PAYPAL_CLIENT_ID,
                           client_secret=paypal_config.PAYPAL_CLIENT_SECRET,
                           timeout=global_config.TIMEOUT,
                           max_retries=global_config.MAX_RETRIES)

    # Initialize resources
    Invoice._client = _client
    Invoice._brand_name = meta_config.BRAND_NAME
    Invoice._return_url = meta_config.RETURN_URL
    Invoice._cancel_url = meta_config.CANCEL_URL

    Order._client = _client
    Order._brand_name = meta_config.BRAND_NAME
    Order._return_url = meta_config.RETURN_URL
    Order._cancel_url = meta_config.CANCEL_URL


# Expose resources at module level
Invoice = Invoice
Order = Order
