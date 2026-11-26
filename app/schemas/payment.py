from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    user_id: uuid.UUID
    cart_id: uuid.UUID
    payment_method_id: uuid.UUID
    idempotency_key: uuid.UUID


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    cart_id: uuid.UUID
    payment_method_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    currency: str
    status: str
    provider_transaction_id: str | None
    failure_reason: str | None
    created_at: datetime
