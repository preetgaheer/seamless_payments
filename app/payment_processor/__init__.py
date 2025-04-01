from typing import Literal
from .base import BasePaymentProcessor
from .paypal import PayPalPaymentProcessor
from .stripe import StripeProcessor


def get_payment_processor(processor_type: Literal["paypal", "stripe"],
                          **kwargs) -> BasePaymentProcessor:
    """Factory function to get payment processor instance"""
    processors = {"paypal": PayPalPaymentProcessor, "stripe": StripeProcessor}

    if processor_type not in processors:
        raise ValueError(f"Unsupported processor type: {processor_type}")

    return processors[processor_type](**kwargs)
