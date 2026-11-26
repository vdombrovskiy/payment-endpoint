from sqlalchemy import select

from app.extensions import db
from app.models import Cart, Payment


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
