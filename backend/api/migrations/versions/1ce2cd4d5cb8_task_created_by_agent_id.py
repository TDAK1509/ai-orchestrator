"""task created by agent id

Revision ID: 1ce2cd4d5cb8
Revises: a3cec77c5260
Create Date: 2026-09-05 00:00:03.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models.base

revision: str = '1ce2cd4d5cb8'
down_revision: str | None = 'a3cec77c5260'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('created_by_agent_id', models.base.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_tasks_created_by_agent_id', 'agents', ['created_by_agent_id'], ['id'])
        batch_op.create_index('ix_tasks_created_by_agent_id', ['created_by_agent_id'])


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_index('ix_tasks_created_by_agent_id')
        batch_op.drop_constraint('fk_tasks_created_by_agent_id', type_='foreignkey')
        batch_op.drop_column('created_by_agent_id')
