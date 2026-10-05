"""Local review desk for this PC."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.review import ReviewArticleRead, ReviewStoryRead, StoryEdit
from app.services.article_service import ArticleNotFoundError
from app.services.review_service import (
    InvalidReviewError,
    approve_article,
    edit_story,
    list_queue,
    list_review_stories,
    reject_article,
    set_story_visible,
)
from app.services.story_service import StoryNotFoundError

router = APIRouter(prefix="/review", tags=["review"])
_DESK = Path(__file__).resolve().parents[2] / "review" / "desk.html"


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def review_desk() -> HTMLResponse:
    return HTMLResponse(_DESK.read_text(encoding="utf-8"))


@router.get("/queue", response_model=list[ReviewArticleRead])
def read_queue(session: Session = Depends(get_db)) -> list[ReviewArticleRead]:
    return [
        ReviewArticleRead(
            id=article.id,
            title=article.title,
            source_name=source_name,
            url=article.url,
            excerpt=article.excerpt,
            published_at=article.published_at,
        )
        for article, source_name in list_queue(session)
    ]


@router.get("/stories", response_model=list[ReviewStoryRead])
def read_review_stories(session: Session = Depends(get_db)) -> list[ReviewStoryRead]:
    return [_story_read(story) for story in list_review_stories(session)]


@router.post("/articles/{article_id}/approve", response_model=ReviewArticleRead)
def approve(article_id: int, session: Session = Depends(get_db)) -> ReviewArticleRead:
    try:
        article = approve_article(session, article_id)
    except ArticleNotFoundError:
        raise HTTPException(status_code=404, detail="Article not found") from None
    return _article_read(article, session)


@router.post("/articles/{article_id}/reject", response_model=ReviewArticleRead)
def reject(article_id: int, session: Session = Depends(get_db)) -> ReviewArticleRead:
    try:
        article = reject_article(session, article_id)
    except ArticleNotFoundError:
        raise HTTPException(status_code=404, detail="Article not found") from None
    return _article_read(article, session)


@router.post("/stories/{story_id}/hide", response_model=ReviewStoryRead)
def hide_story(story_id: int, session: Session = Depends(get_db)) -> ReviewStoryRead:
    return _visibility(story_id, visible=False, session=session)


@router.post("/stories/{story_id}/show", response_model=ReviewStoryRead)
def show_story(story_id: int, session: Session = Depends(get_db)) -> ReviewStoryRead:
    return _visibility(story_id, visible=True, session=session)


@router.patch("/stories/{story_id}", response_model=ReviewStoryRead)
def patch_story(story_id: int, data: StoryEdit, session: Session = Depends(get_db)) -> ReviewStoryRead:
    try:
        story = edit_story(session, story_id, title=data.title, summary=data.summary)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Story not found") from None
    except InvalidReviewError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return _story_read(story)


def _visibility(story_id: int, *, visible: bool, session: Session) -> ReviewStoryRead:
    try:
        story = set_story_visible(session, story_id, visible=visible)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Story not found") from None
    return _story_read(story)


def _article_read(article, session: Session) -> ReviewArticleRead:
    from app.db.models.source import Source

    source = session.get(Source, article.source_id)
    return ReviewArticleRead(
        id=article.id,
        title=article.title,
        source_name=source.name if source is not None else "",
        url=article.url,
        excerpt=article.excerpt,
        published_at=article.published_at,
    )


def _story_read(story) -> ReviewStoryRead:
    return ReviewStoryRead(
        id=story.id,
        title=story.editor_title or story.title,
        generated_title=story.title,
        summary=story.editor_summary or story.summary,
        generated_summary=story.summary,
        category=story.category,
        article_count=story.article_count,
        reader_visible=story.reader_visible,
        title_edited=story.editor_title is not None,
        summary_edited=story.editor_summary is not None,
    )
