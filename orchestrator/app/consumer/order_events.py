import asyncio

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import CommitFailedError, KafkaError

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.models import StateEnum
from app.producer.commands import CommandsProducer
from app.repositories.saga import SagaStateRepository
from app.saga.handlers import SagaEventDispatcher
from app.saga.service import CommandMessage, SagaService
from app.schemas.events import BaseEventMessage
from app.schemas.saga import UpdateSagaState

SAGA_EVENT_TYPES = {
    "order.created",
    "inventory.reserved",
    "inventory.reserve-failed",
    "inventory.reservation-cancelled",
    "payment.succeeded",
    "payment.failed",
}

SAGA_ORDER_EVENT_STATUS_MAP = {
    "saga.completed",
    "saga.cancelled",
}


class OrderEventsConsumer:
    def __init__(self, consumer: AIOKafkaConsumer):
        self.consumer: AIOKafkaConsumer = consumer
        self.saga_service = SagaService()
        self.saga_dispatcher = SagaEventDispatcher(self.saga_service)
        self.commands_producer = CommandsProducer()

    async def consume(self, stop_event: asyncio.Event):
        if self.consumer is None:
            raise RuntimeError("Kafka consumer is not initialized")

        try:
            while not stop_event.is_set():
                try:
                    data = await self.consumer.getmany(
                        timeout_ms=settings.KAFKA_CONSUMER_TIMEOUT,
                        max_records=settings.KAFKA_CONSUMER_MAX_RECORDS,
                    )
                except KafkaError as ex:
                    logger.error("Kafka connection lost or error occurred", error=ex)
                    await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                    continue

                if not data:
                    continue

                try:
                    for _, messages in data.items():
                        for message in messages:
                            base_event = BaseEventMessage.model_validate_json(message.value)
                            if base_event.event_type not in SAGA_EVENT_TYPES:
                                logger.info("Event skipped", event_type=base_event.event_type)
                                continue

                            async with async_session_maker() as session:
                                try:
                                    await self.handle_event(session, message.value)
                                except Exception as ex:
                                    logger.error("Order event batch processing failed", error=ex)
                                    await session.rollback()

                    try:
                        await self.consumer.commit()
                    except CommitFailedError as ex:
                        logger.warning(
                            "Kafka rebalance occurred. Batch processed but offset not committed",
                            error=ex
                        )

                except Exception as ex:
                    logger.error("Order event batch processing failed", error=ex)
                    for tp, messages in data.items():
                        first_offset = messages[0].offset
                        logger.info(f"Seeking back to offset {first_offset} for partition {tp.partition}")
                        self.consumer.seek(tp, first_offset)

                    await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                    continue

        except asyncio.CancelledError:
            logger.info("Order event worker shutdown")

    async def handle_event(self, session, raw_event: str):
        message = await self.saga_dispatcher.dispatch(session, raw_event)
        if message is None:
            return

        if isinstance(message, CommandMessage):
            new_state_data = None

            if message.command_type == "reserve_inventory":
                await self.commands_producer.send_inventory_command(message)
                new_state_data = UpdateSagaState(state=StateEnum.INVENTORY_RESERVING)

            if message.command_type == "charge_payment":
                await self.commands_producer.send_payment_command(message)
                new_state_data = UpdateSagaState(state=StateEnum.PAYMENT_CHARGING)

            if message.command_type == "cancel_reservation":
                await self.commands_producer.send_inventory_command(message)
                new_state_data = UpdateSagaState(state=StateEnum.COMPENSATING_INVENTORY)

            await SagaStateRepository(session).edit(new_state_data, saga_id=message.saga_id)
            await session.commit()

        else:
            if message.event_type in SAGA_ORDER_EVENT_STATUS_MAP:
                await self.commands_producer.send_order_status(message)
