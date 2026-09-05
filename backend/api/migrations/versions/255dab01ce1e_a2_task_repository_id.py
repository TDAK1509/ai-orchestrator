"""a2 task repository id

Revision ID: 255dab01ce1e
Revises: 3c352092b9cb
Create Date: 2026-09-05 00:00:01.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models.base

revision: str = '255dab01ce1e'
down_revision: str | None = '3c352092b9cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('repository_id', models.base.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_tasks_repository_id', 'repositories', ['repository_id'], ['id'])
        batch_op.create_index('ix_tasks_repository_id', ['repository_id'])


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_index('ix_tasks_repository_id')
        batch_op.drop_constraint('fk_tasks_repository_id', type_='foreignkey')
        batch_op.drop_column('repository_id')
