from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.exceptions import (
    DatabaseNotUnavailableHTTPException,
    NoAccessTokenHTTPException,
    TokenExpiredHTTPException,
    UserIsNotFoundException,
    UserIsNotFoundHTTPException,
)
from app.core.logger import logger
from app.schemas.users import User
from app.services.db_manager import DBManager


bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[DBManager]:
    async with DBManager(session_factory=async_session_maker) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DBDep,
) -> User:
    if not credentials:
        raise NoAccessTokenHTTPException

    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise UserIsNotFoundException
    except jwt.exceptions.DecodeError as ex:
        raise NoAccessTokenHTTPException from ex
    except jwt.exceptions.ExpiredSignatureError as ex:
        raise TokenExpiredHTTPException from ex

    try:
        user = await db.users.get_one_or_none(id=user_id)
    except (SQLAlchemyError, OSError) as ex:
        logger.error("Database connection error during fetch", error=ex)
        raise DatabaseNotUnavailableHTTPException from ex

    if user is None:
        raise UserIsNotFoundHTTPException

    return user


UserDep = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: UserDep) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас недостаточно прав для выполнения этого действия"
        )
    return current_user


AdminDep = Annotated[User, Depends(require_admin)]
