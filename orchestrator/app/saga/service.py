import uuid
from decimal import Decimal
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.models import StateEnum
from app.repositories.saga import SagaStateRepository
from app.schemas.events import BaseEventMessage, InventoryEvent, OrderCreatedEvent, PaymentEvent
from app.schemas.messages import CommandMessage, OrderEventMessage
from app.schemas.saga import CreateSagaState, UpdateSagaState

SAGA_COMMAND_NAMESPACE = uuid.UUID("12345678-1234-1234-1234-123456789abc")


class SagaService:
    def __init__(self, repository_factory: Callable[[AsyncSession], SagaStateRepository] = SagaStateRepository):
        self.repository_factory = repository_factory

    def repository(self, session: AsyncSession) -> SagaStateRepository:
        return self.repository_factory(session)

    async def get_current_state(self, session: AsyncSession, event: BaseEventMessage) -> StateEnum | None:
        if event.event_type == "order.created":
            return None

        saga_data = await self.repository(session).get_one(saga_id=event.saga_id)
        return saga_data.state

    async def start_saga(self, session: AsyncSession, event_data: OrderCreatedEvent) -> CommandMessage:
        payload = {
            "items": event_data.items,
            "amount": str(event_data.total_amount)
        }
        add_saga_data = CreateSagaState(
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=payload
        )
        await self.repository(session).add(add_saga_data)
        await session.commit()
        logger.info(
            "Saga state transition",
            saga_id=str(event_data.saga_id),
            order_id=str(event_data.order_id),
            event_type=event_data.event_type,
            state=StateEnum.CREATED.value
        )

        command_type = "reserve_inventory"
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=payload["items"],
            message_id=message_id
        )

    async def handle_inventory_reserved(self, session: AsyncSession, event_data: InventoryEvent) -> CommandMessage:
        saga_event_data = await self._transition_state(session, event_data, StateEnum.INVENTORY_RESERVED)

        command_type = "charge_payment"
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=Decimal(saga_event_data.payload["amount"]),
            message_id=message_id
        )

    async def handle_inventory_failed(
        self,
        session: AsyncSession,
        event_data: InventoryEvent
    ) -> OrderEventMessage | CommandMessage:
        saga_event_data = await self.repository(session).get_one(saga_id=event_data.saga_id)

        retry_command = await self._retry_same_step_or_none(
            saga_event_data=saga_event_data,
            command_type="reserve_inventory",
            payload=saga_event_data.payload["items"],
            msg="Saga inventory failed, retry scheduled"
        )
        if retry_command:
            return retry_command

        saga_event_data = await self._transition_state(session, event_data, StateEnum.CANCELLED)

        return OrderEventMessage(
            event_id=uuid.uuid4(),
            event_type="saga.cancelled",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id,
        )

    async def handle_payment_succeeded(
        self, session: AsyncSession,
        event_data: PaymentEvent
    ) -> OrderEventMessage:
        saga_event_data = await self._transition_state(session, event_data, StateEnum.COMPLETED)

        return OrderEventMessage(
            event_id=uuid.uuid4(),
            event_type="saga.completed",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id,
        )

    async def handle_payment_failed(self, session: AsyncSession, event_data: PaymentEvent) -> CommandMessage:
        saga_event_data = await self.repository(session).get_one(saga_id=event_data.saga_id)

        retry_command = await self._retry_same_step_or_none(
            saga_event_data=saga_event_data,
            command_type="charge_payment",
            payload=Decimal(saga_event_data.payload["amount"]),
            msg="Saga payment failed, retry scheduled"
        )
        if retry_command is not None:
            return retry_command

        logger.warning(
            "Saga payment failed, start compensation",
            saga_id=str(event_data.saga_id),
            order_id=str(event_data.order_id)
        )
        command_type = "cancel_reservation"
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=saga_event_data.payload["items"],
            message_id=message_id
        )

    async def handle_inventory_cancelled(
        self, session: AsyncSession,
        event_data: InventoryEvent
    ) -> OrderEventMessage:
        saga_event_data = await self._transition_state(session, event_data, StateEnum.CANCELLED)

        return OrderEventMessage(
            event_id=uuid.uuid4(),
            event_type="saga.cancelled",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id
        )

    async def ignore_event(self, event: BaseEventMessage, state: StateEnum | None) -> None:
        logger.info(
            "Saga event ignored",
            event_type=event.event_type,
            state=state.value if isinstance(state, StateEnum) else None
        )

    async def _transition_state(self, session: AsyncSession, event: BaseEventMessage, state: StateEnum):
        saga_data = await self.repository(session).edit(
            UpdateSagaState(state=state),
            exclude_unset=True,
            saga_id=event.saga_id
        )
        await session.commit()
        logger.info(
            "Saga state transition",
            saga_id=str(saga_data.saga_id),
            order_id=str(saga_data.order_id),
            event_type=event.event_type,
            state=state.value
        )
        return saga_data

    async def _retry_same_step_or_none(
        self,
        saga_event_data,
        command_type: str,
        payload,
        msg: str
    ) -> CommandMessage | None:
        if saga_event_data.retry_count >= settings.SAGA_MAX_RETRIES:
            return None

        next_retry_count = saga_event_data.retry_count + 1
        logger.warning(
            msg,
            saga_id=str(saga_event_data.saga_id),
            order_id=str(saga_event_data.order_id),
            retry_count=next_retry_count
        )
        message_id = command_message_id(saga_event_data.saga_id, command_type, retry_count=next_retry_count)
        return CommandMessage(
            command_type=command_type,
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id,
            payload=payload,
            message_id=message_id
        )


def command_message_id(saga_id: uuid.UUID, step: str, retry_count: int = 0) -> uuid.UUID:
    identifier = f"{saga_id}:{step}"

    if retry_count > 0:
        identifier = f"{identifier}:retry:{retry_count}"

    return uuid.uuid5(SAGA_COMMAND_NAMESPACE, identifier)
