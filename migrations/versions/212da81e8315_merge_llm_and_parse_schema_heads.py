"""Merge LLM and parse schema heads.

Revision ID: 212da81e8315
Revises: a6e9582e19f6, bd594d9d26b8
Create Date: 2026-11-25 21:58:12.858829

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "212da81e8315"
down_revision: Union[str, Sequence[str], None] = ("a6e9582e19f6", "bd594d9d26b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge the LLM and parse schema branches."""
    pass


def downgrade() -> None:
    """Unmerge the schema branches."""
    pass
