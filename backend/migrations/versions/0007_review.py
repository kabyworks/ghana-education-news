"""Let a local reviewer hide a story and keep a title or summary edit.

Revision ID: 0007_review
Revises: 0006_stories
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_review"
down_revision = "0006_stories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column("reader_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("stories", sa.Column("editor_title", sa.String(length=500), nullable=True))
    op.add_column("stories", sa.Column("editor_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "editor_summary")
    op.drop_column("stories", "editor_title")
    op.drop_column("stories", "reader_visible")
