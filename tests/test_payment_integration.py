from sqlalchemy import select

from app.extensions import db
from app.models import Cart, Payment

from unittest.mock import patch

from app.services.payment_provider import PaymentProviderResult


def make_payment_request(sample_checkout, idempotency_key):
    return {
        "user_id": str(sample_checkout["user"].id),
        "cart_id": str(sample_checkout["cart"].id),
        "payment_method_id": str(sample_checkout["payment_method"].id),
        "idempotency_key": str(idempotency_key),
    }


def test_successful_payment_creates_payment_and_checks_out_cart(
    client,
    sample_checkout,
):
    import uuid

    payload = make_payment_request(
        sample_checkout,
        uuid.uuid4(),
    )

    response = client.post("/api/payments", json=payload)

    assert response.status_code == 201

    response_data = response.get_json()

    assert response_data["status"] == "succeeded"
    assert response_data["amount"] == "70.00"
    assert response_data["currency"] == "USD"
    assert response_data["provider_transaction_id"].startswith("mock_txn_")

    payment = db.session.execute(
        select(Payment).where(Payment.id == response_data["id"])
    ).scalar_one()

    cart = db.session.get(Cart, sample_checkout["cart"].id)

    assert payment.status == "succeeded"
    assert cart.status == "checked_out"


def test_declined_payment_keeps_cart_active(
    client,
    sample_checkout,
):
    import uuid

    sample_checkout["payment_method"].provider_token = "tok_test_declined"
    db.session.commit()

    payload = make_payment_request(
        sample_checkout,
        uuid.uuid4(),
    )

    response = client.post("/api/payments", json=payload)

    assert response.status_code == 201

    response_data = response.get_json()

    assert response_data["status"] == "failed"
    assert response_data["failure_reason"] == (
        "Payment declined by mock provider"
    )

    cart = db.session.get(Cart, sample_checkout["cart"].id)

    assert cart.status == "active"


def test_repeated_request_does_not_create_another_payment(
    client,
    sample_checkout,
):
    import uuid

    payload = make_payment_request(
        sample_checkout,
        uuid.uuid4(),
    )

    first_response = client.post("/api/payments", json=payload)
    second_response = client.post("/api/payments", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_data = first_response.get_json()
    second_data = second_response.get_json()

    assert first_data["id"] == second_data["id"]

    payments = db.session.execute(
        select(Payment).where(
            Payment.cart_id == sample_checkout["cart"].id
        )
    ).scalars().all()

    assert len(payments) == 1


def test_provider_exception_keeps_payment_pending(
    client,
    sample_checkout,
):
    import uuid

    payload = make_payment_request(
        sample_checkout,
        uuid.uuid4(),
    )

    with patch(
        "app.api.payments.MockPaymentProvider.charge",
        side_effect=TimeoutError("Provider request timed out"),
    ):
        response = client.post("/api/payments", json=payload)

    assert response.status_code == 202

    response_data = response.get_json()

    assert response_data["status"] == "pending"
    assert response_data["provider_transaction_id"] is None

    payment = db.session.execute(
        select(Payment).where(
            Payment.id == response_data["id"]
        )
    ).scalar_one()

    cart = db.session.get(
        Cart,
        sample_checkout["cart"].id,
    )

    assert payment.status == "pending"
    assert cart.status == "active"

def test_retry_pending_payment_with_same_key(
    client,
    sample_checkout,
):
    import uuid

    payload = make_payment_request(
        sample_checkout,
        uuid.uuid4(),
    )

    with patch(
        "app.api.payments.MockPaymentProvider.charge",
        side_effect=[
            TimeoutError("Provider request timed out"),
            PaymentProviderResult(
                success=True,
                transaction_id="mock_txn_retry_success",
            ),
        ],
    ) as mock_charge:
        first_response = client.post("/api/payments", json=payload)

        assert first_response.status_code == 202
        assert first_response.get_json()["status"] == "pending"

        # Second request uses exactly the same idempotency key.
        second_response = client.post("/api/payments", json=payload)

    assert second_response.status_code == 201
    assert second_response.get_json()["status"] == "succeeded"

    assert mock_charge.call_count == 2

    first_call = mock_charge.call_args_list[0]
    second_call = mock_charge.call_args_list[1]

    assert (
        first_call.kwargs["idempotency_key"]
        == second_call.kwargs["idempotency_key"]
    )

    assert first_call.kwargs["amount"] == second_call.kwargs["amount"]
