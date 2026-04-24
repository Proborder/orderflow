from typing import Annotated

import jwt
from aiokafka import AIOKafkaProducer
from fastapi import Depends, Request

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.exceptions import (
    NoAccessTokenHTTPException,
    InvalidAccessTokenHTTPException,
    TokenExpiredHTTPException,
)
from app.core.kafka_conn import kafka_manager
from app.core.logger import logger
from app.schemas.tokens import TokenData
from app.services.db_manager import DBManager


async def verify_jwt_token(request: Request):
    token = request.cookies.get("access_token")

    if not token:
        raise NoAccessTokenHTTPException

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenData(
            user_id=payload.get("sub"),
            role=payload.get("role"),
            expire=payload.get("exp"),
        )
    except jwt.exceptions.DecodeError as ex:
        raise InvalidAccessTokenHTTPException from ex
    except jwt.exceptions.ExpiredSignatureError as ex:
        raise TokenExpiredHTTPException from ex


TokenDep = Annotated[TokenData, Depends(verify_jwt_token)]


def get_kafka_producer() -> AIOKafkaProducer:
    if kafka_manager.producer is None:
        logger.warning("Kafka producer not initialized")
    return kafka_manager.producer


ProducerDep = Annotated[AIOKafkaProducer, Depends(get_kafka_producer)]


async def get_db(token_data: TokenDep):
    async with DBManager(
        session_factory=async_session_maker,
        user_id=token_data.user_id,
        role=token_data.role
    ) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]
