from typing import Callable, Awaitable, Any
from contextlib import asynccontextmanager
from uuid import uuid4


class PaymentTransaction:
    """
    A lightweight transaction manager for wrapping async payment operations.
    Allows you to register async operations via `add()` and get their result immediately.
    """

    def __init__(self, transaction_id: str):
        self._operations = []
        self.transaction_id = transaction_id

    async def __aenter__(self):
        print(f"[PaymentTransaction] Started with ID: {self.transaction_id}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(
                f"[PaymentTransaction {self.transaction_id}] Exception: {exc_val}"
            )
            return False  # re-raise exception
        print(
            f"[PaymentTransaction {self.transaction_id}] Completed successfully."
        )
        return True

    async def add(self, operation: Callable[[str], Awaitable[Any]]) -> Any:
        """
        Add an async operation to the transaction and return its result immediately.

        Args:
            operation: A callable that takes transaction_id and returns an awaitable.

        Returns:
            Result of the awaited operation.
        """
        try:
            result = await operation(self.transaction_id)
            self._operations.append(operation)
            return result
        except Exception as e:
            print(
                f"[PaymentTransaction {self.transaction_id}] Operation failed: {e}"
            )
            raise


@asynccontextmanager
async def payment_transaction():
    """
    Async context manager to wrap PaymentTransaction usage.
    """
    transaction_id = str(uuid4())  # generate random transaction ID
    txn = PaymentTransaction(transaction_id)
    try:
        await txn.__aenter__()
        yield txn
    except Exception as e:
        await txn.__aexit__(type(e), e, e.__traceback__)
        raise
    else:
        await txn.__aexit__(None, None, None)
