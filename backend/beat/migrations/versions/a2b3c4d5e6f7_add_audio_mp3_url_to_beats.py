"""Add audio_mp3_url to beats

Revision ID: a2b3c4d5e6f7
Revises: c9d8e7f6a5b4
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('beats', sa.Column('audio_mp3_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('beats', 'audio_mp3_url')
