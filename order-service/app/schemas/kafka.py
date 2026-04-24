import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class KafkaOrderEvent(BaseModel):
    event_id: uuid.UUID
    event_type: str
    saga_id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    items: dict[str, Any]
    total_amount: Decimal
    timestamp: datetime
