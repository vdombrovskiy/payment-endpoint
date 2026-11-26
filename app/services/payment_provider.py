import uuid
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from threading import Lock


class PaymentProviderResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    success: bool
    transaction_id: str | None = None
    failure_reason: str | None = None


class PaymentProvider(Protocol):
    def charge(
        self,
        *,
        provider_token: str,
        amount: Decimal,
        currency: str,
        idempotency_key: uuid.UUID,
    ) -> PaymentProviderResult:
        ...

class MockPaymentProvider:
    def __init__(self):
        self._results: dict[uuid.UUID, PaymentProviderResult] = {}
        self._lock = Lock()

    def charge(
        self,
        *,
        provider_token: str,
        amount: Decimal,
        currency: str,
        idempotency_key: uuid.UUID,
    ) -> PaymentProviderResult:

        with self._lock:
            existing_result = self._results.get(idempotency_key)

            if existing_result is not None:
                return existing_result

            if provider_token == "tok_test_declined":
                result = PaymentProviderResult(
                    success=False,
                    failure_reason="Payment declined by mock provider",
                )
            else:
                result = PaymentProviderResult(
                    success=True,
                    transaction_id=f"mock_txn_{uuid.uuid4().hex}",
                )

            self._results[idempotency_key] = result

            return result