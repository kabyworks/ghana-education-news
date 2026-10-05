"""Mark whether a source covers Ghana.

Revision ID: 0005_covers_ghana
Revises: 0004_relevance
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_covers_ghana"
down_revision = "0004_relevance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("covers_ghana", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("sources", "covers_ghana")
