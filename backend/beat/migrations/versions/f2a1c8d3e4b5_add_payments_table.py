"""Add payments table

Revision ID: f2a1c8d3e4b5
Revises: b3e7f1a92c40
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'f2a1c8d3e4b5'
down_revision: Union[str, Sequence[str], None] = 'e5f7a9b3c2d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('beat_id', UUID(as_uuid=True), sa.ForeignKey('beats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('buyer_id', UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_payments_beat_id', 'payments', ['beat_id'])
    op.create_index('ix_payments_buyer_id', 'payments', ['buyer_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])


def downgrade() -> None:
    op.drop_index('ix_payments_status', 'payments')
    op.drop_index('ix_payments_buyer_id', 'payments')
    op.drop_index('ix_payments_beat_id', 'payments')
    op.drop_table('payments')