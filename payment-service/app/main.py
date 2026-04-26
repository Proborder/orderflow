import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.logger import logger
from app.core.payment_command import PaymentCommandManager


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting payment service")
    stop_event = asyncio.Event()

    payment_command_manager = PaymentCommandManager()
    await payment_command_manager.start()
    consumer_task = asyncio.create_task(payment_command_manager.consume(stop_event))

    yield

    logger.info("Shutting down payment service")
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
        await payment_command_manager.stop()
        logger.info("Stopping payment service")


app = FastAPI(
    title="Payment Service",
    lifespan=lifespan
)

app.include_router(health_router, prefix="/api/v1")
