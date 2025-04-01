from typing import Literal
from app.payment_processor.base import BasePaymentProcessor
from app.payment_processor.paypal import PayPalPaymentProcessor
from app.payment_processor.stripe import StripeProcessor


def get_payment_processor(processor_type: Literal["paypal", "stripe"],
                          **kwargs) -> BasePaymentProcessor:
    """Factory function to get payment processor instance"""
    processors = {"paypal": PayPalPaymentProcessor, "stripe": StripeProcessor}

    if processor_type not in processors:
        raise ValueError(f"Unsupported processor type: {processor_type}")

    return processors[processor_type](**kwargs)
