from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette import status

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.exceptions import (
    DatabaseNotUnavailableHTTPException,
    NoAccessTokenHTTPException,
    UserIsNotFoundException,
    UserIsNotFoundHTTPException,
)
from app.core.logger import logger
from app.schemas.users import User
from app.services.db_manager import DBManager


async def get_db():
    async with DBManager(session_factory=async_session_maker) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]


async def get_current_user(request: Request, db: DBDep):
    token = request.cookies.get("access_token")

    if not token:
        raise NoAccessTokenHTTPException

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise UserIsNotFoundException
    except jwt.exceptions.DecodeError as ex:
        raise NoAccessTokenHTTPException from ex

    try:
        user = await db.users.get_one_or_none(id=user_id)
    except (SQLAlchemyError, OSError) as ex:
        logger.error("Database connection error during fetch", error=ex)
        raise DatabaseNotUnavailableHTTPException from ex

    if user is None:
        raise UserIsNotFoundHTTPException

    return user


UserDep = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: UserDep):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас недостаточно прав для выполнения этого действия"
        )
    return current_user


AdminDep = Annotated[User, Depends(require_admin)]
