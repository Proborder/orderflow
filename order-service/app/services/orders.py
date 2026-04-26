import uuid
from datetime import datetime
from decimal import Decimal

from aiokafka.errors import KafkaError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import (
    DatabaseNotUnavailableException,
    ObjectNotFoundException,
    OrderCannotBeCancelledException,
    OrderNotFoundException,
    OrderValidationException,
)
from app.core.logger import logger
from app.models.orders import StatusEnum
from app.schemas.kafka import KafkaOrderEvent
from app.schemas.orders import (
    Order,
    OrderCreate,
    OrderCreateRequest,
    OrderResponse,
    OrderUpdateStatus,
)
from app.services.base import BaseService


class OrdersService(BaseService):
    async def create_order(self, user_id: uuid.UUID, data: OrderCreateRequest) -> tuple[OrderResponse, bool]:
        try:
            existing_order = await self.db.orders.get_one_or_none(idempotency_key=data.idempotency_key)
            if existing_order:
                logger.info("Order already exists for idempotency key", data=str(existing_order.id))
                return existing_order, False
        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

        try:
            total_amount = sum(
                Decimal(str(v["price"])) * int(v.get("quantity", 1)) for v in data.items.values()
            )
        except (KeyError, TypeError, ValueError) as ex:
            logger.warning("Order validation failed", error=ex)
            raise OrderValidationException from ex

        new_order = OrderCreate(
            user_id=user_id,
            items=data.items,
            total_amount=Decimal(total_amount),
            saga_id=uuid.uuid4(),
            idempotency_key=data.idempotency_key,
        )

        try:
            new_order_data: Order = await self.db.orders.add(new_order)
            await self.db.commit()
            logger.info("Order saved to database", data=str(new_order_data.id))
        except (SQLAlchemyError, OSError) as ex:
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
            logger.info(
                "Order event sent to Kafka",
                order_id=str(new_order_data.id),
                saga_id=str(new_order_data.saga_id),
            )
        except KafkaError as ex:
            logger.error("Failed to send event to Kafka", data=data, error=ex)

        return new_order_data, True

    async def get_orders(self) -> list[OrderResponse]:
        try:
            orders_data: list[Order] = await self.db.orders.get_all()
            logger.info("Orders fetched", count=len(orders_data))
            return orders_data
        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def get_order(self, order_id: uuid.UUID) -> OrderResponse:
        try:
            order_data = await self.db.orders.get_one(id=order_id)
            logger.info("Order fetched", data=str(order_id))
            return order_data
        except ObjectNotFoundException as ex:
            logger.warning("Order not found", data=str(order_id))
            raise OrderNotFoundException from ex
        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex

    async def cancel_order(self, order_id: uuid.UUID) -> OrderResponse:
        try:
            order = await self.db.orders.get_one(with_lock=True, id=order_id)
            if order.status != StatusEnum.PENDING:
                logger.warning("Order cannot be cancelled", data=str(order_id), status=order.status)
                raise OrderCannotBeCancelledException

            update_order_data = OrderUpdateStatus(status=StatusEnum.CANCELLED)
            new_order_data = await self.db.orders.edit(update_order_data, exclude_unset=True, id=order_id)
            await self.db.commit()
            logger.info("Order cancelled", data=str(order_id))

            return new_order_data

        except ObjectNotFoundException as ex:
            logger.warning("Order not found", data=str(order_id))
            raise OrderNotFoundException from ex
        except (SQLAlchemyError, OSError) as ex:
            logger.error("Database connection error during fetch", error=ex)
            raise DatabaseNotUnavailableException from ex
