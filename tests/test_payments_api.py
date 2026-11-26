from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app import create_app
from app.api import payments


def create_payment():
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        cart_id=uuid.uuid4(),
        payment_method_id=uuid.uuid4(),
        amount=Decimal("70.00"),
        currency="USD",
        status="succeeded",
        provider_transaction_id="mock_txn_123",
        failure_reason=None,
        created_at=datetime.now(timezone.utc),
    )


def test_create_payment_returns_201(monkeypatch):
    payment = create_payment()

    class FakePaymentService:
        def process_payment(self, **kwargs):
            assert kwargs["user_id"] is not None
            assert kwargs["cart_id"] is not None
            return payment

    monkeypatch.setattr(
        payments,
        "build_payment_service",
        lambda: FakePaymentService(),
    )

    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.post(
        "/api/payments",
        json={
            "user_id": str(payment.user_id),
            "cart_id": str(payment.cart_id),
            "payment_method_id": str(payment.payment_method_id),
            "idempotency_key": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["id"] == str(payment.id)
    assert data["amount"] == "70.00"
    assert data["currency"] == "USD"
    assert data["status"] == "succeeded"


def test_create_payment_rejects_invalid_request():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.post(
        "/api/payments",
        json={
            "cart_id": "not-a-valid-uuid",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request"


def test_create_payment_rejects_missing_json():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.post("/api/payments")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid request"
