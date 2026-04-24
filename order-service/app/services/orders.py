import socket
import uuid
from datetime import datetime
from decimal import Decimal

from aiokafka.errors import KafkaError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import (
    DatabaseNotUnavailableException,
    OrderValidationException,
    ObjectNotFoundException,
    OrderNotFoundException,
    OrderCannotBeCancelledException,
)
from app.core.logger import logger
from app.models.orders import StatusEnum
from app.schemas.kafka import KafkaOrderEvent
from app.schemas.orders import (
    OrderCreateRequest,
    OrderCreate,
    Order,
    OrderResponse,
    OrderUpdateStatus,
)
from app.services.base import BaseService


class OrdersService(BaseService):
    async def create_order(self, user_id: uuid.UUID, data: OrderCreateRequest) -> OrderResponse:
        try:
            total_amount = sum(
                Decimal(str(v["price"])) * int(v.get("quantity", 1))
                for v in data.items.values()
            )
        except (KeyError, TypeError, ValueError) as ex:
            raise OrderValidationException from ex

        new_order = OrderCreate(
            user_id=user_id,
            items=data.items,
            total_amount=Decimal(total_amount),
            saga_id=uuid.uuid4()
        )

        try:
            new_order_data: Order = await self.db.orders.add(new_order)
            await self.db.commit()
        except (SQLAlchemyError, socket.error) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

        kafka_data = KafkaOrderEvent(
            event_id=uuid.uuid4(),
            event_type="order.created",
            saga_id=new_order_data.saga_id,
            order_id=new_order_data.id,
            user_id=new_order_data.user_id,
            items=new_order_data.items,
            total_amount=new_order_data.total_amount,
            timestamp=datetime.now(),
        )

        try:
            await self.producer.send_and_wait(
                topic=settings.KAFKA_ORDER_TOPIC,
                value=kafka_data.model_dump_json().encode("utf-8"),
                key=str(new_order_data.id).encode("utf-8"),
            )
        except KafkaError as ex:
            logger.error("Failed to send event to Kafka", data=data, error=ex)

        return OrderResponse(**new_order_data.model_dump())

    async def get_orders(self) -> list[OrderResponse]:
        try:
            orders_data: list[OrderResponse] = await self.db.orders.get_all()
            return orders_data
        except (SQLAlchemyError, socket.error) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def get_order(self, order_id: uuid.UUID) -> OrderResponse:
        try:
            order_data = await self.db.orders.get_one(id=order_id)
            return order_data
        except ObjectNotFoundException as ex:
            raise OrderNotFoundException from ex
        except (SQLAlchemyError, socket.error) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def cancel_order(self, order_id: uuid.UUID) -> OrderResponse:
        try:
            order = await self.db.orders.get_one(with_lock=True, id=order_id)
            if order.status != StatusEnum.PENDING:
                raise OrderCannotBeCancelledException

            update_order_data = OrderUpdateStatus(status=StatusEnum.CANCELLED)
            new_order_data = await self.db.orders.edit(update_order_data, exclude_unset=True, id=order_id)
            await self.db.commit()

            return new_order_data

        except ObjectNotFoundException as ex:
            raise OrderNotFoundException from ex
        except (SQLAlchemyError, socket.error) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex
