"""Add relevance scores and the stored decision.

Revision ID: 0004_relevance
Revises: 0003_articles
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_relevance"
down_revision = "0003_articles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("ghana_relevance", sa.Float(), nullable=True))
    op.add_column("articles", sa.Column("education_relevance", sa.Float(), nullable=True))
    op.add_column("articles", sa.Column("relevance_decision", sa.String(length=16), nullable=True))
    op.add_column("articles", sa.Column("relevance_reason", sa.Text(), nullable=True))
    op.create_index("ix_articles_relevance_decision", "articles", ["relevance_decision"])


def downgrade() -> None:
    op.drop_index("ix_articles_relevance_decision", table_name="articles")
    op.drop_column("articles", "relevance_reason")
    op.drop_column("articles", "relevance_decision")
    op.drop_column("articles", "education_relevance")
    op.drop_column("articles", "ghana_relevance")
