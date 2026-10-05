"""Run one ingestion pass from the command line."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_engine
from app.ingestion.client import HttpxFeedClient
from app.ingestion.pipeline import run_ingestion


def main() -> None:
    with Session(get_engine()) as session:
        report = run_ingestion(
            session,
            HttpxFeedClient(timeout=get_settings().ingestion_timeout_seconds),
            force=True,
        )
    print(
        "Stored "
        f"{report.articles_stored} articles. "
        f"Succeeded {report.sources_succeeded}, "
        f"failed {report.sources_failed}, "
        f"skipped {report.sources_skipped}."
    )
    for result in report.results:
        if result.status == "skipped":
            continue
        detail = result.error or f"stored {result.articles_stored}"
        print(f"- {result.source_name}: {result.status} ({detail})")


if __name__ == "__main__":
    main()
