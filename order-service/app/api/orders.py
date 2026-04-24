import uuid

from fastapi import APIRouter

from app.api.dependecies import DBDep, TokenDep, ProducerDep
from app.core.exceptions import (
    DatabaseNotUnavailableHTTPException,
    DatabaseNotUnavailableException,
    OrderValidationHTTPException,
    OrderValidationException,
    OrderNotFoundException,
    OrderNotFoundHTTPException,
    OrderCannotBeCancelledException,
    OrderCannotBeCancelledHTTPException,
)
from app.schemas.orders import OrderCreateRequest, Order, OrderResponse
from app.services.orders import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderResponse)
async def create_order(
    db: DBDep,
    token_data: TokenDep,
    producer: ProducerDep,
    data: OrderCreateRequest
):
    try:
        user_id = token_data.user_id
        return await OrdersService(db, producer).create_order(user_id, data)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderValidationException as ex:
        raise OrderValidationHTTPException from ex


@router.get("/", response_model=list[OrderResponse])
async def get_orders(db: DBDep):
    try:
        return await OrdersService(db).get_orders()
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(db: DBDep, order_id: uuid.UUID):
    try:
        return await OrdersService(db).get_order(order_id)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderNotFoundException as ex:
        raise OrderNotFoundHTTPException from ex


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(db: DBDep, order_id: uuid.UUID):
    try:
        return await OrdersService(db).cancel_order(order_id)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderNotFoundException as ex:
        raise OrderNotFoundHTTPException from ex
    except OrderCannotBeCancelledException as ex:
        raise OrderCannotBeCancelledHTTPException from ex
