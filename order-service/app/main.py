from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import LoggingMiddleware
from app.api.health import router as health_router
from app.core.logger import logger
from app.core.redis_conn import redis_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting_orders_service")

    await redis_manager.connect()

    yield

    await redis_manager.close()
    logger.info("stopping_orders_service")


app = FastAPI(
    title="Order Service API",
    lifespan=lifespan
)

app.add_middleware(LoggingMiddleware)

app.include_router(health_router, prefix="/api/v1")
