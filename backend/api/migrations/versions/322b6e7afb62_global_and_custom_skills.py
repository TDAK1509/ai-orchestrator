"""global and custom skills

Revision ID: 322b6e7afb62
Revises: b8e1003773eb
Create Date: 2026-09-04 06:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '322b6e7afb62'
down_revision: str | None = 'b8e1003773eb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('skills') as batch_op:
        batch_op.add_column(sa.Column('source', sa.Enum('GLOBAL', 'CUSTOM', name='skillsource', native_enum=False, length=10), server_default=sa.text("'CUSTOM'"), nullable=False))
        batch_op.add_column(sa.Column('instructions', sa.String(), nullable=True))
        batch_op.alter_column('repository_path', existing_type=sa.String(length=500), nullable=True)

    op.execute("UPDATE skills SET repository_path = NULL")


def downgrade() -> None:
    op.execute("UPDATE skills SET repository_path = '' WHERE repository_path IS NULL")

    with op.batch_alter_table('skills') as batch_op:
        batch_op.alter_column('repository_path', existing_type=sa.String(length=500), nullable=False)
        batch_op.drop_column('instructions')
        batch_op.drop_column('source')
