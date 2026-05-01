from app.models import SagaStateOrm
from app.repositories.base import BaseRepository
from app.schemas.saga import SagaState


class SagaStateRepository(BaseRepository):
    model = SagaStateOrm
    schema = SagaState
