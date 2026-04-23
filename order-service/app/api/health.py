from fastapi import APIRouter

from app.core.logger import logger

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def ping():
    logger.info("healthcheck_called")
    return {"status": "ok"}
