import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class CommandMessage(BaseModel):
    command_type: str
    saga_id: uuid.UUID
    order_id: uuid.UUID
    payload: dict[str, Any] | Decimal
    message_id: uuid.UUID


class OrderEventMessage(BaseModel):
    event_id: uuid.UUID
    event_type: str
    saga_id: uuid.UUID
    order_id: uuid.UUID


class DlqEventMessage(BaseModel):
    event_type: str
    saga_id: uuid.UUID
    retry_count: int
    last_error: str
    failed_at: datetime
