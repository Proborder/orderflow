from aiokafka import AIOKafkaClient
from fastapi import APIRouter
from sqlalchemy import text
from starlette import status
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.core.redis_conn import redis_manager

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def ping() -> dict[str, str]:
    logger.info("Healthcheck called")
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    logger.info("Readiness check called")

    checks = {"postgresql": "ok", "kafka": "ok", "redis": "ok"}
    status_code = status.HTTP_200_OK

    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
    except Exception as ex:
        logger.warning("Readiness check failed: PostgreSQL is unavailable", error=ex)
        checks["postgresql"] = "Unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    client = AIOKafkaClient(bootstrap_servers=settings.KAFKA_BOOTSTRAP_URL)
    try:
        await client.bootstrap()
    except Exception as ex:
        logger.warning("Readiness check failed: Kafka is unavailable", error=ex)
        checks["kafka"] = "Unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    finally:
        await client.close()

    try:
        await redis_manager.ping()
    except Exception as ex:
        logger.warning("Readiness check failed: Redis is unavailable", error=ex)
        checks["redis"] = "Unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=status_code, content=checks)
