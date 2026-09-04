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

# Three ways an existing row can violate NEW_SCOPE_OWNER_CHECK without a value this
# migration can supply. Each predicate is a module-level literal, never user input.
UNREPAIRABLE_SCOPES = (
    (
        "AGENT",
        "scope = 'AGENT' AND agent_id IS NULL",
        (
            "A memory row scoped AGENT with no agent_id has no owner: in_scope_clause compares "
            "agent_id to the caller's id and a NULL never matches, so nothing can retrieve it. "
            "The old constraint compared lowercase scope names against uppercase stored values, "
            "so it accepted the row."
        ),
    ),
    (
        "TASK",
        "scope = 'TASK' AND task_id IS NULL",
        (
            "A memory row scoped TASK with no task_id has no owner, for the same reason as an "
            "ownerless AGENT row."
        ),
    ),
    (
        "TEAM",
        "scope = 'TEAM'",
        (
            "This revision is what introduces team_id and TEAM as a real, owned scope. A row "
            "already scoped TEAM predates both, so its team cannot be recovered from the row."
        ),
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    refuse_unrepairable_rows(bind)
    repair_stray_workspace_agent_id(bind)

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


def refuse_unrepairable_rows(bind: sa.engine.Connection) -> None:
    """Runs before any DDL: abort loudly rather than let batch_alter_table raise a bare IntegrityError."""
    for label, predicate, explanation in UNREPAIRABLE_SCOPES:
        query = f"SELECT id, scope, agent_id, task_id, content FROM memory_records WHERE {predicate}"
        count = bind.execute(sa.text(f"SELECT count(*) FROM memory_records WHERE {predicate}")).scalar()
        if count:
            raise RuntimeError(
                f"refusing to correct ck_memory_records_scope_owner: {count} row(s) violate it ({label}).\n"
                f"{explanation}\n"
                "Their owner cannot be recovered from the row. Do NOT relax the constraint: decide per "
                "row whether to re-scope or delete it, then re-run.\n"
                f"Query: {query}"
            )


# Repairs the one violation that IS provable from the row: promote_memory_to_workspace
# (memory_service.py) already nulls agent_id when it moves a record to WORKSPACE scope,
# so NULL is the shape the app itself produces here. It can only narrow: in_scope_clause
# already serves this row to every agent on the scope == WORKSPACE clause alone, with or
# without the stray agent_id, so retrieval and listing are unaffected. It changes what
# same_owner() (memory_consolidation_service.py) sees, though: two WORKSPACE rows that
# differ only by this stray agent_id could not be paired into a consolidation proposal
# before, and can be after -- a correctness gain, since both rows were always workspace
# rows, and a proposal is only ever a suggestion a human applies. It is a no-op on a
# database written entirely through the service layer.
def repair_stray_workspace_agent_id(bind: sa.engine.Connection) -> None:
    bind.execute(sa.text("UPDATE memory_records SET agent_id = NULL WHERE scope = 'WORKSPACE' AND agent_id IS NOT NULL"))


def downgrade() -> None:
    # A downgraded MemoryScope enum has no TEAM member, so any TEAM row must stop being one before the
    # column disappears. Deleted, not re-scoped to WORKSPACE: a team's memory is private to its members,
    # and re-scoping would inject it into every agent's context instead.
    op.execute("DELETE FROM memory_records WHERE scope = 'TEAM'")

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
