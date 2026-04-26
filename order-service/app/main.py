import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

sys.path.append(str(Path(__file__).parent.parent))

from app.api.health import router as health_router
from app.api.middleware import LoggingMiddleware
from app.api.orders import router as orders_router
from app.core.kafka_conn import kafka_manager
from app.core.logger import logger
from app.core.redis_conn import redis_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_orders_service")

    await redis_manager.connect()
    await kafka_manager.setup()

    yield

    await redis_manager.close()
    await kafka_manager.stop()

    logger.info("stopping_orders_service")


app = FastAPI(
    title="Order Service API",
    lifespan=lifespan
)

app.add_middleware(LoggingMiddleware)

app.include_router(health_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
