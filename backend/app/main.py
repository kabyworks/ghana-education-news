"""Application entrypoint."""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes.articles import router as articles_router
from app.api.routes.feed import router as feed_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.relevance import router as relevance_router
from app.api.routes.review import router as review_router
from app.api.routes.sources import router as sources_router
from app.api.routes.stories import router as stories_router
from app.api.routes.system import router as system_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.database import reset_engine
from app.ingestion.scheduler import IngestionScheduler

logger = logging.getLogger(__name__)
READER_DIR = Path(__file__).resolve().parent / "reader"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting %s %s (%s)", settings.app_name, __version__, settings.app_env)
    scheduler = IngestionScheduler()
    if settings.ingestion_enabled:
        scheduler.start()
        logger.info("Ingestion scheduler started")
    yield
    scheduler.stop()
    logger.info("Stopped %s", settings.app_name)
    reset_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan, debug=False)
    app.include_router(system_router)
    app.include_router(sources_router)
    app.include_router(articles_router)
    app.include_router(ingestion_router)
    app.include_router(relevance_router)
    app.include_router(stories_router)
    app.include_router(feed_router)
    app.include_router(review_router)

    @app.get("/app/manifest.webmanifest", include_in_schema=False)
    def reader_manifest() -> FileResponse:
        return FileResponse(READER_DIR / "manifest.webmanifest", media_type="application/manifest+json")

    app.mount("/app", StaticFiles(directory=READER_DIR, html=True), name="reader")
    return app


app = create_app()
