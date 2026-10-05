"""Manual ingestion trigger."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.ingestion.client import HttpxFeedClient
from app.ingestion.pipeline import IngestionBusyError, IngestionReport, run_ingestion
from app.schemas.ingestion import IngestionReportRead

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_feed_client() -> HttpxFeedClient:
    return HttpxFeedClient(timeout=get_settings().ingestion_timeout_seconds)


@router.post("/run", response_model=IngestionReportRead)
def run_now(session: Session = Depends(get_db), client: HttpxFeedClient = Depends(get_feed_client)) -> IngestionReportRead:
    try:
        report = run_ingestion(session, client, force=True)
    except IngestionBusyError:
        raise HTTPException(status_code=409, detail="An ingestion run is already in progress") from None
    return _read_report(report)


def _read_report(report: IngestionReport) -> IngestionReportRead:
    return IngestionReportRead.model_validate(
        {
            "sources_considered": report.sources_considered,
            "sources_succeeded": report.sources_succeeded,
            "sources_failed": report.sources_failed,
            "sources_skipped": report.sources_skipped,
            "articles_discovered": report.articles_discovered,
            "articles_stored": report.articles_stored,
            "duplicates_skipped": report.duplicates_skipped,
            "results": [asdict(result) for result in report.results],
        }
    )
