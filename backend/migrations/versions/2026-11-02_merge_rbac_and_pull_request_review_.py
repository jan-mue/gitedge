"""Merge RBAC and pull request review migrations

Revision ID: e7a5424061d3
Revises: a84ff2412dbc, c1e7092e3487
Create Date: 2026-11-02 20:49:57.120084

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e7a5424061d3"
down_revision: str | Sequence[str] | None = ("a84ff2412dbc", "c1e7092e3487")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
