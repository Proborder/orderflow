import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from random import uniform

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import CommitFailedError, KafkaError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.models import StateEnum
from app.producer.commands import CommandsProducer
from app.repositories.saga import SagaStateRepository
from app.saga.handlers import SagaEventDispatcher
from app.saga.service import SagaService
from app.schemas.events import BaseEventMessage
from app.schemas.messages import CommandMessage, DlqEventMessage
from app.schemas.saga import UpdateSagaState

SAGA_EVENT_TYPES = {
    "order.created",
    "inventory.reserved",
    "inventory.reserve-failed",
    "inventory.reservation-cancelled",
    "payment.succeeded",
    "payment.failed"
}

SAGA_ORDER_EVENT_STATUS_MAP = {
    "saga.completed",
    "saga.cancelled"
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
                            try:
                                base_event = BaseEventMessage.model_validate_json(message.value)
                            except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as ex:
                                await self.commands_producer.send_dlq(self._build_non_retriable_dlq(message.value, ex))
                                logger.error("Invalid event format sent to DLQ", error=ex)
                                continue

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
            command_routes = {
                "reserve_inventory": (self.commands_producer.send_inventory_command, StateEnum.INVENTORY_RESERVING),
                "charge_payment": (self.commands_producer.send_payment_command, StateEnum.PAYMENT_CHARGING),
                "cancel_reservation": (self.commands_producer.send_inventory_command, StateEnum.COMPENSATING_INVENTORY)
            }

            send_command_func, target_state = command_routes.get(message.command_type)
            saga = await SagaStateRepository(session).get_one(saga_id=message.saga_id)

            if saga.state == target_state:
                await self.schedule_retry(
                    session=session,
                    saga_id=message.saga_id,
                    state=target_state,
                    error=Exception("Domain logical retry requested")
                )
                return

            try:
                await send_command_func(message)
                new_state_data = UpdateSagaState(state=target_state, retry_count=0)
                await SagaStateRepository(session).edit(
                    new_state_data,
                    exclude_unset=True,
                    saga_id=message.saga_id
                )
                await session.commit()

            except KafkaError as ex:
                await self.schedule_retry(
                    session=session,
                    saga_id=message.saga_id,
                    state=target_state,
                    error=ex
                )
                return

        else:
            if message.event_type in SAGA_ORDER_EVENT_STATUS_MAP:
                await self.commands_producer.send_order_status(message)

    async def schedule_retry(self, session: AsyncSession, saga_id: uuid.UUID, state: StateEnum, error: Exception):
        saga_data = await SagaStateRepository(session).get_one(saga_id=saga_id)
        next_retry_count = saga_data.retry_count + 1

        if next_retry_count > settings.SAGA_MAX_RETRIES:
            new_state_data = UpdateSagaState(state=StateEnum.FAILED, retry_after=None)
            await SagaStateRepository(session).edit(
                new_state_data,
                exclude_unset=True,
                saga_id=saga_id
            )
            await session.commit()
            await self.commands_producer.send_dlq(
                DlqEventMessage(
                    event_type="orchestrator.retry-exhausted",
                    saga_id=saga_id,
                    retry_count=next_retry_count,
                    last_error=str(error),
                    failed_at=datetime.now(UTC)
                )
            )
            logger.error("Saga moved to FAILED after max retries", saga_id=str(saga_id), error=error)
            return

        delay_seconds = 2 ** next_retry_count + uniform(0.8, 1.2)
        retry_after = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).replace(tzinfo=None)
        new_state_data = UpdateSagaState(
            state=state,
            retry_count=next_retry_count,
            retry_after=retry_after
        )
        await SagaStateRepository(session).edit(
            new_state_data,
            exclude_unset=True,
            saga_id=saga_id
        )
        await session.commit()

    @staticmethod
    def _build_non_retriable_dlq(raw_event: str, error: Exception):
        saga_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

        try:
            parsed = json.loads(raw_event)
            if isinstance(parsed, dict):
                if "saga_id" in parsed:
                    saga_id = uuid.UUID(str(parsed["saga_id"]))
        except Exception:
            pass

        from app.schemas.messages import DlqEventMessage

        return DlqEventMessage(
            saga_id=saga_id,
            event_type="orchestrator.invalid-event",
            retry_count=0,
            last_error=str(error),
            failed_at=datetime.now(UTC)
        )
