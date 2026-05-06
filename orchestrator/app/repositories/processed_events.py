from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert

from app.models import ProcessedEventsOrm
from app.repositories.base import BaseRepository
from app.schemas.processed_events import ProcessedEvent


class ProcessedEventsRepository(BaseRepository):
    model = ProcessedEventsOrm
    schema = ProcessedEvent

    async def add(self, data: BaseModel) -> bool:
        stmt = (
            insert(ProcessedEventsOrm)
            .values(**data.model_dump())
            .on_conflict_do_nothing(index_elements=[ProcessedEventsOrm.event_id])
            .returning(ProcessedEventsOrm.event_id)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return model is not None
