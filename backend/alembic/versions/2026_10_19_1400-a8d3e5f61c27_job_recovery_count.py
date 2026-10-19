"""Count how often a job was recovered after its worker died

Revision ID: a8d3e5f61c27
Revises: f2a7c41d9e85
Create Date: 2026-10-19 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a8d3e5f61c27'
down_revision: Union[str, None] = 'f2a7c41d9e85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('processing_jobs', sa.Column('recovery_count', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('processing_jobs', 'recovery_count')
