import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StateEnum(enum.StrEnum):
    CREATED = "CREATED"
    INVENTORY_RESERVING = "INVENTORY_RESERVING"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    PAYMENT_CHARGING = "PAYMENT_CHARGING"
    COMPLETED = "COMPLETED"
    COMPENSATING_INVENTORY = "COMPENSATING_INVENTORY"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class SagaStateOrm(Base):
    __tablename__ = 'saga_state'

    saga_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID]
    state: Mapped[StateEnum] = mapped_column(Enum(StateEnum, native_enum=True), default=StateEnum.CREATED)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(default=0)
    retry_after: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now(), server_default=func.now())


class ProcessedEventsOrm(Base):
    __tablename__ = 'processed_events'

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    saga_id: Mapped[uuid.UUID]
    event_type: Mapped[str]
    processed_at: Mapped[datetime] = mapped_column(server_default=func.now())
