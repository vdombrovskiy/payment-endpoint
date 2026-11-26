
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from app.services.cart_total import CartTotal
from app.services.payment import PaymentService
from app.services.payment_provider import PaymentProviderResult


def scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def create_payment_service(
    *,
    provider_result,
    existing_payment=None,
):
    user_id = uuid.uuid4()
    cart_id = uuid.uuid4()
    payment_method_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()

    cart = SimpleNamespace(
        id=cart_id,
        status="active",
    )

    payment_method = SimpleNamespace(
        id=payment_method_id,
        provider_token="tok_test_alice_visa",
    )

    session = MagicMock()

    if existing_payment is not None:
        session.execute.side_effect = [
            scalar_result(existing_payment),
        ]
    else:
        payment = SimpleNamespace(
            id=uuid.uuid4(),
            status="pending",
            amount=Decimal("70.00"),
            currency="USD",
            provider_transaction_id=None,
            failure_reason=None,
            idempotency_key=idempotency_key,
        )

        results = iter([
            scalar_result(None),
            scalar_result(cart),
            scalar_result(None),
            scalar_result(None),
            scalar_result(payment_method),
        ])

        def execute(statement):
            try:
                return next(results)
            except StopIteration:
                return scalar_result(session._added_payment)

        session.execute.side_effect = execute

        session.add.side_effect = lambda added_payment: setattr(
            session,
            "_added_payment",
            added_payment,
        )

    provider = MagicMock()
    provider.charge.return_value = provider_result

    total_calculator = MagicMock()
    total_calculator.calculate.return_value = CartTotal(
        amount=Decimal("70.00"),
        currency="USD",
    )

    service = PaymentService(
        provider=provider,
        total_calculator=total_calculator,
        session=session,
    )

    request = {
        "user_id": user_id,
        "cart_id": cart_id,
        "payment_method_id": payment_method_id,
        "idempotency_key": idempotency_key,
    }

    return service, session, provider, cart, request


def test_process_payment_success():
    service, session, provider, cart, request = create_payment_service(
        provider_result=PaymentProviderResult(
            success=True,
            transaction_id="mock_txn_123",
        )
    )

    payment = service.process_payment(**request)

    assert payment.status == "succeeded"
    assert payment.amount == Decimal("70.00")
    assert payment.currency == "USD"
    assert payment.provider_transaction_id == "mock_txn_123"
    assert payment.failure_reason is None

    assert cart.status == "checked_out"
    provider.charge.assert_called_once()
    assert session.commit.call_count == 2


def test_process_payment_declined():
    service, session, provider, cart, request = create_payment_service(
        provider_result=PaymentProviderResult(
            success=False,
            failure_reason="Payment declined",
        )
    )

    payment = service.process_payment(**request)

    assert payment.status == "failed"
    assert payment.failure_reason == "Payment declined"
    assert payment.provider_transaction_id is None

    assert cart.status == "active"

    provider.charge.assert_called_once()
    assert session.commit.call_count == 2


def test_idempotent_request_returns_existing_payment():
    user_id = uuid.uuid4()
    cart_id = uuid.uuid4()
    payment_method_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()

    existing_payment = SimpleNamespace(
        cart_id=cart_id,
        payment_method_id=payment_method_id,
        status="succeeded",
    )

    service, session, provider, _, _ = create_payment_service(
        provider_result=None,
        existing_payment=existing_payment,
    )

    result = service.process_payment(
        user_id=user_id,
        cart_id=cart_id,
        payment_method_id=payment_method_id,
        idempotency_key=idempotency_key,
    )

    assert result is existing_payment

    provider.charge.assert_not_called()

    session.add.assert_not_called()
    session.commit.assert_not_called()
