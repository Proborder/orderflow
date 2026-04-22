import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Очищаем контекст перед началом (на случай переиспользования потоков)
        clear_contextvars()

        # Генерируем уникальный ID запроса
        request_id = str(uuid.uuid4())

        # Привязываем request_id к контексту structlog
        bind_contextvars(request_id=request_id)

        # Логируем начало запроса
        logger.info("request_started", path=request.url.path, method=request.method)

        response = await call_next(request)

        # Добавляем ID в заголовок ответа (полезно для отладки на фронтенде)
        response.headers["X-Request-ID"] = request_id

        logger.info("request_finished", status_code=response.status_code)

        return response
