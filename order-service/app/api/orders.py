import uuid

from fastapi import APIRouter, Response
from starlette import status

from app.api.dependencies import DBDep, ProducerDep, TokenDep
from app.core.exceptions import (
    DatabaseNotUnavailableException,
    DatabaseNotUnavailableHTTPException,
    OrderCannotBeCancelledException,
    OrderCannotBeCancelledHTTPException,
    OrderNotFoundException,
    OrderNotFoundHTTPException,
    OrderValidationException,
    OrderValidationHTTPException,
)
from app.schemas.orders import OrderCreateRequest, OrderResponse
from app.services.orders import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse)
async def create_order(
    db: DBDep,
    response: Response,
    token_data: TokenDep,
    producer: ProducerDep,
    data: OrderCreateRequest
) -> OrderResponse:
    try:
        user_id = token_data.user_id
        order, is_created = await OrdersService(db, producer).create_order(user_id, data)
        response.status_code = status.HTTP_201_CREATED if is_created else status.HTTP_200_OK
        return order
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderValidationException as ex:
        raise OrderValidationHTTPException from ex


@router.get("/", response_model=list[OrderResponse])
async def get_orders(db: DBDep) -> list[OrderResponse]:
    try:
        return await OrdersService(db).get_orders()
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(db: DBDep, order_id: uuid.UUID) -> OrderResponse:
    try:
        return await OrdersService(db).get_order(order_id)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderNotFoundException as ex:
        raise OrderNotFoundHTTPException from ex


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(db: DBDep, order_id: uuid.UUID) -> OrderResponse:
    try:
        return await OrdersService(db).cancel_order(order_id)
    except DatabaseNotUnavailableException as ex:
        raise DatabaseNotUnavailableHTTPException from ex
    except OrderNotFoundException as ex:
        raise OrderNotFoundHTTPException from ex
    except OrderCannotBeCancelledException as ex:
        raise OrderCannotBeCancelledHTTPException from ex
