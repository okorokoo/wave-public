"""Add cover_url to beats

Revision ID: d4f6a8b2c1e9
Revises: b3e7f1a92c40
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f6a8b2c1e9'
down_revision: Union[str, Sequence[str], None] = 'b3e7f1a92c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('beats', sa.Column('cover_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('beats', 'cover_url')
