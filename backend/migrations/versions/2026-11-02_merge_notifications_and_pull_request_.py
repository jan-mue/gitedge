"""merge notifications and pull request reviews

Revision ID: 29f14f00606f
Revises: da70b2e6a25d, c1e7092e3487
Create Date: 2026-11-02 20:44:10.448048

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "29f14f00606f"
down_revision: str | tuple[str, ...] | None = ("da70b2e6a25d", "c1e7092e3487")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
