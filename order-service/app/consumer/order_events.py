import asyncio

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError, CommitFailedError
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.models.orders import StatusEnum
from app.repositories.orders import OrdersRepository
from app.schemas.kafka import SagaOrderEventMessage, BaseEventMessage
from app.schemas.orders import OrderUpdateStatus

SAGA_EVENT_STATUS_MAP = {
    "saga.completed": StatusEnum.COMPLETED,
    "saga.cancelled": StatusEnum.CANCELLED,
}


class OrderEventsConsumer:
    def __init__(self, consumer: AIOKafkaConsumer):
        self.consumer: AIOKafkaConsumer = consumer

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

                async with async_session_maker() as session:
                    try:
                        await session.execute(text("SELECT set_config('app.current_user_role', 'admin', true)"))

                        for _, messages in data.items():
                            for message in messages:
                                base_event = BaseEventMessage.model_validate_json(message.value)
                                if base_event.event_type not in SAGA_EVENT_STATUS_MAP:
                                    logger.info("Order event skipped", event_type=base_event.event_type)
                                    continue

                                event = SagaOrderEventMessage.model_validate_json(message.value)
                                logger.info(
                                    "Saga event received",
                                    event_type=event.event_type,
                                    event_id=event.event_id,
                                    order_id=event.order_id,
                                    saga_id=event.saga_id
                                )
                                await self.handle_event(session, event)

                        await session.commit()

                        try:
                            await self.consumer.commit()
                        except CommitFailedError as ex:
                            logger.warning(
                                "Kafka rebalance occurred. Batch processed but offset not committed",
                                error=ex
                            )

                    except Exception as ex:
                        logger.error("Order event batch processing failed", error=ex)
                        await session.rollback()

                        for tp, messages in data.items():
                            first_offset = messages[0].offset
                            logger.info(f"Seeking back to offset {first_offset} for partition {tp.partition}")
                            self.consumer.seek(tp, first_offset)

                        await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                        continue

        except asyncio.CancelledError:
            logger.info("Order event worker shutdown")

    async def handle_event(self, session, event: SagaOrderEventMessage):
        try:
            next_status = SAGA_EVENT_STATUS_MAP.get(event.event_type)
            if not next_status:
                logger.warning(
                    "Unknown order event received",
                    event_type=event.event_type,
                    message_id=event.message_id,
                    order_id=event.order_id
                )
                return

            order_exists = await OrdersRepository(session).get_one_or_none(id=event.order_id)
            if not order_exists:
                logger.warning(
                    "The order does not exist",
                    event_type=event.event_type,
                    message_id=event.message_id,
                    order_id=event.order_id
                )
                return

            if order_exists.status == next_status:
                logger.info(
                    "Order event already applied",
                    event_type=event.event_type,
                    order_id=event.order_id,
                    status=next_status
                )
                return

            if order_exists.status != StatusEnum.PENDING:
                logger.warning(
                    "Order status transition rejected",
                    event_type=event.event_type,
                    order_id=event.order_id,
                    current_status=order_exists.status,
                    next_status=next_status
                )
                return

            order_update_data = OrderUpdateStatus(status=next_status)
            await OrdersRepository(session).edit(order_update_data, exclude_unset=True, id=event.order_id)

        except Exception as ex:
            logger.error(
                "Unexpected order event handling error",
                event_type=event.event_type,
                message_id=event.message_id,
                order_id=event.order_id,
                error=ex
            )
            raise
