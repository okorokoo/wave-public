"""Add purchases table

Revision ID: b3e7f1a92c40
Revises: 0321f64929d0
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'b3e7f1a92c40'
down_revision: Union[str, Sequence[str], None] = '0321f64929d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'purchases',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('beat_id', UUID(as_uuid=True), sa.ForeignKey('beats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('buyer_id', UUID(as_uuid=True), nullable=False),
        sa.Column('license_type', sa.String(), nullable=False, server_default='basic'),
        sa.Column('purchased_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_purchases_beat_id', 'purchases', ['beat_id'])
    op.create_index('ix_purchases_buyer_id', 'purchases', ['buyer_id'])
    op.create_unique_constraint('uq_purchases_beat_buyer', 'purchases', ['beat_id', 'buyer_id'])


def downgrade() -> None:
    op.drop_constraint('uq_purchases_beat_buyer', 'purchases', type_='unique')
    op.drop_index('ix_purchases_buyer_id', 'purchases')
    op.drop_index('ix_purchases_beat_id', 'purchases')
    op.drop_table('purchases')
