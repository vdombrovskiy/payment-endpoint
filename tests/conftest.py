import pytest
from decimal import Decimal
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from app.models import (
    Cart,
    CartItem,
    Product,
    User,
    UserPaymentMethod,
)


@pytest.fixture
def app():
    from app.config import Settings

    database_url = Settings().test_database_url

    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured before running integration tests"
        )

    database_name = make_url(database_url).database

    if not database_name or not database_name.endswith("_test"):
        raise RuntimeError(
            "Integration tests must use a dedicated database ending in '_test'"
        )

    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_url,
        }
    )

    with application.app_context():
        db.drop_all()
        db.create_all()

        yield application

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_checkout(app):
    user = User(
        email="alice@example.com",
        name="Alice",
    )

    product = Product(
        name="Blue Kettle",
        price=Decimal("45.00"),
        currency="USD",
        stock_quantity=10,
    )

    second_product = Product(
        name="Ceramic Mug",
        price=Decimal("12.50"),
        currency="USD",
        stock_quantity=10,
    )

    db.session.add_all([user, product, second_product])
    db.session.flush()

    cart = Cart(
        user_id=user.id,
        status="active",
    )

    payment_method = UserPaymentMethod(
        user_id=user.id,
        provider_token="tok_test_alice_visa",
        last_four="4242",
        is_default=True,
    )

    db.session.add_all([cart, payment_method])
    db.session.flush()

    db.session.add_all(
        [
            CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=1,
                unit_price=Decimal("45.00"),
            ),
            CartItem(
                cart_id=cart.id,
                product_id=second_product.id,
                quantity=2,
                unit_price=Decimal("12.50"),
            ),
        ]
    )

    db.session.commit()

    return {
        "user": user,
        "cart": cart,
        "payment_method": payment_method,
    }
