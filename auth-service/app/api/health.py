from fastapi import APIRouter
from sqlalchemy import text
from starlette import status
from starlette.responses import JSONResponse

from app.api.dependencies import DBDep
from app.core.logger import logger

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def ping() -> dict[str, str]:
    logger.info("Healthcheck called")
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: DBDep) -> JSONResponse:
    logger.info("Readiness check called")

    checks = {"postgresql": "ok"}
    status_code = status.HTTP_200_OK

    try:
        await db.session.execute(text("SELECT 1"))
    except Exception as ex:
        logger.warning("Readiness check failed: PostgreSQL is unavailable", error=ex)
        checks["postgresql"] = "Unavailable"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(status_code=status_code, content=checks)
