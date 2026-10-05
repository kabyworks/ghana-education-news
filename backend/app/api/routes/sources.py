"""Source registry routes. Fetching articles is a later phase."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.services.source_service import (
    DuplicateSourceError,
    InvalidSourceError,
    SourceInUseError,
    SourceNotFoundError,
    create_source,
    delete_source,
    get_source,
    list_sources,
    update_source,
)

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[SourceRead])
def read_sources(active: bool | None = None, session: Session = Depends(get_db)) -> list[SourceRead]:
    return [SourceRead.model_validate(source) for source in list_sources(session, active=active)]


@router.post("", response_model=SourceRead, status_code=201)
def add_source(data: SourceCreate, session: Session = Depends(get_db)) -> SourceRead:
    try:
        source = create_source(session, data)
    except DuplicateSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from None
    except InvalidSourceError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return SourceRead.model_validate(source)


@router.get("/{source_id}", response_model=SourceRead)
def read_source(source_id: int, session: Session = Depends(get_db)) -> SourceRead:
    try:
        source = get_source(session, source_id)
    except SourceNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found") from None
    return SourceRead.model_validate(source)


@router.patch("/{source_id}", response_model=SourceRead)
def patch_source(
    source_id: int,
    data: SourceUpdate,
    session: Session = Depends(get_db),
) -> SourceRead:
    try:
        source = update_source(session, source_id, data)
    except SourceNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found") from None
    except DuplicateSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from None
    except InvalidSourceError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return SourceRead.model_validate(source)


@router.delete("/{source_id}", status_code=204)
def remove_source(source_id: int, session: Session = Depends(get_db)) -> Response:
    try:
        delete_source(session, source_id)
    except SourceNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found") from None
    except SourceInUseError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from None
    return Response(status_code=204)
