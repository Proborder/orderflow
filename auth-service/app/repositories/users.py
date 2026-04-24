from pydantic import EmailStr
from sqlalchemy import select

from app.models.users import UsersOrm
from app.repositories.base import BaseRepository
from app.schemas.users import User, UserWithHashedPassword


class UsersRepository(BaseRepository):
    model = UsersOrm
    schema = User

    async def get_user_with_hashed_password(self, email: EmailStr) -> UserWithHashedPassword | None:
        query = select(self.model).filter_by(email=email)
        result = await self.session.execute(query)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return UserWithHashedPassword.model_validate(model)
