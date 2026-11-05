"""Merge RBAC and notification migrations

Revision ID: c5fae2fb7d47
Revises: e7a5424061d3, c45f8528cc79
Create Date: 2026-11-05 00:20:00.986741

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c5fae2fb7d47"
down_revision: str | Sequence[str] | None = ("e7a5424061d3", "c45f8528cc79")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
