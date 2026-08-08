"""Add missing indexes for purchases

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ускоряет get_by_buyer — сортировка по purchased_at без filesort
    op.create_index(
        'ix_purchases_buyer_purchased',
        'purchases',
        ['buyer_id', 'purchased_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_purchases_buyer_purchased', table_name='purchases')
