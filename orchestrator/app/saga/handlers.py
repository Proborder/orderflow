from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StateEnum
from app.saga.service import SagaService
from app.schemas.events import BaseEventMessage
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

    async def dispatch(self, session: AsyncSession, raw_event: str) -> CommandMessage | OrderEventMessage | None:
        event = BaseEventMessage.model_validate_json(raw_event)
        current_state = await self.service.get_current_state(session, event)

        handler = self.routes.get((event.event_type, current_state))
        if handler is None:
            return await self.service.ignore_event(raw_event, current_state)

        return await handler(session=session, raw_event=raw_event)
