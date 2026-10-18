"""login_attempts table for a rate limit shared by all API processes

Revision ID: e5b20a4c7d13
Revises: d91f3b6c2e48
Create Date: 2026-10-18 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5b20a4c7d13'
down_revision: Union[str, None] = 'd91f3b6c2e48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_key', sa.String(length=64), nullable=False),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_login_attempts_client_key_attempted_at', 'login_attempts', ['client_key', 'attempted_at'])


def downgrade() -> None:
    op.drop_index('ix_login_attempts_client_key_attempted_at', table_name='login_attempts')
    op.drop_table('login_attempts')
