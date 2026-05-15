import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class BaseEventMessage(BaseModel):
    event_id: uuid.UUID
    event_type: str
    saga_id: uuid.UUID


class OrderCreatedEvent(BaseEventMessage):
    order_id: uuid.UUID
    user_id: uuid.UUID
    items: dict[str, Any]
    total_amount: Decimal
    timestamp: datetime


class InventoryEvent(BaseEventMessage):
    order_id: uuid.UUID
    payload: dict[str, Any]
    message_id: uuid.UUID
    timestamp: datetime


class PaymentEvent(BaseEventMessage):
    order_id: uuid.UUID
    payload: Decimal
    message_id: uuid.UUID
    timestamp: datetime
