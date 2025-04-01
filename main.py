# This script demonstrates how to use the SeamlessPayPalClient to create and pay an invoice.
# It uses environment variables for configuration, making it easy to adapt to different environments.
# Make sure to set up your .env file with the required variables:

import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# seamless_payments library imports
from seamless_payments import SeamlessPayPalClient
from seamless_payments.app.schemas.core import (InvoiceRequest,
                                                CustomerDetails, Item,
                                                Currency)

# Load environment variables from .env file
load_dotenv()

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
ENVIRONMENT = os.getenv("ENVIRONMENT", "sandbox")
BRAND_NAME = os.getenv("BRAND_NAME", "My Online Store")
RETURN_URL = os.getenv("RETURN_URL")
CANCEL_URL = os.getenv("CANCEL_URL")


async def main():
    try:
        # Initialize PayPal client using environment variables
        client = SeamlessPayPalClient(client_id=PAYPAL_CLIENT_ID,
                                      client_secret=PAYPAL_CLIENT_SECRET,
                                      environment=ENVIRONMENT,
                                      brand_name=BRAND_NAME,
                                      return_url=RETURN_URL,
                                      cancel_url=CANCEL_URL)

        # Prepare invoice data
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

        # Create invoice
        payment = await client.create_and_pay_invoice(invoice_data)
        print(f"Payment successful! ID: {payment.payment_id}")

    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
