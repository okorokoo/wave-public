"""Add author_name to beats

Revision ID: f3a4b5c6d7e8
Revises: e4f5a6b7c8d9
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'beats',
        sa.Column('author_name', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('beats', 'author_name')
