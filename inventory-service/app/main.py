import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.logger import logger
from app.core.inventory_command import inventory_command_manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("starting_inventory_service")
    stop_event = asyncio.Event()

    consumer = await inventory_command_manager.start()
    consumer_task = asyncio.create_task(consumer.consume(stop_event))

    yield

    logger.info("shutting_down_inventory_service")
    stop_event.set()

    try:
        await asyncio.wait_for(consumer_task, timeout=10.0)
        logger.info("Consumer task finished cleanly")
    except TimeoutError:
        logger.error("Consumer task timed out during shutdown")
        consumer_task.cancel()
    except Exception as ex:
        logger.error("Error during consumer shutdown", error=ex)
    finally:
        await inventory_command_manager.stop()
        logger.info("stopping_inventory_service")


app = FastAPI(
    title="Inventory Service",
    lifespan=lifespan
)

app.include_router(health_router, prefix="/api/v1")
