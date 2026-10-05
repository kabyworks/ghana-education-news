"""Score stored articles."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.intelligence.relevance.service import score_articles

router = APIRouter(prefix="/relevance", tags=["relevance"])


class RelevanceRunRead(BaseModel):
    considered: int
    publish: int
    reject: int
    review: int


@router.post("/run", response_model=RelevanceRunRead)
def run_relevance(force: bool = False, session: Session = Depends(get_db)) -> RelevanceRunRead:
    report = score_articles(session, force=force)
    return RelevanceRunRead(
        considered=report.considered,
        publish=report.publish,
        reject=report.reject,
        review=report.review,
    )
