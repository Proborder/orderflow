from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.orm import joinedload

from app.models.refresh_tokens import RefreshTokensOrm
from app.repositories.base import BaseRepository
from app.schemas.refresh_tokens import RefreshToken, RefreshTokenAdd


class RefreshTokensRepository(BaseRepository):
    model = RefreshTokensOrm
    schema = RefreshToken

    async def get_one_or_none(self, **filter_by) -> BaseModel | None:
        query = (
            select(self.model)
            .options(joinedload(self.model.user))
            .filter_by(**filter_by)
        )
        result = await self.session.execute(query)
        model = result.unique().scalar_one_or_none()
        if model is None:
            return None
        return RefreshToken.model_validate(model)

    async def add_without_user(self, data: BaseModel) -> BaseModel:
        add_data_stmt = insert(self.model).values(**data.model_dump()).returning(self.model)
        result = await self.session.execute(add_data_stmt)
        model = result.scalars().one()
        return RefreshTokenAdd.model_validate(model)
