"""Group articles about the same event into stories.

Revision ID: 0006_stories
Revises: 0005_covers_ghana
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_stories"
down_revision = "0005_covers_ghana"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("article_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stories_category", "stories", ["category"])
    with op.batch_alter_table("articles") as batch:
        batch.add_column(sa.Column("story_id", sa.Integer(), nullable=True))
        batch.create_index("ix_articles_story_id", ["story_id"])
        batch.create_foreign_key("fk_articles_story_id", "stories", ["story_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("articles") as batch:
        batch.drop_constraint("fk_articles_story_id", type_="foreignkey")
        batch.drop_index("ix_articles_story_id")
        batch.drop_column("story_id")
    op.drop_index("ix_stories_category", table_name="stories")
    op.drop_table("stories")
