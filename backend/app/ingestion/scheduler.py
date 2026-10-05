"""Background loop that fetches sources when they are due."""

import logging
import threading

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_engine
from app.ingestion.client import HttpxFeedClient
from app.ingestion.pipeline import IngestionBusyError, run_ingestion

logger = logging.getLogger(__name__)


class IngestionScheduler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ingestion", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_scheduled_ingestion()
            except Exception:
                logger.exception("Scheduled ingestion failed")
            if self._stop.wait(get_settings().ingestion_interval_seconds):
                return


def run_scheduled_ingestion() -> None:
    with Session(get_engine()) as session:
        try:
            run_ingestion(
                session,
                HttpxFeedClient(timeout=get_settings().ingestion_timeout_seconds),
                force=False,
            )
        except IngestionBusyError:
            logger.info("Skipped scheduled ingestion because a run is already in progress")
