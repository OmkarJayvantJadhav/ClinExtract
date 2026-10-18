"""Store the report's own reference range and abnormal flag per extracted result

Revision ID: c4d81a7e9b02
Revises: b7e4f19c2a51
Create Date: 2026-10-18 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d81a7e9b02'
down_revision: Union[str, None] = 'b7e4f19c2a51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('extracted_fields', sa.Column('reference_range', sa.String(), nullable=True))
    op.add_column('extracted_fields', sa.Column('abnormal_flag', sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column('extracted_fields', 'abnormal_flag')
    op.drop_column('extracted_fields', 'reference_range')
