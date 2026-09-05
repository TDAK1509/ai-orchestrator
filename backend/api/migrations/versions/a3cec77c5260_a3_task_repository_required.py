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
    repository_id = find_or_seed_repository_id(bind)
    bind.execute(TASKS.update().where(TASKS.c.repository_id.is_(None)).values(repository_id=repository_id))
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('repository_id', existing_type=models.base.GUID(), nullable=False)


def find_or_seed_repository_id(bind) -> uuid.UUID:
    """PR 4: every task created before this migration has repository_id NULL -- backfill them all to one repository row cut from AGENT_OFFICE_REPO_ROOT, the fallback they were already using."""
    path = str(Path(os.environ.get("AGENT_OFFICE_REPO_ROOT", ".")).resolve())
    existing = bind.execute(sa.select(REPOSITORIES.c.id).where(REPOSITORIES.c.path == path)).first()
    if existing is not None:
        return existing.id
    return insert_seed_repository(bind, path)


def insert_seed_repository(bind, path: str) -> uuid.UUID:
    repository_id = uuid.uuid4()
    bind.execute(REPOSITORIES.insert().values(
        id=repository_id, name=Path(path).name or "default", path=path,
        default_target_branch="main", active=True, created_at=sa.func.now(),
    ))
    return repository_id


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('repository_id', existing_type=models.base.GUID(), nullable=True)
