from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ObjectNotFoundException


class BaseRepository:
    model = None
    schema = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_one(self, with_lock: bool = False, **filter_by) -> BaseModel:
        query = select(self.model).filter_by(**filter_by)
        if with_lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
        try:
            model = result.scalar_one()
        except NoResultFound as ex:
            raise ObjectNotFoundException from ex
        return self.schema.model_validate(model, from_attributes=True)

    async def get_filtered(self, *filter, **filter_by) -> list[BaseModel]:
        query = select(self.model).filter(*filter).filter_by(**filter_by)
        result = await self.session.execute(query)
        return [self.schema.model_validate(model) for model in result.scalars().all()]

    async def get_all(self, *args, **kwargs) -> list[BaseModel]:
        return await self.get_filtered(*args, **kwargs)

    async def add(self, data: BaseModel) -> BaseModel:
        add_data_stmt = insert(self.model).values(**data.model_dump()).returning(self.model)
        result = await self.session.execute(add_data_stmt)
        model = result.scalars().one()
        return self.schema.model_validate(model)

    async def edit(self, data: BaseModel, exclude_unset: bool = False, **filter_by) -> None:
        update_stmt = (
            update(self.model)
            .filter_by(**filter_by)
            .values(**data.model_dump(exclude_unset=exclude_unset))
        ).returning(self.model)
        result = await self.session.execute(update_stmt)
        model = result.scalar_one()
        return self.schema.model_validate(model)
