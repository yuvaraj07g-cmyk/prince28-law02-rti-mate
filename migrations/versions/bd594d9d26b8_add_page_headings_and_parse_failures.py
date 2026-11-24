"""Add page headings and parse failures.

Revision ID: bd594d9d26b8
Revises: 002
Create Date: 2026-11-24 14:06:30.880184

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bd594d9d26b8"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "parse_failures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), server_default="", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parse_failures")),
        sa.UniqueConstraint("path", name=op.f("uq_parse_failures_path")),
    )
    op.create_index(op.f("ix_parse_failures_reason"), "parse_failures", ["reason"], unique=False)

    op.add_column(
        "pages",
        sa.Column(
            "headings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pages", "headings")
    op.drop_index(op.f("ix_parse_failures_reason"), table_name="parse_failures")
    op.drop_table("parse_failures")
