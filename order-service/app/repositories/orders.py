from app.models.orders import OrdersOrm
from app.repositories.base import BaseRepository
from app.schemas.orders import Order


class OrdersRepository(BaseRepository):
    model = OrdersOrm
    schema = Order
