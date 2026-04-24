import uuid
from datetime import datetime

from pydantic import BaseModel


class TokenData(BaseModel):
    user_id: uuid.UUID
    role: str
    expire: datetime
