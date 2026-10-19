"""Units on field corrections, so a reviewer can correct a result's unit

Revision ID: f2a7c41d9e85
Revises: e5b20a4c7d13
Create Date: 2026-10-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a7c41d9e85'
down_revision: Union[str, None] = 'e5b20a4c7d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('field_corrections', sa.Column('previous_unit', sa.String(), nullable=True))
    op.add_column('field_corrections', sa.Column('new_unit', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('field_corrections', 'new_unit')
    op.drop_column('field_corrections', 'previous_unit')
