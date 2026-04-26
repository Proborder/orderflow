import uuid

from sqlalchemy import text

from app.core.logger import logger
from app.repositories.orders import OrdersRepository


class DBManager:
    def __init__(self, session_factory, user_id: uuid.UUID = None, role: str = None):
        self.session_factory = session_factory
        self.user_id = user_id
        self.role = role

    async def __aenter__(self):
        self.session = self.session_factory()

        if self.user_id and self.role:
            await self.session.execute(
                text(
                    "SELECT set_config('app.current_user_id', :uid, true), "
                    "set_config('app.current_user_role', :role, true)"
                ),
                {"uid": str(self.user_id), "role": self.role},
            )

        self.orders = OrdersRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.session.rollback()
                logger.warning("Database session rolled back", error=exc_val)
        finally:
            await self.session.close()

    async def commit(self):
        await self.session.commit()
