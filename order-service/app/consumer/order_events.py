import asyncio

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError, CommitFailedError
from sqlalchemy import text

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.models.orders import StatusEnum
from app.repositories.orders import OrdersRepository
from app.schemas.kafka import CommandMessage
from app.schemas.orders import OrderUpdateStatus

ORDER_COMMAND_STATUS_MAP = {
    "saga.completed": StatusEnum.COMPLETED,
    "saga.cancelled": StatusEnum.CANCELLED,
}


class OrderEventConsumer:
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
                                command: CommandMessage = CommandMessage.model_validate_json(message.value)
                                logger.info(
                                    "Order command received",
                                    command_type=command.command_type,
                                    order_id=command.order_id,
                                    message_id=command.message_id,
                                )
                                await self.command_handling(session, command)

                        await session.commit()

                        try:
                            await self.consumer.commit()
                        except CommitFailedError as ex:
                            logger.warning(
                                "Kafka rebalance occurred. Batch processed but offset not committed",
                                error=ex
                            )

                    except Exception as ex:
                        logger.error("Order command batch processing failed", error=ex)
                        await session.rollback()

                        for tp, messages in data.items():
                            first_offset = messages[0].offset
                            logger.info(f"Seeking back to offset {first_offset} for partition {tp.partition}")
                            self.consumer.seek(tp, first_offset)

                        await asyncio.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
                        continue

        except asyncio.CancelledError:
            logger.info("Order event worker shutdown")

    async def command_handling(self, session, command: CommandMessage):
        try:
            next_status = ORDER_COMMAND_STATUS_MAP.get(command.command_type)
            if not next_status:
                logger.warning(
                    "Unknown order command received",
                    command_type=command.command_type,
                    message_id=command.message_id,
                    order_id=command.order_id,
                )
                return

            order_exists = await OrdersRepository(session).get_one_or_none(id=command.order_id)
            if not order_exists:
                logger.warning(
                    "The order does not exist",
                    command_type=command.command_type,
                    message_id=command.message_id,
                    order_id=command.order_id
                )
                return

            if order_exists.status == next_status:
                logger.info(
                    "Order command already applied",
                    command_type=command.command_type,
                    order_id=command.order_id,
                    status=next_status
                )
                return

            if order_exists.status != StatusEnum.PENDING:
                logger.warning(
                    "Order status transition rejected",
                    command_type=command.command_type,
                    order_id=command.order_id,
                    current_status=order_exists.status,
                    next_status=next_status
                )
                return

            order_update_data = OrderUpdateStatus(status=next_status)
            await OrdersRepository(session).edit(order_update_data, exclude_unset=True, id=command.order_id)

        except Exception as ex:
            logger.error(
                "Unexpected order command handling error",
                command_type=command.command_type,
                message_id=command.message_id,
                order_id=command.order_id,
                error=ex
            )
            raise
