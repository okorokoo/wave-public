"""Add beat_likes table

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'beat_likes',
        sa.Column('beat_id', sa.UUID(as_uuid=True), sa.ForeignKey('beats.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_beat_likes_user_id', 'beat_likes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_beat_likes_user_id', table_name='beat_likes')
    op.drop_table('beat_likes')
