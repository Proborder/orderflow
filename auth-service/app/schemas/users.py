import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.users import RoleEnum


class UserRequestAdd(BaseModel):
    email: EmailStr
    password: str


class UserAdd(BaseModel):
    email: EmailStr
    hashed_password: str


class User(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: RoleEnum

    model_config = ConfigDict(from_attributes=True)


class UserWithHashedPassword(User):
    hashed_password: str
