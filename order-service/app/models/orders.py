import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Enum, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StatusEnum(enum.StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class OrdersOrm(Base):
    __tablename__ = 'orders'
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_id_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[StatusEnum] = mapped_column(Enum(StatusEnum, native_enum=True), default=StatusEnum.PENDING)
    items: Mapped[dict[str, Any]] = mapped_column(JSONB)
    total_amount: Mapped[Decimal]
    saga_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now(), server_default=func.now())
    idempotency_key: Mapped[uuid.UUID]
