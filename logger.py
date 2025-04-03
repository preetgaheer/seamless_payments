import logging
import os


def _initialize_logger():
    """Initialize loggers: 'paypal_logger' (INFO, WARNING, ERROR)
    and 'stripe_logger' (INFO, WARNING, ERROR) ."""

    # Ensure "logs" folder exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Log file paths
    paypal_log_file = os.path.join(log_dir, "paypal.log")
    stripe_log_file = os.path.join(log_dir, "stripe.log")

    # Ensure log files exist
    for log_file in [paypal_log_file, stripe_log_file]:
        if not os.path.exists(log_file):
            open(log_file, "w").close()  # Create empty file if not exists

    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    paypal_logger = logging.getLogger("paypal")
    paypal_logger.setLevel(logging.INFO)

    paypal_handler = logging.FileHandler(paypal_log_file)
    paypal_handler.setFormatter(formatter)
    paypal_logger.addHandler(paypal_handler)

    stripe_logger = logging.getLogger("stripe")
    stripe_logger.setLevel(logging.INFO)

    stripe_handler = logging.FileHandler(stripe_log_file)
    stripe_handler.setFormatter(formatter)
    stripe_logger.addHandler(stripe_handler)

    return paypal_logger, stripe_logger  # Return loggers for use
