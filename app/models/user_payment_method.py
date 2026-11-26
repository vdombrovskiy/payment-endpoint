from datetime import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class UserPaymentMethod(db.Model):
    __tablename__ = "user_payment_methods"

    __table_args__ = (
        Index("idx_user_payment_methods_user_id", "user_id"),
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
    provider_token: Mapped[str] = mapped_column(String, nullable=False)
    last_four: Mapped[str | None] = mapped_column(CHAR(4))
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="payment_methods")
    payments: Mapped[list["Payment"]] = relationship(back_populates="payment_method")
