import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.users import User


class RefreshTokenAdd(BaseModel):
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefreshToken(RefreshTokenAdd):
    id: uuid.UUID
    revoked: bool
    created_at: datetime
    user: User | None = None

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenUpdate(BaseModel):
    revoked: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
