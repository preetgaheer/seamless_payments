from abc import ABC, abstractmethod

# local imports
from seamless_payments.schemas.paypal import (
    InvoiceRequest,
    InvoiceResponse,
    PaymentCaptureRequest,
)
from seamless_payments.exceptions.paypal import (
    PaymentValidationError, )


class BasePaymentProcessor(ABC):
    """Abstract base class for all payment processors"""

    @abstractmethod
    async def create_invoice(self,
                             invoice_data: InvoiceRequest) -> InvoiceResponse:
        """Create an invoice for payment"""
        pass

    # @abstractmethod
    # async def capture_payment(
    #         self, capture_data: PaymentCaptureRequest) -> PaymentResponse:
    #     """Capture payment for an invoice"""
    #     pass

    # @abstractmethod
    # async def get_invoice(self, invoice_id: str) -> InvoiceResponse:
    #     """Retrieve invoice details"""
    #     pass

    def validate_invoice_data(self, invoice_data: InvoiceRequest) -> None:
        """Validate invoice data before processing"""
        try:
            # For Pydantic v2, existing instances are already validated
            # We can force re-validation by converting to dict and back
            validated_data = invoice_data.model_dump()
            InvoiceRequest.model_validate(validated_data)
        except Exception as e:
            raise PaymentValidationError(f"Invalid invoice data: {str(e)}")

    def validate_capture_data(self,
                              capture_data: PaymentCaptureRequest) -> None:
        """Validate payment capture data before processing"""
        try:
            # Same approach for capture data
            validated_data = capture_data.model_dump()
            PaymentCaptureRequest.model_validate(validated_data)
        except Exception as e:
            raise PaymentValidationError(f"Invalid capture data: {str(e)}")
