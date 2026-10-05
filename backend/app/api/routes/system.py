"""Liveness endpoints. These stay free of news-domain behavior."""

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app import __version__
from app.core.config import get_settings
from app.db.database import get_engine
from app.schemas.system import HealthResponse, RootResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    settings = get_settings()
    return RootResponse(
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        health="/health",
        docs="/docs",
        reader="/app/",
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        database="ok",
    )
