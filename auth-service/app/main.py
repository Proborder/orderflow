from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.middleware import LoggingMiddleware

app = FastAPI(
    title="Auth Service API",
)

app.add_middleware(LoggingMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
