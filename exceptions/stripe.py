class StripeError(Exception):
    """Base exception for all Stripe-related errors"""
    pass


class StripeAuthenticationError(StripeError):
    """Base exception for all Stripe-related errors"""
    pass


class StripeInvoiceCreationError(StripeError):
    """Base exception for all Stripe-related errors"""
    pass


class StripePaymentIntentError(StripeError):
    """Base exception for all Stripe-related errors"""
    pass


class StripeConfigurationError(StripeError):
    """Raised when Stripe is not properly configured"""
    pass


class StripeInvoiceGenerationError(StripeError):
    """Raised when invoice creation fails"""
    pass


class PaymentIntentError(StripeError):
    """Base class for PaymentIntent related errors"""
    pass


class PaymentIntentCreationError(PaymentIntentError):
    """Raised when PaymentIntent creation fails"""
    pass


class PaymentCaptureError(PaymentIntentError):
    """Raised when payment capture fails"""
    pass


class CustomerCreationError(StripeError):
    """Raised when customer creation fails"""
    pass


class StripeCustomerRetrievalError(StripeError):
    """Raised when customer creation fails"""
    pass




class StripeInvoiceItemCreationError(StripeError):
    """Raised when customer creation fails"""
    pass


class StripeCustomerCreationError(StripeError):
    """Raised when customer creation fails"""
    pass


class CardError(StripeError):
    """Raised when there's an issue with the payment card"""

    def __init__(self, message, code=None, decline_code=None, param=None):
        super().__init__(message)
        self.code = code
        self.decline_code = decline_code
        self.param = param


class StripeAPIError(StripeError):
    """Raised when the Stripe API returns an error"""

    def __init__(self, message, http_status=None, json_body=None):
        super().__init__(message)
        self.http_status = http_status
        self.json_body = json_body
