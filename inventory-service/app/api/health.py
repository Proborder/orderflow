from aiokafka import AIOKafkaClient
from fastapi import APIRouter
from starlette import status
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    logger.info("Inventory live check called")
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    logger.info("Inventory readiness check called")

    checks = {"kafka": "ok"}
    status_code = status.HTTP_200_OK

    client = AIOKafkaClient(bootstrap_servers=settings.kafka_bootstrap_url)
    try:
        await client.bootstrap()
    except Exception as ex:
        logger.warning("Inventory readiness check failed: Kafka is unavailable", error=ex)
        checks["kafka"] = "Unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    finally:
        await client.close()

    return JSONResponse(status_code=status_code, content=checks)
