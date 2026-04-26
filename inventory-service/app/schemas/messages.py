import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CommandMessage(BaseModel):
    command_type: str
    saga_id: uuid.UUID
    order_id: uuid.UUID
    payload: dict[str, Any]
    message_id: uuid.UUID


class EventMessage(BaseModel):
    event_type: str
    saga_id: uuid.UUID
    order_id: uuid.UUID
    payload: dict[str, Any]
    message_id: uuid.UUID
    timestamp: datetime
