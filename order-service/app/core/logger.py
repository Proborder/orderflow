import structlog
from structlog.contextvars import merge_contextvars


def setup_logging():
    structlog.configure(
        processors=[
            # 1. Слияние контекстных переменных (наш request_id будет здесь)
            merge_contextvars,
            # 2. Добавление уровня лога (info, error)
            structlog.processors.add_log_level,
            # 3. Добавление таймстемпа в формате ISO
            structlog.processors.TimeStamper(fmt="iso"),
            # 4. JSON-форматирование для Docker/ELK
            structlog.processors.JSONRenderer()
        ],
        # Стандартный логгер, который будет выводить в консоль
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Инициализируем настройки
setup_logging()
logger = structlog.get_logger()
