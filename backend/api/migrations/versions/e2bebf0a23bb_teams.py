"""teams

Revision ID: e2bebf0a23bb
Revises: 322b6e7afb62
Create Date: 2026-09-04 10:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models.base

revision: str = 'e2bebf0a23bb'
down_revision: str | None = '322b6e7afb62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_SCOPE_OWNER_CHECK = (
    "(scope != 'WORKSPACE' OR (agent_id IS NULL AND team_id IS NULL)) "
    "AND (scope != 'AGENT' OR (agent_id IS NOT NULL AND team_id IS NULL)) "
    "AND (scope != 'TEAM' OR (team_id IS NOT NULL AND agent_id IS NULL AND task_id IS NULL)) "
    "AND (scope != 'TASK' OR task_id IS NOT NULL)"
)
OLD_SCOPE_OWNER_CHECK = (
    "(scope != 'workspace' OR agent_id IS NULL) "
    "AND (scope != 'agent' OR agent_id IS NOT NULL) "
    "AND (scope != 'task' OR task_id IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table('teams',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('id', models.base.GUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('agents') as batch_op:
        batch_op.add_column(sa.Column('team_id', models.base.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_agents_team_id', 'teams', ['team_id'], ['id'])
        batch_op.create_index('ix_agents_team_id', ['team_id'])

    with op.batch_alter_table('memory_records') as batch_op:
        batch_op.add_column(sa.Column('team_id', models.base.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_memory_records_team_id', 'teams', ['team_id'], ['id'])
        batch_op.create_index('ix_memory_records_team_scope', ['team_id', 'scope', 'status'])
        batch_op.drop_constraint('ck_memory_records_scope_owner', type_='check')
        batch_op.create_check_constraint('ck_memory_records_scope_owner', NEW_SCOPE_OWNER_CHECK)


def downgrade() -> None:
    # A downgraded MemoryScope enum has no TEAM member, so any TEAM row must stop being one before the
    # column disappears: re-scope it to WORKSPACE (team_id already becomes NULL below) rather than delete it.
    op.execute("UPDATE memory_records SET scope = 'WORKSPACE' WHERE scope = 'TEAM'")

    with op.batch_alter_table('memory_records') as batch_op:
        batch_op.drop_constraint('ck_memory_records_scope_owner', type_='check')
        batch_op.create_check_constraint('ck_memory_records_scope_owner', OLD_SCOPE_OWNER_CHECK)
        batch_op.drop_index('ix_memory_records_team_scope')
        batch_op.drop_constraint('fk_memory_records_team_id', type_='foreignkey')
        batch_op.drop_column('team_id')

    with op.batch_alter_table('agents') as batch_op:
        batch_op.drop_index('ix_agents_team_id')
        batch_op.drop_constraint('fk_agents_team_id', type_='foreignkey')
        batch_op.drop_column('team_id')

    op.drop_table('teams')
