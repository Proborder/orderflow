from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StateEnum
from app.saga.service import SagaService
from app.schemas.events import BaseEventMessage, InventoryEvent, OrderCreatedEvent, PaymentEvent
from app.schemas.messages import CommandMessage, OrderEventMessage


class SagaEventDispatcher:
    def __init__(self, service: SagaService):
        self.service = service
        self.routes = {
            ("order.created", None): self.service.start_saga,
            ("inventory.reserved", StateEnum.INVENTORY_RESERVING): self.service.handle_inventory_reserved,
            ("inventory.reserve-failed", StateEnum.INVENTORY_RESERVING): self.service.handle_inventory_failed,
            ("payment.succeeded", StateEnum.PAYMENT_CHARGING): self.service.handle_payment_succeeded,
            ("payment.failed", StateEnum.PAYMENT_CHARGING): self.service.handle_payment_failed,
            ("inventory.reservation-cancelled", StateEnum.COMPENSATING_INVENTORY): self.service.handle_inventory_cancelled
        }

    async def dispatch(
        self, session: AsyncSession,
        event: BaseEventMessage
    ) -> CommandMessage | OrderEventMessage | None:
        current_state = await self.service.get_current_state(session, event)

        handler = self.routes.get((event.event_type, current_state))
        if handler is None:
            await self.service.ignore_event(event, current_state)
            return None

        return await handler(session=session, event_data=event)

    @staticmethod
    def parse_event(raw_event: str) -> BaseEventMessage:
        base_event = BaseEventMessage.model_validate_json(raw_event)

        event_parser_by_type = {
            "order.created": OrderCreatedEvent,
            "inventory.reserved": InventoryEvent,
            "inventory.reserve-failed": InventoryEvent,
            "inventory.reservation-cancelled": InventoryEvent,
            "payment.succeeded": PaymentEvent,
            "payment.failed": PaymentEvent
        }
        event = event_parser_by_type.get(base_event.event_type)
        if event is None:
            return base_event
        return event.model_validate_json(raw_event)
