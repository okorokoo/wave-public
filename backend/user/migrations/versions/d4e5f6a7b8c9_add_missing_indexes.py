"""Add missing indexes for follows and profiles

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ускоряет _count_following — фильтрация по follower_id без скана
    op.create_index('ix_follows_follower_id', 'follows', ['follower_id'])
    # Ускоряет get_by_username — поиск по lower(username) без полного скана
    op.execute("CREATE INDEX ix_profiles_lower_username ON profiles (lower(username))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_profiles_lower_username")
    op.drop_index('ix_follows_follower_id', table_name='follows')
