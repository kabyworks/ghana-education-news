"""Grouped stories built from published articles."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.intelligence.stories.categories import CATEGORY_NAMES
from app.intelligence.stories.service import build_stories
from app.schemas.story import StoryArticleRead, StoryBuildRead, StoryDetailRead, StoryRead
from app.services.story_service import StoryNotFoundError, get_story, list_stories

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("", response_model=list[StoryRead])
def read_stories(
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> list[StoryRead]:
    if category is not None and category not in CATEGORY_NAMES:
        allowed = ", ".join(sorted(CATEGORY_NAMES))
        raise HTTPException(status_code=422, detail=f"category must be one of: {allowed}")
    return [
        StoryRead(
            id=story.id,
            title=story.title,
            summary=story.summary,
            category=story.category,
            article_count=story.article_count,
            first_published_at=story.first_published_at,
        )
        for story in list_stories(session, category=category, limit=limit)
    ]


@router.post("/build", response_model=StoryBuildRead)
def run_story_build(force: bool = False, session: Session = Depends(get_db)) -> StoryBuildRead:
    report = build_stories(session, force=force)
    return StoryBuildRead(
        considered=report.considered,
        created=report.created,
        attached=report.attached,
        stories=report.stories,
    )


@router.get("/{story_id}", response_model=StoryDetailRead)
def read_story(story_id: int, session: Session = Depends(get_db)) -> StoryDetailRead:
    try:
        story, articles = get_story(session, story_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Story not found") from None
    return StoryDetailRead(
        id=story.id,
        title=story.title,
        summary=story.summary,
        category=story.category,
        article_count=story.article_count,
        first_published_at=story.first_published_at,
        articles=[
            StoryArticleRead(
                id=article.id,
                source_name=source_name,
                title=article.title,
                url=article.url,
                published_at=article.published_at,
                excerpt=article.excerpt,
            )
            for article, source_name in articles
        ],
    )
