"""Add beat_tags table

Revision ID: e5f7a9b3c2d1
Revises: d4f6a8b2c1e9
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5f7a9b3c2d1'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8b2c1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'beat_tags',
        sa.Column('beat_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('beats.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('tag', sa.String(50), primary_key=True),
    )
    op.create_index('ix_beat_tags_beat_id', 'beat_tags', ['beat_id'])
    op.create_index('ix_beat_tags_tag', 'beat_tags', ['tag'])


def downgrade() -> None:
    op.drop_index('ix_beat_tags_tag', table_name='beat_tags')
    op.drop_index('ix_beat_tags_beat_id', table_name='beat_tags')
    op.drop_table('beat_tags')
