import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import uniform

from aiokafka.errors import KafkaError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logger import logger
from app.models import StateEnum
from app.producer.commands import CommandsProducer
from app.repositories.saga import SagaStateRepository
from app.saga.service import command_message_id
from app.schemas.messages import CommandMessage, DlqEventMessage, OrderEventMessage
from app.schemas.saga import SagaState, UpdateSagaState


class SagaRetryWorker:
    def __init__(self):
        self.commands_producer = CommandsProducer()

    async def start(self, stop_event: asyncio.Event):
        try:
            while not stop_event.is_set():
                async with async_session_maker() as session:
                    due_sagas = await SagaStateRepository(session).get_due_retries()

                    for saga in due_sagas:
                        await self.process_retry(session, saga)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Saga retry worker stopped")

    async def process_retry(self, session: AsyncSession, saga_state_event: SagaState):
        command = self.get_command(saga_state_event)
        if command is None:
            return

        try:
            if command.command_type in {"reserve_inventory", "cancel_reservation"}:
                await self.commands_producer.send_inventory_command(command)
            else:
                await self.commands_producer.send_payment_command(command)

            new_state_data = UpdateSagaState(retry_after=None)
            await SagaStateRepository(session).edit(
                new_state_data,
                exclude_unset=True,
                saga_id=saga_state_event.saga_id
            )
            await session.commit()

        except KafkaError as ex:
            next_retry_count = saga_state_event.retry_count + 1
            if next_retry_count > settings.SAGA_MAX_RETRIES:
                new_state_data = UpdateSagaState(state=StateEnum.FAILED, retry_after=None)
                await SagaStateRepository(session).edit(
                    new_state_data,
                    exclude_unset=True,
                    saga_id=saga_state_event.saga_id
                )
                await session.commit()

                await self.commands_producer.send_dlq(
                    DlqEventMessage(
                        event_type=command.command_type,
                        saga_id=saga_state_event.saga_id,
                        retry_count=next_retry_count,
                        last_error=str(ex),
                        failed_at=datetime.now(UTC)
                    )
                )
                await self.commands_producer.send_order_status(
                    OrderEventMessage(
                        event_type="saga.cancelled",
                        saga_id=saga_state_event.saga_id,
                        order_id=saga_state_event.order_id
                    )
                )
                return

            delay_seconds = 2 ** next_retry_count + uniform(0.8, 1.2)
            retry_after = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).replace(tzinfo=None)
            new_state_data = UpdateSagaState(
                retry_count=next_retry_count,
                retry_after=retry_after
            )
            await SagaStateRepository(session).edit(
                new_state_data,
                exclude_unset=True,
                saga_id=saga_state_event.saga_id
            )
            await session.commit()

    def get_command(self, saga_event_data: SagaState) -> CommandMessage | None:
        if saga_event_data.state == StateEnum.INVENTORY_RESERVING:
            message_id = command_message_id(
                saga_event_data.saga_id,
                "reserve_inventory",
                retry_count=saga_event_data.retry_count
            )
            return CommandMessage(
                command_type="reserve_inventory",
                saga_id=saga_event_data.saga_id,
                order_id=saga_event_data.order_id,
                payload=saga_event_data.payload["items"],
                message_id=message_id
            )

        if saga_event_data.state == StateEnum.PAYMENT_CHARGING:
            message_id = command_message_id(
                saga_event_data.saga_id,
                "charge_payment",
                retry_count=saga_event_data.retry_count
            )
            return CommandMessage(
                command_type="charge_payment",
                saga_id=saga_event_data.saga_id,
                order_id=saga_event_data.order_id,
                payload=Decimal(saga_event_data.payload["amount"]),
                message_id=message_id
            )

        if saga_event_data.state == StateEnum.COMPENSATING_INVENTORY:
            message_id = command_message_id(
                saga_event_data.saga_id,
                "cancel_reservation",
                retry_count=saga_event_data.retry_count
            )
            return CommandMessage(
                command_type="cancel_reservation",
                saga_id=saga_event_data.saga_id,
                order_id=saga_event_data.order_id,
                payload=saga_event_data.payload["items"],
                message_id=message_id
            )

        return None
