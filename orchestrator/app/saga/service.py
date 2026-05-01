import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models import StateEnum
from app.repositories.saga import SagaStateRepository
from app.schemas.events import (
    BaseEventMessage,
    InventoryEvent,
    OrderCreatedEvent,
    PaymentEvent,
)
from app.schemas.messages import CommandMessage, OrderEventMessage
from app.schemas.saga import CreateSagaState, UpdateSagaState

SAGA_COMMAND_NAMESPACE = uuid.UUID("12345678-1234-1234-1234-123456789abc")


class SagaService:
    async def get_current_state(self, session: AsyncSession, event: BaseEventMessage) -> StateEnum | None:
        if event.event_type == "order.created":
            return None

        saga_data = await SagaStateRepository(session).get_one(saga_id=event.saga_id)
        return saga_data.state

    async def start_saga(self, session: AsyncSession, raw_event: str) -> CommandMessage:
        event_data = OrderCreatedEvent.model_validate_json(raw_event)
        payload = {
            "items": event_data.items,
            "amount": str(event_data.total_amount),
        }
        add_saga_data = CreateSagaState(
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=payload
        )
        await SagaStateRepository(session).add(add_saga_data)
        await session.commit()

        command_type = "reserve_inventory"
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=payload["items"],
            message_id=message_id
        )

    async def handle_inventory_reserved(self, session: AsyncSession, raw_event: str) -> CommandMessage:
        event_data = InventoryEvent.model_validate_json(raw_event)

        new_state_data = UpdateSagaState(state=StateEnum.INVENTORY_RESERVED)
        saga_event_data = await SagaStateRepository(session).edit(new_state_data, saga_id=event_data.saga_id)
        await session.commit()

        command_type = "charge_payment"
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=Decimal(saga_event_data.payload["amount"]),
            message_id=message_id
        )


    async def handle_inventory_failed(self, session: AsyncSession, raw_event: str) -> OrderEventMessage | None:
        event_data = InventoryEvent.model_validate_json(raw_event)

        new_state_data = UpdateSagaState(state=StateEnum.CANCELLED)
        saga_event_data = await SagaStateRepository(session).edit(new_state_data, saga_id=event_data.saga_id)
        await session.commit()

        return OrderEventMessage(
            event_type="saga.cancelled",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id
        )

    async def handle_payment_succeeded(self, session: AsyncSession, raw_event: str) -> OrderEventMessage | None:
        event_data = PaymentEvent.model_validate_json(raw_event)

        new_state_data = UpdateSagaState(state=StateEnum.COMPLETED)
        saga_event_data = await SagaStateRepository(session).edit(new_state_data, saga_id=event_data.saga_id)
        await session.commit()

        return OrderEventMessage(
            event_type="saga.completed",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id
        )

    async def handle_payment_failed(self, session: AsyncSession, raw_event: str) -> CommandMessage | None:
        event_data = PaymentEvent.model_validate_json(raw_event)

        command_type = "cancel_reservation"
        saga_event_data = await SagaStateRepository(session).get_one(saga_id=event_data.saga_id)
        message_id = command_message_id(event_data.saga_id, command_type)
        return CommandMessage(
            command_type=command_type,
            saga_id=event_data.saga_id,
            order_id=event_data.order_id,
            payload=saga_event_data.payload["items"],
            message_id=message_id
        )

    async def handle_inventory_cancelled(self, session: AsyncSession, raw_event: str) -> OrderEventMessage | None:
        event_data = InventoryEvent.model_validate_json(raw_event)

        new_state_data = UpdateSagaState(state=StateEnum.CANCELLED)
        saga_event_data = await SagaStateRepository(session).edit(new_state_data, saga_id=event_data.saga_id)
        await session.commit()

        return OrderEventMessage(
            event_type="saga.cancelled",
            saga_id=saga_event_data.saga_id,
            order_id=saga_event_data.order_id
        )

    async def ignore_event(self, raw_event: str, state: StateEnum | None) -> CommandMessage | None:
        event = BaseEventMessage.model_validate_json(raw_event)
        logger.info(
            "Saga event ignored",
            event_type=event.event_type,
            state=state.value if isinstance(state, StateEnum) else None
        )
        return None


def command_message_id(saga_id: uuid.UUID, step: str) -> uuid.UUID:
    return uuid.uuid5(SAGA_COMMAND_NAMESPACE, f"{saga_id}:{step}")
