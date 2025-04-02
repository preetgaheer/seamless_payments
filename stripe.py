import logging
from typing import Optional

from seamless_payments.config import GlobalConfig, MetaConfig, StripeConfig

# Local imports
from seamless_payments.payment_processors.stripe import StripeClient
from seamless_payments.resources.stripe import Invoice, PaymentIntent, Customer

logger = logging.getLogger(__name__)

# Module-level configuration
api_key: Optional[str] = None
timeout: int = 30
max_retries: int = 3
brand_name: str = "My Online Store"

# Module-level client instance
_client: Optional[StripeClient] = None


def _initialize_client():
    """Initialize the client with current module settings"""
    global _client
    if not api_key:
        raise ValueError("Stripe API key not configured. Set stripe.api_key")

    stripe_config = StripeConfig(STRIPE_API_KEY=api_key)
    global_config = GlobalConfig(timeout=timeout, max_retries=max_retries)
    meta_config = MetaConfig(BRAND_NAME=brand_name)

    _client = StripeClient(api_key=stripe_config.STRIPE_API_KEY,
                           timeout=global_config.TIMEOUT,
                           max_retries=global_config.MAX_RETRIES)

    # Initialize resources
    Invoice._client = _client
    Invoice._brand_name = meta_config.BRAND_NAME
    # Invoice._return_url = meta_config.RETURN_URL
    # Invoice._cancel_url = meta_config.CANCEL_URL

    PaymentIntent._client = _client

    Customer._client = _client
    Customer._brand_name = meta_config.BRAND_NAME


# Expose resources at module level
Invoice = Invoice
PaymentIntent = PaymentIntent
Customer = Customer
