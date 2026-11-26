from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.cart_total import EmptyCartError, MixedCurrencyError
from app.services.payment import (
    CartNotActiveError,
    CartNotFoundError,
    IdempotencyConflictError,
    InvalidCartTotalError,
    PaymentAlreadyExistsError,
    PaymentMethodNotFoundError,
    PaymentService,
)
from app.services.cart_total import DatabaseCartTotalCalculator
from app.services.payment_provider import MockPaymentProvider


payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def build_payment_service() -> PaymentService:
    return PaymentService(
        provider=MockPaymentProvider(),
        total_calculator=DatabaseCartTotalCalculator(),
    )


@payments_bp.post("")
def create_payment():
    try:
        payload = PaymentCreate.model_validate(request.get_json(silent=True))

        payment_service = build_payment_service()

        payment = payment_service.process_payment(
            user_id=payload.user_id,
            cart_id=payload.cart_id,
            payment_method_id=payload.payment_method_id,
            idempotency_key=payload.idempotency_key,
        )

        response = PaymentResponse.model_validate(payment)

        return jsonify(response.model_dump(mode="json")), 201

    except ValidationError as exc:
        return jsonify({
            "error": "Invalid request",
            "details": [error["msg"] for error in exc.errors()],
        }), 400

    except (CartNotFoundError, PaymentMethodNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 404

    except (
        CartNotActiveError,
        PaymentAlreadyExistsError,
        IdempotencyConflictError,
    ) as exc:
        return jsonify({"error": str(exc)}), 409

    except (
        EmptyCartError,
        MixedCurrencyError,
        InvalidCartTotalError,
    ) as exc:
        return jsonify({"error": str(exc)}), 400
