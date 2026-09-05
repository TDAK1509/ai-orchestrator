"""agent model and effort

Revision ID: e1a501667f72
Revises: e2bebf0a23bb
Create Date: 2026-09-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e1a501667f72'
down_revision: str | None = 'e2bebf0a23bb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('agents') as batch_op:
        batch_op.add_column(sa.Column('model', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('effort', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'XHIGH', 'MAX', name='agenteffort', native_enum=False, length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('agents') as batch_op:
        batch_op.drop_column('effort')
        batch_op.drop_column('model')
