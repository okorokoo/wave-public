"""add username to auth_users

Revision ID: b1c2d3e4f5a6
Revises: ca114a0210ba
Create Date: 2026-08-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a7c3e1f9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable first, backfill from email, then set NOT NULL + unique
    op.add_column('auth_users', sa.Column('username', sa.String(length=30), nullable=True))
    op.execute("UPDATE auth_users SET username = split_part(email, '@', 1) WHERE username IS NULL")
    op.alter_column('auth_users', 'username', nullable=False)
    op.create_index(op.f('ix_auth_users_username'), 'auth_users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_auth_users_username'), table_name='auth_users')
    op.drop_column('auth_users', 'username')
