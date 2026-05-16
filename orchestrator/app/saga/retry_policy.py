import uuid
from datetime import UTC, datetime, timedelta
from random import uniform

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.models import StateEnum
from app.repositories.saga import SagaStateRepository
from app.schemas.messages import DlqEventMessage, OrderEventMessage
from app.schemas.saga import UpdateSagaState


class SagaRetryPolicy:
    @staticmethod
    def backoff_schedule(next_retry_count: int) -> tuple[float, datetime]:
        delay_seconds = 2 ** next_retry_count + uniform(0.8, 1.2)
        retry_after = (datetime.now(UTC) + timedelta(seconds=delay_seconds)).replace(tzinfo=None)
        return delay_seconds, retry_after

    @staticmethod
    async def apply_retry_or_fail(
        session: AsyncSession,
        saga_id: uuid.UUID,
        state: StateEnum,
        next_retry_count: int,
        error: Exception,
        commands_producer,
        dlq_event_type: str,
        order_id: uuid.UUID | None = None
    ) -> bool:
        if next_retry_count > settings.SAGA_MAX_RETRIES:
            await SagaStateRepository(session).edit(
                UpdateSagaState(state=StateEnum.FAILED, retry_after=None),
                exclude_unset=True,
                saga_id=saga_id
            )
            await session.commit()

            await commands_producer.send_dlq(
                DlqEventMessage(
                    event_type=dlq_event_type,
                    saga_id=saga_id,
                    retry_count=next_retry_count,
                    last_error=str(error),
                    failed_at=datetime.now(UTC)
                )
            )

            if order_id:
                await commands_producer.send_order_status(
                    OrderEventMessage(
                        event_id=uuid.uuid4(),
                        event_type="saga.cancelled",
                        saga_id=saga_id,
                        order_id=order_id
                    )
                )

            logger.error("Saga moved to FAILED after max retries", saga_id=str(saga_id), error=error)
            return True

        delay_seconds, retry_after = SagaRetryPolicy.backoff_schedule(next_retry_count)
        await SagaStateRepository(session).edit(
            UpdateSagaState(state=state, retry_count=next_retry_count, retry_after=retry_after),
            exclude_unset=True,
            saga_id=saga_id
        )
        await session.commit()

        logger.warning(
            "Saga retry scheduled",
            saga_id=str(saga_id),
            state=state.value,
            retry_count=next_retry_count,
            delay_seconds=round(delay_seconds, 3),
            retry_after=retry_after.isoformat(),
            error=str(error)
        )
        return False
