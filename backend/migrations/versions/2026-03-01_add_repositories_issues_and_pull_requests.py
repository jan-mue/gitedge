"""Add repositories, issues and pull requests

Revision ID: 7f8c9a0b1d2e
Revises: 7bb9cfa0c73d
Create Date: 2026-03-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f8c9a0b1d2e"
down_revision: str | None = "7bb9cfa0c73d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repository",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("stars_count", sa.Integer(), nullable=False),
        sa.Column("forks_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], name=op.f("repository_owner_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("repository_pkey")),
    )
    op.create_index(op.f("repository_owner_id_idx"), "repository", ["owner_id"], unique=False)
    op.create_index(op.f("repository_path_idx"), "repository", ["path"], unique=True)

    op.create_table(
        "issue",
        sa.Column("repo_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("author_email", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="issue"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["repo_id"], ["repository.id"], name=op.f("issue_repo_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("issue_pkey")),
        sa.UniqueConstraint("repo_id", "number", name="issue_repo_number_key"),
    )
    op.create_index(op.f("issue_repo_id_idx"), "issue", ["repo_id"], unique=False)

    op.create_table(
        "pull_request",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("head_repo_id", sa.UUID(), nullable=False),
        sa.Column("base_repo_id", sa.UUID(), nullable=False),
        sa.Column("head_branch", sa.String(length=255), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False, server_default="main"),
        sa.Column("merge_base", sa.String(length=40), nullable=True),
        sa.Column("merged_commit_id", sa.String(length=40), nullable=True),
        sa.Column("has_merged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("merger_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["issue.id"], name=op.f("pull_request_id_fkey")),
        sa.ForeignKeyConstraint(["head_repo_id"], ["repository.id"], name=op.f("pull_request_head_repo_id_fkey")),
        sa.ForeignKeyConstraint(["base_repo_id"], ["repository.id"], name=op.f("pull_request_base_repo_id_fkey")),
        sa.ForeignKeyConstraint(["merger_id"], ["user.id"], name=op.f("pull_request_merger_id_fkey")),
        sa.PrimaryKeyConstraint("id", name=op.f("pull_request_pkey")),
    )


def downgrade() -> None:
    op.drop_table("pull_request")
    op.drop_index(op.f("issue_repo_id_idx"), table_name="issue")
    op.drop_table("issue")
    op.drop_index(op.f("repository_path_idx"), table_name="repository")
    op.drop_index(op.f("repository_owner_id_idx"), table_name="repository")
    op.drop_table("repository")
