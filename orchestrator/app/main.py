import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.consumer.dlq_reader import DLQReader
from app.consumer.order_events import OrderEventsConsumer
from app.core.kafka_conn import kafka_manager
from app.core.logger import logger
from app.saga.retry import SagaRetryWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting orchestrators service")

    await kafka_manager.setup()

    stop_event = asyncio.Event()
    consumer_order_task = asyncio.create_task(
        OrderEventsConsumer(kafka_manager.order_consumer).consume(stop_event)
    )
    consumer_dlq_task = asyncio.create_task(DLQReader(kafka_manager.dlq_consumer).consume(stop_event))
    retry_task = asyncio.create_task(SagaRetryWorker().start(stop_event))

    yield

    logger.info("Shutting down orchestrator service")
    stop_event.set()

    try:
        await asyncio.wait_for(consumer_order_task, timeout=10.0)
        await asyncio.wait_for(consumer_dlq_task, timeout=10.0)
        await asyncio.wait_for(retry_task, timeout=10.0)
        logger.info("Consumer task finished cleanly")
    except TimeoutError:
        logger.error("Consumer task timed out during shutdown")
        consumer_order_task.cancel()
        consumer_dlq_task.cancel()
        retry_task.cancel()
        try:
            await consumer_order_task
            await consumer_dlq_task
            await retry_task
        except asyncio.CancelledError:
            logger.info("Consumer task cancelled")
    except Exception as ex:
        logger.error("Error during consumer shutdown", error=ex)
    finally:
        await kafka_manager.stop()
        logger.info("Stopping orchestrator service")


app = FastAPI(
    title="Orchestrator",
    lifespan=lifespan
)

app.include_router(health_router, prefix="/api/v1")
