import os
import sys
import logging
from pathlib import Path

# Local imports
from .app.payment_processor.paypal import (PayPalPaymentProcessor,
                                           PayPalClient)
from .config import (GlobalConfig, MetaConig, PayPalConfig, EnvironmentChoice)

# Add parent directory to Python path
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

print('parent_dir: ', parent_dir)
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class SeamlessPayPalClient():

    def __init__(
            self,
            client_id: str,
            client_secret: str,
            environment: EnvironmentChoice = EnvironmentChoice.SANDBOX.value,
            # global_config
            timeout: int = 30,
            max_retries: int = 3,
            # meta details
            brand_name: str = "My Online Store",
            return_url: str = "https://yourdomain.com/payment/return",
            cancel_url: str = "https://yourdomain.com/payment/cancel",
            *args,
            **kwargs):
        paypal_config = PayPalConfig(
            PAYPAL_CLIENT_ID=client_id,
            PAYPAL_CLIENT_SECRET=client_secret,
            PAYPAL_ENVIRONMENT=environment,
        )
        global_config = GlobalConfig(timeout=timeout, max_retries=max_retries)
        meta_config = MetaConig(
            brand_name=brand_name,
            return_url=return_url,
            cancel_url=cancel_url,
        )

        self._paypal_client = PayPalClient(
            environment=paypal_config.PAYPAL_ENVIRONMENT,
            client_id=paypal_config.PAYPAL_CLIENT_ID,
            client_secret=paypal_config.PAYPAL_CLIENT_SECRET,
            timeout=global_config.timeout,
            max_retries=global_config.max_retries)

        # Initialize payment processor
        self._processor = PayPalPaymentProcessor(
            paypal_client=self._paypal_client,
            brand_name=meta_config.brand_name,
            return_url=meta_config.return_url.encoded_string(),
            cancel_url=meta_config.cancel_url.encoded_string(),)

    async def create_and_pay_invoice(self, invoice_data):
        """Public method that delegates to the processor"""
        return await self._processor.create_and_pay_invoice(invoice_data)
