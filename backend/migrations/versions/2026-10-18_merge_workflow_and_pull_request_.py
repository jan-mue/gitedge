"""merge workflow and pull request migrations

Revision ID: ba580225e122
Revises: ab72b7495533, c1e7092e3487
Create Date: 2026-10-18 00:15:14.037009

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "ba580225e122"
down_revision: str | Sequence[str] | None = ("ab72b7495533", "c1e7092e3487")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
