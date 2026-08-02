"""Add is_deleted to beats

Revision ID: d1e2f3a4b5c6
Revises: c9d8e7f6a5b4
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'beats',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_beats_is_deleted', 'beats', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('ix_beats_is_deleted', 'beats')
    op.drop_column('beats', 'is_deleted')