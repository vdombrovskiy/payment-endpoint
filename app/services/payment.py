
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


class PaymentOutcomeUnknownError(PaymentError):
    """Raised when the provider's payment outcome cannot be determined."""

    def __init__(self, payment: Payment):
        self.payment = payment
        super().__init__(
            "Payment outcome is unknown. The payment is still pending."
        )


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
            self._validate_idempotency_request(
                payment=existing_payment,
                cart_id=cart_id,
                payment_method_id=payment_method_id,
            )

            if existing_payment.status != "pending":
                return existing_payment

            cart = self._session.get(Cart, existing_payment.cart_id)

            payment_method = self._get_payment_method(
                user_id=user_id,
                payment_method_id=existing_payment.payment_method_id,
            )

            return self._charge_payment(
                payment=existing_payment,
                cart=cart,
                payment_method=payment_method,
            )

        cart = self._get_active_cart(
            user_id=user_id,
            cart_id=cart_id,
        )

        existing_payment = self._get_payment_by_idempotency_key(
            user_id=user_id,
            idempotency_key=idempotency_key,
        )

        if existing_payment is not None:
            self._validate_idempotency_request(
                payment=existing_payment,
                cart_id=cart_id,
                payment_method_id=payment_method_id,
            )

            if existing_payment.status != "pending":
                return existing_payment

            payment_method = self._get_payment_method(
                user_id=user_id,
                payment_method_id=existing_payment.payment_method_id,
            )

            return self._charge_payment(
                payment=existing_payment,
                cart=cart,
                payment_method=payment_method,
            )

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

        # Persist pending payment before contacting the provider.
        self._session.add(payment)
        self._session.commit()
        self._session.refresh(payment)

        return self._charge_payment(
            payment=payment,
            cart=cart,
            payment_method=payment_method,
        )

    def _charge_payment(
        self,
        *,
        payment: Payment,
        cart: Cart,
        payment_method: UserPaymentMethod,
    ) -> Payment:
        payment = self._session.execute(
            select(Payment)
            .where(Payment.id == payment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()

        if payment.status != "pending":
            return payment

        try:
            result = self._provider.charge(
                provider_token=payment_method.provider_token,
                amount=payment.amount,
                currency=payment.currency,
                idempotency_key=payment.idempotency_key,
            )
        except Exception as exc:
            payment_id = payment.id
            self._session.rollback()

            payment = self._session.get(Payment, payment_id)

            raise PaymentOutcomeUnknownError(payment) from exc

        if result.success:
            payment.status = "succeeded"
            payment.provider_transaction_id = result.transaction_id
            payment.failure_reason = None
            cart.status = "checked_out"
        else:
            payment.status = "failed"
            payment.failure_reason = result.failure_reason

        self._session.commit()
        self._session.refresh(payment)

        return payment

    def _validate_idempotency_request(
        self,
        *,
        payment: Payment,
        cart_id: uuid.UUID,
        payment_method_id: uuid.UUID,
    ) -> None:
        if (
            payment.cart_id != cart_id
            or payment.payment_method_id != payment_method_id
        ):
            raise IdempotencyConflictError(
                "Idempotency key was already used for a different request"
            )

    def _get_payment_by_idempotency_key(
        self,
        *,
        user_id: uuid.UUID,
        idempotency_key: uuid.UUID,
        for_update: bool = False,
    ) -> Payment | None:
        statement = select(Payment).where(
            Payment.user_id == user_id,
            Payment.idempotency_key == idempotency_key,
        )

        if for_update:
            statement = statement.with_for_update()

        statement = statement.execution_options(populate_existing=True)

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
