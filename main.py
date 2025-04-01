import asyncio
import logging
from datetime import datetime, timedelta

from app.exceptions.core import PaymentProcessorError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Local imports
from app.payment_processor.paypal import (PayPalPaymentProcessor, PayPalClient,
                                          PayPalEnvironment)
from app.schemas.core import (InvoiceRequest, CustomerDetails, Item, Currency)

# Configuration - ideally load from environment variables in production
CONFIG = {
    "PAYPAL_CLIENT_ID":
    "AevnETK9IHPSxlUmHbzJADnkuaSJvZeTvaAyQpGyZVuyJ8WgUXWFIZnE46bXR58wiB8IyC2Kq0vGhWdQ",
    "PAYPAL_CLIENT_SECRET":
    "ENxqM1Locis8yNVk9niDDUrs6e76wfVeTxFKxfWB1syRYJYIEenf5BuggkIFheos1cefaTVFw6fCmR_U",
    "BRAND_NAME": "My Online Store",
    "RETURN_URL": "https://my-store.com/payment/return",
    "CANCEL_URL": "https://my-store.com/payment/cancel",
    "ENVIRONMENT": "sandbox"  # or "production"
}


async def main():
    try:
        # Initialize PayPal client
        paypal_client = PayPalClient(
            environment=PayPalEnvironment.SANDBOX if CONFIG["ENVIRONMENT"]
            == "sandbox" else PayPalEnvironment.PRODUCTION,
            client_id=CONFIG["PAYPAL_CLIENT_ID"],
            client_secret=CONFIG["PAYPAL_CLIENT_SECRET"],
            timeout=30,
            max_retries=3)

        # Initialize payment processor
        processor = PayPalPaymentProcessor(paypal_client=paypal_client,
                                           brand_name=CONFIG["BRAND_NAME"],
                                           return_url=CONFIG["RETURN_URL"],
                                           cancel_url=CONFIG["CANCEL_URL"])

        # Create invoice data
        invoice_data = InvoiceRequest(
            customer=CustomerDetails(name="John Doe",
                                     email="john@example.com",
                                     phone="+1234567890"),
            items=[Item(name="Product 1", price=19.99, quantity=2)],
            currency=Currency.USD,
            notes="Thank you for your business!",
            due_date=datetime.now() +
            timedelta(days=10)  # Must be 10 days for NET_10
        )

        payment = await processor.create_and_pay_invoice(invoice_data)
        print(f"Payment successful! ID: {payment.payment_id}")

    except ValueError as e:
        print(f"\nValidation error: {str(e)}")
        print("Please ensure:")
        print("- Due date is in the future")
        print("- For NET_10 terms, due date must be exactly 10 days from now")
    except PaymentProcessorError as e:
        print(f"\nPayment processing error: {str(e)}")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
