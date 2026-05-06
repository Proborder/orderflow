import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateProcessedEvent(BaseModel):
    event_id: uuid.UUID
    saga_id: uuid.UUID
    event_type: str


class ProcessedEvent(CreateProcessedEvent):
    processed_at: datetime

    model_config = ConfigDict(from_attributes=True)
