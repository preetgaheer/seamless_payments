import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import webbrowser

# local imports
from seamless_payments.manager import payment_transaction
import seamless_payments.stripe as stripe
from seamless_payments.schemas.stripe import (
    StripeCustomerRequest,
    StripeInvoiceRequest,
    StripeItem,
    StripeCurrency,
)
from seamless_payments import paypal
from seamless_payments.schemas.paypal import (
    PayPalCustomer,
    PayPalInvoiceRequest,
    PayPalItem,
    PayPalCurrency,
)
from seamless_payments.db.init import db_integration
from seamless_payments import app

# Load environment variables
load_dotenv()

app.initialize_logger()

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
ENVIRONMENT = os.getenv("ENVIRONMENT", "sandbox")

STRIPE_API_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

BRAND_NAME = os.getenv("BRAND_NAME", "My Online Store")
RETURN_URL = os.getenv("RETURN_URL")
CANCEL_URL = os.getenv("CANCEL_URL")

# FastAPI app
app = FastAPI()

# Global state (for demo only - use DB in production)
payment_intent_data = None
payment_confirmation = False
payment_failure = False
payment_intent_id = None


def reset_payment_state():
    global payment_intent_data, payment_confirmation, payment_failure
    payment_intent_data = None
    payment_confirmation = False
    payment_failure = False
    print("Payment state reset!")


@app.post("/payment-auth-failure")
async def payment_auth_failure(request: Request):
    global payment_failure, payment_confirmation, payment_intent_id
    data = await request.json()
    payment_intent_id = data.get("payment_intent_id")
    payment_failure = True
    payment_confirmation = True

    error_message = data.get("error_message")

    if not payment_intent_id or not error_message:
        raise HTTPException(400, "Invalid request")

    # Log the failure (Can also send an email or trigger an alert)
    print(f"Payment authentication failed for {payment_intent_id}: {error_message}")

    return JSONResponse({"success": True, "message": "Failure recorded"})


@app.get("/payment-page", response_class=HTMLResponse)
async def get_payment_page():
    if not payment_intent_data:
        raise HTTPException(400, "PaymentIntent not initialized")

    return HTMLResponse(
        f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Stripe Payment</title>
        <script src="https://js.stripe.com/v3/"></script>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; }}
            #card-element {{ margin: 20px 0; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }}
            button {{ background: #6772e5; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }}
            #payment-message {{ margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h2>Complete Payment</h2>
        <div id="card-element"></div>
        <button id="submit-btn">Pay Now</button>
        <div id="payment-message"></div>

        <script>
            const stripe = Stripe('{STRIPE_PUBLISHABLE_KEY}');
            const elements = stripe.elements();
            const card = elements.create('card');
            card.mount('#card-element');

            document.getElementById('submit-btn').addEventListener('click', async () => {{
                const {{ paymentMethod, error }} = await stripe.createPaymentMethod({{
                    type: 'card',
                    card: card,
                }});

                if (error) {{
                    document.getElementById('payment-message').textContent = error.message;
                    return;
                }}

                // Attach payment method to PaymentIntent
                const response = await fetch('/attach-payment-method', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        payment_method_id: paymentMethod.id,
                        payment_intent_id: '{payment_intent_data['payment_intent_id']}'
                    }})
                }});

                const result = await response.json();
                if (!result.success) {{
                    document.getElementById('payment-message').textContent = 'Failed to attach payment method';
                    return;
                }}

                // Confirm payment on client side
                const {{ error: confirmError, paymentIntent }} = await stripe.confirmCardPayment(
                    '{payment_intent_data['client_secret']}', {{
                        payment_method: paymentMethod.id
                    }}
                );

                console.log(confirmError, paymentIntent);

                if (confirmError) {{
                    // implmenet api for payment failure
                    document.getElementById('payment-message').textContent = confirmError.message;

            // Notify backend about the failure
            await fetch('/payment-auth-failure', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    payment_intent_id: '{payment_intent_data['payment_intent_id']}',
                    error_message: confirmError.message
                }})
            }});
                    document.getElementById('payment-message').textContent = confirmError.message;
                }} else {{
                    if (paymentIntent.status === 'requires_action') {{
                        // Handle 3DS - Stripe.js will automatically handle the redirect
                        document.getElementById('payment-message').textContent = 'Please complete authentication';
                    }} else if (paymentIntent.status === 'requires_capture') {{
                        document.getElementById('payment-message').textContent = 'Payment succeeded!';
                        // Notify backend to capture
                        await fetch('/payment-confirmation', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{
                                payment_intent_id: paymentIntent.id,
                                status: paymentIntent.status
                            }})
                        }});
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    )


@app.post("/attach-payment-method")
async def attach_payment_method(request: Request):
    data = await request.json()
    try:
        await stripe.PaymentIntent.update(
            data["payment_intent_id"], payment_method=data["payment_method_id"]
        )
        return JSONResponse({"success": True})
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/payment-confirmation")
async def payment_confirmation_api(request: Request):
    global payment_confirmation
    data = await request.json()
    if data.get("status") == "requires_capture":
        payment_confirmation = True
        return JSONResponse({"success": True})
    raise HTTPException(400, "Payment not succeeded")


async def run_payment_flow():
    global payment_intent_data, payment_confirmation, payment_failure

    # Configure Stripe
    stripe.api_key = STRIPE_API_KEY
    stripe.brand_name = BRAND_NAME

    print("Stripe configured successfully!")
    print("Getting customer...")
    # Create or retrieve customer
    async with payment_transaction() as txn:
        customer_email = "johnjonga@new.com"
        customer = await txn.add(
            lambda txn_id: stripe.Customer.create_or_get(
                StripeCustomerRequest(
                    name="John Doe", email=customer_email, phone="+1234567890"
                ),
                txn_id,
            )
        )
        print("customer: ", customer)
        print("creating invoice ...")
        # Create invoice
        invoice = await txn.add(
            lambda txn_id: stripe.Invoice.create(
                StripeInvoiceRequest(
                    customer=customer,
                    items=[StripeItem(name="Product 1", price=15.42, quantity=2)],
                    currency=StripeCurrency.INR.value,
                    notes="Thank you for your business!",
                    due_date=datetime.now() + timedelta(days=10),
                ),
                txn_id,
            )
        )
        print(f"Invoice created! ID: {invoice.id}")

        # Create PaymentIntent from invoice
        print("Creating PaymentIntent from invoice ...")
        payment_intent = await txn.add(
            lambda txn_id: stripe.PaymentIntent.create_from_invoice(
                invoice, customer, txn_id
            )
        )
        print(f"PaymentIntent created! ID: {payment_intent['payment_intent_id']}")

    payment_intent_data = payment_intent
    print("payment_intent_data: ", payment_intent_data)
    # Open payment page
    webbrowser.open("http://localhost:8000/payment-page")

    # Wait for payment confirmation
    while not payment_confirmation:
        await asyncio.sleep(1)
    if payment_failure:
        print("Payment failed!")
        reset_payment_state()
        payment = await stripe.PaymentIntent.cancel(
            payment_intent_id,
            reason="auth failure",
        )

        return
    print("Payment confirmed!")
    print("Trying to capture payment ...")
    # 7. Capture payment (only if frontend confirmed success)
    try:
        payment = await stripe.PaymentIntent.capture(
            payment_intent_data["payment_intent_id"]
        )
        print(f"✅ Payment captured! ID: {payment.id}")
    except Exception as e:
        print(f"⚠️ Capture failed: {str(e)}")
        # Handle already captured case gracefully
        if "already been captured" in str(e):
            print("Payment already captured - all good!")
        else:
            raise
    finally:
        # Reset payment state
        reset_payment_state()


async def run_paypal():
    await db_init()
    # try:
    # Configure exactly like Stripe
    paypal.client_id = PAYPAL_CLIENT_ID
    paypal.client_secret = PAYPAL_CLIENT_SECRET
    paypal.environment = ENVIRONMENT
    paypal.brand_name = BRAND_NAME
    paypal.return_url = RETURN_URL
    paypal.cancel_url = CANCEL_URL
    paypal.timeout = 40
    paypal.max_retries = 3

    # Create invoice EXACTLY like Stripe
    print("Creating invoice ...")
    async with payment_transaction() as txn:
        invoice = await txn.add(
            lambda txn_id: paypal.Invoice.create(
                PayPalInvoiceRequest(
                    **{
                        "customer": PayPalCustomer(
                            name="John Doe",
                            email="john@example.com",
                            phone="+1234567890",
                        ),
                        "items": [
                            PayPalItem(name="Product 1", price=19.99, quantity=2)
                        ],
                        "currency": PayPalCurrency.USD,
                        "notes": "Thank you for your business!",
                        "due_date": datetime.now() + timedelta(days=10),
                    }
                ),
                txn_id,
            )
        )
        print(f"Invoice created! ID: {invoice.invoice_id}")

        # Create order from invoice
        order = await txn.add(
            lambda txn_id: paypal.Order.create_from_invoice(invoice, txn_id)
        )
        print(f"Order created! ID: {order['order_id']}")

        print("\nPayment approval required!")
        print("Please visit this URL to approve the payment:")
        print(order["approval_url"])
        print("\nWaiting for payment approval...")

        await asyncio.sleep(60)
        print("Trying to capture payment ...")
        # Capture payment
        payment = await paypal.Order.capture(order["order_id"], invoice.invoice_id)
        print(f"Payment captured! ID: {payment.payment_id}")
        print(f"Payment successful! ID: {payment.payment_id}")


async def run_server():
    print("running server...")
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000))
    await server.serve()


async def db_init():
    print("Initializing db...")
    await db_integration.initialize()


async def main4():
    # Ensure DB is initialized before anything else
    await db_init()

    # Then start server and payment flow concurrently
    await asyncio.gather(run_server(), run_payment_flow())


if __name__ == "__main__":
    asyncio.run(run_paypal())
