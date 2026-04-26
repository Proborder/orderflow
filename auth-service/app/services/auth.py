import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import (
    DatabaseNotUnavailableException,
    EmailOrPasswordIncorrectException,
    IncorrectTokenException,
    RefreshTokenExpiredException,
    UserAlreadyExistsException,
)
from app.core.logger import logger
from app.schemas.refresh_tokens import RefreshTokenAdd, RefreshTokenUpdate, TokenResponse
from app.schemas.users import User, UserAdd, UserRequestAdd
from app.services.base import BaseService


class AuthService(BaseService):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def create_access_token(self, data: dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode |= {"exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def register_user(self, data: UserRequestAdd) -> User:
        try:
            email_exists = await self.db.users.get_one_or_none(email=data.email)
            if email_exists:
                raise UserAlreadyExistsException

            hashed_password = self.hash_password(data.password)
            new_user_data = UserAdd(email=data.email, hashed_password=hashed_password)

            new_user = await self.db.users.add(new_user_data)
            await self.db.commit()
            return new_user

        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def login_user(self, data: UserRequestAdd) -> TokenResponse:
        try:
            user = await self.db.users.get_user_with_hashed_password(email=data.email)
            if not user or not self.verify_password(data.password, user.hashed_password):
                raise EmailOrPasswordIncorrectException

            access_token = self.create_access_token({"sub": str(user.id), "role": user.role})
            refresh_token = str(uuid.uuid4())

            new_refresh_token_data = RefreshTokenAdd(
                user_id=user.id,
                token_hash=self.hash_token(refresh_token),
                expires_at=(
                    datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                ).replace(tzinfo=None)
            )

            await self.db.refresh_tokens.add_without_user(new_refresh_token_data)
            await self.db.commit()

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token
            )

        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        try:
            if not refresh_token:
                raise RefreshTokenExpiredException

            token_hash = self.hash_token(refresh_token)
            token_data = await self.db.refresh_tokens.get_one_or_none(token_hash=token_hash)

            if not token_data:
                raise IncorrectTokenException

            if token_data.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
                raise RefreshTokenExpiredException

            if token_data.revoked:
                update_data = RefreshTokenUpdate(revoked=True)
                await self.db.refresh_tokens.edit(update_data, user_id=token_data.user_id)
                await self.db.commit()
                raise IncorrectTokenException

            update_data = RefreshTokenUpdate(revoked=True)
            await self.db.refresh_tokens.edit(update_data, exclude_unset=True, id=token_data.id)

            access_token = self.create_access_token({
                "sub": str(token_data.user_id),
                "role": token_data.user.role
            })
            refresh_token = str(uuid.uuid4())

            new_refresh_token_data = RefreshTokenAdd(
                user_id=token_data.user_id,
                token_hash=self.hash_token(refresh_token),
                expires_at=(
                    datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
                ).replace(tzinfo=None)
            )

            await self.db.refresh_tokens.add_without_user(new_refresh_token_data)
            await self.db.commit()

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token
            )

        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def logout(self, refresh_token: str) -> None:
        try:
            if not refresh_token:
                raise IncorrectTokenException

            token_hash = self.hash_token(refresh_token)
            token = await self.db.refresh_tokens.get_one_or_none(token_hash=token_hash)
            if not token:
                raise IncorrectTokenException

            update_data = RefreshTokenUpdate(revoked=True)
            await self.db.refresh_tokens.edit(update_data, exclude_unset=True, token_hash=token_hash)
            await self.db.commit()
        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex
