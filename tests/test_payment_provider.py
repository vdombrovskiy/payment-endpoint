
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError

from app.services.payment_provider import (
    MockPaymentProvider,
    PaymentProviderResult,
)


def test_mock_provider_successful_payment():
    provider = MockPaymentProvider()

    result = provider.charge(
        provider_token="tok_test_alice_visa",
        amount=Decimal("70.00"),
        currency="USD",
        idempotency_key=uuid.uuid4(),
    )

    assert result.success is True
    assert result.transaction_id.startswith("mock_txn_")
    assert result.failure_reason is None


def test_mock_provider_declined_payment():
    provider = MockPaymentProvider()

    result = provider.charge(
        provider_token="tok_test_declined",
        amount=Decimal("70.00"),
        currency="USD",
        idempotency_key=uuid.uuid4(),
    )

    assert result.success is False
    assert result.transaction_id is None
    assert result.failure_reason == "Payment declined by mock provider"


def test_payment_provider_result_is_immutable():
    result = PaymentProviderResult(
        success=True,
        transaction_id="txn_123",
    )

    with pytest.raises(ValidationError):
        result.success = False


def test_payment_provider_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PaymentProviderResult(
            success=True,
            transaction_id="txn_123",
            unexpected_field="value",
        )
