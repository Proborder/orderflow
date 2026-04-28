import sys
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.consumer.order_events import OrderEventConsumer

sys.path.append(str(Path(__file__).parent.parent))

from app.api.health import router as health_router
from app.api.middleware import LoggingMiddleware
from app.api.orders import router as orders_router
from app.core.kafka_conn import kafka_manager
from app.core.logger import logger
from app.core.redis_conn import redis_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting orders service")

    await kafka_manager.setup()
    await redis_manager.connect()

    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(OrderEventConsumer(kafka_manager.consumer).consume(stop_event))

    yield

    logger.info("Shutting down order service")
    stop_event.set()

    try:
        await asyncio.wait_for(consumer_task, timeout=10.0)
        logger.info("Consumer task finished cleanly")
    except TimeoutError:
        logger.error("Consumer task timed out during shutdown")
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
    except Exception as ex:
        logger.error("Error during consumer shutdown", error=ex)
    finally:
        await kafka_manager.stop()
        await redis_manager.close()
        logger.info("Stopping orders service")


app = FastAPI(
    title="Order Service API",
    lifespan=lifespan
)

app.add_middleware(LoggingMiddleware)

app.include_router(health_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
