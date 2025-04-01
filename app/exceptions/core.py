class PaymentProcessorError(Exception):
    """Base exception for payment processor errors"""
    pass


class PaymentValidationError(PaymentProcessorError):
    """Raised when payment data validation fails"""
    pass


class PaymentCaptureError(PaymentProcessorError):
    """Raised when payment capture fails"""
    pass


class InvoiceGenerationError(PaymentProcessorError):
    """Raised when invoice generation fails"""
    pass
