"""a1 repositories

Revision ID: 3c352092b9cb
Revises: e1a501667f72
Create Date: 2026-09-05 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import models.base

revision: str = '3c352092b9cb'
down_revision: str | None = 'e1a501667f72'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'repositories',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('default_target_branch', sa.String(length=200), nullable=False, server_default='main'),
        sa.Column('default_working_dir', sa.String(length=500), nullable=True),
        sa.Column('setup_script', sa.String(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', models.base.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('path'),
    )


def downgrade() -> None:
    op.drop_table('repositories')
