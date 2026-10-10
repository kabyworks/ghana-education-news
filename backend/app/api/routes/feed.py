"""Reader feed. Ranking and search run on stored stories, not on full articles."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.intelligence.stories.categories import CATEGORY_NAMES
from app.schemas.feed import FeedArticleRead, FeedCategoryRead, FeedDetailRead, FeedStoryRead
from app.services.feed_service import (
    FeedStory,
    get_feed_story,
    list_categories,
    list_feed,
    search_feed,
    search_terms,
    story_image,
)
from app.services.story_service import StoryNotFoundError

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=list[FeedStoryRead])
def read_feed(
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
) -> list[FeedStoryRead]:
    _check_category(category)
    return [_story_read(story) for story in list_feed(session, category=category, limit=limit, offset=offset)]


@router.get("/categories", response_model=list[FeedCategoryRead])
def read_categories(session: Session = Depends(get_db)) -> list[FeedCategoryRead]:
    return [FeedCategoryRead(name=item.name, story_count=item.story_count) for item in list_categories(session)]


@router.get("/search", response_model=list[FeedStoryRead])
def read_search(
    q: str = Query(min_length=1, max_length=100),
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_db),
) -> list[FeedStoryRead]:
    _check_category(category)
    terms = search_terms(q)
    if not terms:
        raise HTTPException(status_code=422, detail="q must contain at least one word of 2 characters")
    return [_story_read(story) for story in search_feed(session, query=q, category=category, limit=limit)]


@router.get("/{story_id}", response_model=FeedDetailRead)
def read_feed_story(story_id: int, session: Session = Depends(get_db)) -> FeedDetailRead:
    try:
        story = get_feed_story(session, story_id)
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail="Story not found") from None
    listed = _story_read(story)
    return FeedDetailRead(
        **listed.model_dump(),
        articles=[
            FeedArticleRead(
                source_name=source_name,
                title=article.title,
                url=article.url,
                published_at=article.published_at,
                excerpt=article.excerpt,
            )
            for article, source_name in story.articles
        ],
    )


def _check_category(category: str | None) -> None:
    if category is not None and category not in CATEGORY_NAMES:
        allowed = ", ".join(sorted(CATEGORY_NAMES))
        raise HTTPException(status_code=422, detail=f"category must be one of: {allowed}")


def _story_read(story: FeedStory) -> FeedStoryRead:
    return FeedStoryRead(
        id=story.id,
        title=story.title,
        summary=story.summary,
        category=story.category,
        published_at=story.published_at,
        source_count=story.source_count,
        sources=story.sources,
        image_url=story_image(story.articles),
        rank=story.rank,
    )
