"""Add user_voice_tags table

Revision ID: c9d8e7f6a5b4
Revises: f2a1c8d3e4b5
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, Sequence[str], None] = 'f2a1c8d3e4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_voice_tags',
        sa.Column('user_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('s3_key', sa.String(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_voice_tags')
