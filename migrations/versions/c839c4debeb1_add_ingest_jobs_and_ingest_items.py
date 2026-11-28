
"""No-op migration after the ingest jobs migration.

Revision ID: c839c4debeb1
Revises: 6029561ecd2d
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "c839c4debeb1"
down_revision: Union[str, Sequence[str], None] = "6029561ecd2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema changes are required."""
    pass


def downgrade() -> None:
    """No schema changes are required."""
    pass
