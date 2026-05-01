import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.consumer.order_events import OrderEventsConsumer
from app.core.kafka_conn import kafka_manager
from app.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting orchestrators service")

    await kafka_manager.setup()

    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(OrderEventsConsumer(kafka_manager.consumer).consume(stop_event))

    yield

    logger.info("Shutting down orchestrator service")
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
        logger.info("Stopping orchestrator service")


app = FastAPI(
    title="Orchestrator",
    lifespan=lifespan
)
