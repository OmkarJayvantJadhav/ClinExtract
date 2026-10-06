"""Auth hardening columns on users and the system_settings table

Revision ID: b7e4f19c2a51
Revises: a3c9d2e41f70
Create Date: 2026-10-06 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e4f19c2a51'
down_revision: Union[str, None] = 'a3c9d2e41f70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('failed_login_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('system_settings')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'token_version')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_count')
