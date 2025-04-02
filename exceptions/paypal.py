class PayPalError(Exception):
    """Base exception for all PayPal-related errors"""
    pass


class PayPalConfigurationError(PayPalError):
    """Raised when PayPal is not properly configured"""
    pass


class PayPalAuthenticationError(PayPalError):
    """Raised when PayPal authentication fails"""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class PayPalAPIError(PayPalError):
    """Raised when PayPal API returns an error"""

    def __init__(self, message, http_status=None, json_body=None):
        super().__init__(message)
        self.http_status = http_status
        self.json_body = json_body


class PayPalValidationError(PayPalError):
    """Raised when PayPal data validation fails"""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


class PayPalInvoiceError(PayPalError):
    """Base class for invoice-related errors"""
    pass


class PayPalInvoiceCreationError(PayPalInvoiceError):
    """Raised when invoice creation fails"""
    pass


class PayPalOrderError(PayPalError):
    """Base class for order-related errors"""
    pass


class PayPalOrderCreationError(PayPalOrderError):
    """Raised when order creation fails"""
    pass


class PayPalPaymentCaptureError(PayPalOrderError):
    """Raised when payment capture fails"""

    def __init__(self, message, order_id=None):
        super().__init__(message)
        self.order_id = order_id
