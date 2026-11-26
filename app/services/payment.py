
from decimal import Decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.cart import Cart
from app.models.payment import Payment
from app.models.user_payment_method import UserPaymentMethod
from app.services.cart_total import (
    CartTotalCalculator,
    EmptyCartError,
    MixedCurrencyError,
)
from app.services.payment_provider import PaymentProvider


class PaymentError(Exception):
    """Base exception for payment-related errors."""


class CartNotFoundError(PaymentError):
    """Raised when the cart does not exist or belong to the user."""


class CartNotActiveError(PaymentError):
    """Raised when the cart is not active."""


class PaymentMethodNotFoundError(PaymentError):
    """Raised when the payment method does not belong to the user."""


class PaymentAlreadyExistsError(PaymentError):
    """Raised when the cart already has a pending or successful payment."""


class IdempotencyConflictError(PaymentError):
    """Raised when an idempotency key is reused for a different request."""


class InvalidCartTotalError(PaymentError):
    """Raised when the calculated cart total cannot be charged."""


class PaymentService:
    def __init__(
        self,
        *,
        provider: PaymentProvider,
        total_calculator: CartTotalCalculator,
        session: Session | None = None,
    ):
        self._provider = provider
        self._total_calculator = total_calculator
        self._session = session if session is not None else db.session

    def process_payment(
        self,
        *,
        user_id: uuid.UUID,
        cart_id: uuid.UUID,
        payment_method_id: uuid.UUID,
        idempotency_key: uuid.UUID,
    ) -> Payment:
        existing_payment = self._get_payment_by_idempotency_key(
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

        if existing_payment is not None:
            if (
                existing_payment.cart_id != cart_id
                or existing_payment.payment_method_id != payment_method_id
            ):
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different request"
                )

            return existing_payment

        cart = self._get_active_cart(
            user_id=user_id,
            cart_id=cart_id,
        )

        existing_payment = self._get_payment_by_idempotency_key(
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

        if existing_payment is not None:
            if (
                existing_payment.cart_id != cart_id
                or existing_payment.payment_method_id != payment_method_id
            ):
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different request"
                )

            return existing_payment

        self._ensure_cart_can_be_paid(cart_id=cart.id)

        payment_method = self._get_payment_method(
            user_id=user_id,
            payment_method_id=payment_method_id,
        )

        total = self._total_calculator.calculate(cart.id)

        if total.amount <= Decimal("0.00"):
            raise InvalidCartTotalError(
                "Cart total must be greater than zero"
            )

        payment = Payment(
            user_id=user_id,
            cart_id=cart.id,
            payment_method_id=payment_method.id,
            amount=total.amount,
            currency=total.currency,
            status="pending",
            idempotency_key=idempotency_key,
        )

        self._session.add(payment)
        self._session.commit()
        self._session.refresh(payment)

        result = self._provider.charge(
            provider_token=payment_method.provider_token,
            amount=total.amount,
            currency=total.currency,
            idempotency_key=idempotency_key,
        )

        if result.success:
            payment.status = "succeeded"
            payment.provider_transaction_id = result.transaction_id
            cart.status = "checked_out"
        else:
            payment.status = "failed"
            payment.failure_reason = result.failure_reason

        self._session.commit()
        self._session.refresh(payment)

        return payment

    def _get_payment_by_idempotency_key(
        self,
        *,
        user_id: uuid.UUID,
        idempotency_key: uuid.UUID,
    ) -> Payment | None:
        statement = select(Payment).where(
            Payment.user_id == user_id,
            Payment.idempotency_key == idempotency_key,
        )

        return self._session.execute(statement).scalar_one_or_none()

    def _get_active_cart(
        self,
        *,
        user_id: uuid.UUID,
        cart_id: uuid.UUID,
    ) -> Cart:
        statement = (
            select(Cart)
            .where(
                Cart.id == cart_id,
                Cart.user_id == user_id,
            )
            .with_for_update()
        )

        cart = self._session.execute(statement).scalar_one_or_none()

        if cart is None:
            raise CartNotFoundError(
                "Cart does not exist or does not belong to the user"
            )

        if cart.status != "active":
            raise CartNotActiveError("Cart is not active")

        return cart

    def _ensure_cart_can_be_paid(self, *, cart_id: uuid.UUID) -> None:
        statement = select(Payment).where(
            Payment.cart_id == cart_id,
            Payment.status.in_(["pending", "succeeded"]),
        )

        existing_payment = self._session.execute(
            statement
        ).scalar_one_or_none()

        if existing_payment is not None:
            raise PaymentAlreadyExistsError(
                "Cart already has a pending or successful payment"
            )

    def _get_payment_method(
        self,
        *,
        user_id: uuid.UUID,
        payment_method_id: uuid.UUID,
    ) -> UserPaymentMethod:
        statement = select(UserPaymentMethod).where(
            UserPaymentMethod.id == payment_method_id,
            UserPaymentMethod.user_id == user_id,
        )

        payment_method = self._session.execute(
            statement
        ).scalar_one_or_none()

        if payment_method is None:
            raise PaymentMethodNotFoundError(
                "Payment method does not exist or does not belong to the user"
            )

        return payment_method
