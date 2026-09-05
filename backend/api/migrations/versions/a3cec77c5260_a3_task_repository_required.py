"""a3 task repository required

Revision ID: a3cec77c5260
Revises: 7ff9924cdb8d
Create Date: 2026-09-05 00:00:02.000000

"""
import os
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

import models.base

revision: str = 'a3cec77c5260'
down_revision: str | None = '7ff9924cdb8d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPOSITORIES = sa.table(
    'repositories',
    sa.column('id', models.base.GUID()),
    sa.column('name', sa.String()),
    sa.column('path', sa.String()),
    sa.column('default_target_branch', sa.String()),
    sa.column('active', sa.Boolean()),
    sa.column('created_at', sa.DateTime(timezone=True)),
)
TASKS = sa.table('tasks', sa.column('repository_id', models.base.GUID()))


def upgrade() -> None:
    bind = op.get_bind()
    backfill_null_repository_ids(bind)
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('repository_id', existing_type=models.base.GUID(), nullable=False)


def backfill_null_repository_ids(bind) -> None:
    """PR 4: every task created before this migration has repository_id NULL -- backfill them all to one repository row cut from AGENT_OFFICE_REPO_ROOT, the fallback they were already using. Skipped entirely when there is nothing to backfill, so an install with no legacy tasks never has to seed a row (or collide with one) it doesn't need."""
    if not has_null_repository_tasks(bind):
        return
    repository_id = find_or_seed_repository_id(bind)
    bind.execute(TASKS.update().where(TASKS.c.repository_id.is_(None)).values(repository_id=repository_id))


def has_null_repository_tasks(bind) -> bool:
    return bind.execute(sa.select(TASKS.c.repository_id).where(TASKS.c.repository_id.is_(None)).limit(1)).first() is not None


def find_or_seed_repository_id(bind) -> uuid.UUID:
    path = str(Path(os.environ.get("AGENT_OFFICE_REPO_ROOT", ".")).resolve())
    existing = bind.execute(sa.select(REPOSITORIES.c.id).where(REPOSITORIES.c.path == path)).first()
    if existing is not None:
        return existing.id
    return insert_seed_repository(bind, path)


def insert_seed_repository(bind, path: str) -> uuid.UUID:
    repository_id = uuid.uuid4()
    bind.execute(REPOSITORIES.insert().values(
        id=repository_id, name=find_available_repository_name(bind, Path(path).name or "default"), path=path,
        default_target_branch="main", active=True, created_at=sa.func.now(),
    ))
    return repository_id


def find_available_repository_name(bind, candidate: str) -> str:
    """`repositories.name` is unique -- a second repository whose directory happens to share a basename with this one must not fail the whole migration."""
    taken = {row.name for row in bind.execute(sa.select(REPOSITORIES.c.name))}
    if candidate not in taken:
        return candidate
    suffix = uuid.uuid4().hex[:8]
    return f"{candidate}-{suffix}"


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('repository_id', existing_type=models.base.GUID(), nullable=True)
