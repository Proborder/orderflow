from pydantic import BaseModel
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    model = None
    schema = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, data: BaseModel) -> BaseModel:
        add_data_stmt = insert(self.model).values(**data.model_dump()).returning(self.model)
        result = await self.session.execute(add_data_stmt)
        model = result.scalar().one()
        return self.schema.model_validate(model)
