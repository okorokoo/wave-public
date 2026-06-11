"""Add email_verifications table

Revision ID: c5d8e2f3a1b4
Revises: ca114a0210ba
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'c5d8e2f3a1b4'
down_revision: Union[str, Sequence[str], None] = 'ca114a0210ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_verifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('auth_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_verifications_token', 'email_verifications', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_email_verifications_token', 'email_verifications')
    op.drop_table('email_verifications')
