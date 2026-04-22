import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.refresh_tokens import RefreshTokensOrm


class RoleEnum(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"


class UsersOrm(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, native_enum=True), default=RoleEnum.USER)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    refresh_tokens: Mapped[list["RefreshTokensOrm"]] = relationship(
        back_populates="user",
    )
