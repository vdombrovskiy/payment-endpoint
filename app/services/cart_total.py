
from decimal import Decimal
from typing import Protocol
import uuid

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.cart_item import CartItem
from app.models.product import Product


class EmptyCartError(Exception):
    """Raised when attempting to calculate the total of an empty cart."""


class MixedCurrencyError(Exception):
    """Raised when a cart contains products with different currencies."""


class CartTotal(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str


class CartTotalCalculator(Protocol):
    def calculate(self, cart_id: uuid.UUID) -> CartTotal:
        ...


class DatabaseCartTotalCalculator:
    def __init__(self, session: Session | None = None):
        self._session = session if session is not None else db.session

    def calculate(self, cart_id: uuid.UUID) -> CartTotal:
        statement = (
            select(
                CartItem.unit_price,
                CartItem.quantity,
                Product.currency,
            )
            .join(Product, CartItem.product_id == Product.id)
            .where(CartItem.cart_id == cart_id)
        )

        rows = self._session.execute(statement).all()

        if not rows:
            raise EmptyCartError("Cannot calculate the total of an empty cart")

        currencies = {row.currency for row in rows}

        if len(currencies) != 1:
            raise MixedCurrencyError(
                "All items in a cart must use the same currency"
            )

        amount = sum(
            (
                row.unit_price * row.quantity
                for row in rows
            ),
            start=Decimal("0.00"),
        )

        return CartTotal(
            amount=amount,
            currency=currencies.pop(),
        )
