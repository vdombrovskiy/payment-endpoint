import uuid
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict


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
    def charge(
        self,
        *,
        provider_token: str,
        amount: Decimal,
        currency: str,
        idempotency_key: uuid.UUID,
    ) -> PaymentProviderResult:
        if provider_token == "tok_test_declined":
            return PaymentProviderResult(
                success=False,
                failure_reason="Payment declined by mock provider",
            )

        return PaymentProviderResult(
            success=True,
            transaction_id=f"mock_txn_{uuid.uuid4().hex}",
        )
