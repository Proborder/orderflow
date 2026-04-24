from fastapi import HTTPException


class OrdersExceptions(Exception):
    detail = "Неожиданная ошибка"

    def __init__(self, *args):
        super().__init__(self.detail, *args)


class DatabaseNotUnavailableException(OrdersExceptions):
    detail = "База данных временна недоступна"


class OrderValidationException(OrdersExceptions):
    detail = "Неверный формат данных"


class ObjectNotFoundException(OrdersExceptions):
    detail = "Объект не найден"


class OrderNotFoundException(OrdersExceptions):
    detail = "Заказ не найден"


class OrderCannotBeCancelledException(OrdersExceptions):
    detail = "Заказ нельзя отменить"


class OrdersHTTPExceptions(HTTPException):
    status_code = 500
    detail = None

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class DatabaseNotUnavailableHTTPException(OrdersHTTPExceptions):
    status_code = 503
    detail = "База данных временно недоступна"


class NoAccessTokenHTTPException(OrdersHTTPExceptions):
    status_code = 401
    detail = "Вы не предоставили токен доступа"


class InvalidAccessTokenHTTPException(OrdersHTTPExceptions):
    status_code = 401
    detail = "Неверный токен доступа"


class TokenExpiredHTTPException(OrdersHTTPExceptions):
    status_code = 401
    detail = "Срок токена истёк"


class OrderValidationHTTPException(OrdersHTTPExceptions):
    status_code = 400
    detail = "Неверный формат данных"


class OrderNotFoundHTTPException(OrdersHTTPExceptions):
    status_code = 404
    detail = "Заказ не найден"


class OrderCannotBeCancelledHTTPException(OrdersHTTPExceptions):
    status_code = 422
    detail = "Заказ нельзя отменить"
