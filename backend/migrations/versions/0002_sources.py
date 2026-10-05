"""Create the source registry.

Revision ID: 0002_sources
Revises: 0001_baseline
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_sources"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("feed_url", sa.String(length=500), nullable=True, unique=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("crawl_frequency_minutes", sa.Integer(), nullable=False),
        sa.Column("discovery_method", sa.String(length=30), nullable=False),
        sa.Column("parser_key", sa.String(length=50), nullable=False),
        sa.Column("fallback_method", sa.String(length=30), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_active", "sources", ["active"])


def downgrade() -> None:
    op.drop_index("ix_sources_active", table_name="sources")
    op.drop_table("sources")
