import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.orders import StatusEnum


class OrderCreateRequest(BaseModel):
    idempotency_key: uuid.UUID
    items: dict[str, Any] = Field(..., min_length=1)


class OrderCreate(BaseModel):
    user_id: uuid.UUID
    items: dict[str, Any]
    total_amount: Decimal
    saga_id: uuid.UUID
    idempotency_key: uuid.UUID


class Order(OrderCreate):
    id: uuid.UUID
    status: StatusEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderUpdateStatus(BaseModel):
    status: StatusEnum
