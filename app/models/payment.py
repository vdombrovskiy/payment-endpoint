
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Payment(db.Model):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_payments_amount_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_payments_status",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_payments_user_idempotency_key",
        ),
        Index("idx_payments_user_id", "user_id"),
        Index("idx_payments_cart_id", "cart_id"),
        Index(
            "uq_payments_active_cart",
            "cart_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'succeeded')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carts.id"),
        nullable=False,
    )

    payment_method_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_payment_methods.id"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="pending",
    )

    provider_transaction_id: Mapped[str | None] = mapped_column(Text)

    failure_reason: Mapped[str | None] = mapped_column(Text)

    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="payments")
    cart: Mapped["Cart"] = relationship(back_populates="payments")
    payment_method: Mapped["UserPaymentMethod"] = relationship(
        back_populates="payments"
    )
