from datetime import UTC, datetime

from sqlalchemy import select

from app.models import SagaStateOrm
from app.repositories.base import BaseRepository
from app.schemas.saga import SagaState


class SagaStateRepository(BaseRepository):
    model = SagaStateOrm
    schema = SagaState

    async def get_due_retries(self) -> list[SagaState]:
        query = (
            select(self.model)
            .where(self.model.retry_after.is_not(None))
            .where(self.model.retry_after <= datetime.now(UTC).replace(tzinfo=None))
        )
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self.schema.model_validate(model, from_attributes=True) for model in models]
