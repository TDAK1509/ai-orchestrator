"""repository remote target branch

Revision ID: fee38d669fe8
Revises: 1ce2cd4d5cb8
Create Date: 2026-09-05 15:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'fee38d669fe8'
down_revision: str | None = '1ce2cd4d5cb8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """PR 1: every existing repository's default_target_branch was a plain local branch name (e.g. "main") -- prefix it with "origin/" to match the new remote-ref convention. A repository with no actual origin remote still resolves correctly at runtime: resolve_worktree_base falls back to the local branch of the same name when the remote doesn't exist."""
    op.execute(sa.text("UPDATE repositories SET default_target_branch = 'origin/' || default_target_branch WHERE default_target_branch NOT LIKE '%/%'"))


def downgrade() -> None:
    raise RuntimeError(
        "no downgrade: stripping 'origin/' from every matching row would also strip it from a row that "
        "already had that prefix before this migration ran, which the upgrade never touched and this "
        "migration has no record of distinguishing"
    )
