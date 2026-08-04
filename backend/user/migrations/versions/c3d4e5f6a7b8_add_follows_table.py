"""Add follows table

Revision ID: c3d4e5f6a7b8
Revises: 45ef93894ef5
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '45ef93894ef5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'follows',
        sa.Column('follower_id', sa.UUID(as_uuid=True), sa.ForeignKey('profiles.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('following_id', sa.UUID(as_uuid=True), sa.ForeignKey('profiles.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_follows_following_id', 'follows', ['following_id'])


def downgrade() -> None:
    op.drop_index('ix_follows_following_id', table_name='follows')
    op.drop_table('follows')
