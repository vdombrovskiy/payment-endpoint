from decimal import Decimal
from unittest.mock import MagicMock
import uuid

import pytest

from app.services.cart_total import (
    CartTotal,
    DatabaseCartTotalCalculator,
    EmptyCartError,
    MixedCurrencyError,
)


def create_calculator(rows):
    session = MagicMock()
    session.execute.return_value.all.return_value = rows

    return DatabaseCartTotalCalculator(session=session)


def test_calculates_cart_total():
    calculator = create_calculator(
        [
            MagicMock(
                unit_price=Decimal("45.00"),
                quantity=1,
                currency="USD",
            ),
            MagicMock(
                unit_price=Decimal("12.50"),
                quantity=2,
                currency="USD",
            ),
        ]
    )

    result = calculator.calculate(uuid.uuid4())

    assert result == CartTotal(
        amount=Decimal("70.00"),
        currency="USD",
    )


def test_raises_error_for_empty_cart():
    calculator = create_calculator([])

    with pytest.raises(EmptyCartError):
        calculator.calculate(uuid.uuid4())


def test_raises_error_for_mixed_currencies():
    calculator = create_calculator(
        [
            MagicMock(
                unit_price=Decimal("45.00"),
                quantity=1,
                currency="USD",
            ),
            MagicMock(
                unit_price=Decimal("20.00"),
                quantity=1,
                currency="EUR",
            ),
        ]
    )

    with pytest.raises(MixedCurrencyError):
        calculator.calculate(uuid.uuid4())
