import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import StateEnum


class CreateSagaState(BaseModel):
    saga_id: uuid.UUID
    order_id: uuid.UUID
    payload: dict[str, Any]


class UpdateSagaState(BaseModel):
    state: StateEnum


class SagaState(BaseModel):
    saga_id: uuid.UUID
    order_id: uuid.UUID
    state: StateEnum
    payload: dict[str, Any]
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
