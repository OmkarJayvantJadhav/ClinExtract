"""Add extracted_fields.unit and align extraction version columns with the model

Revision ID: a3c9d2e41f70
Revises: 7e17279d29e6
Create Date: 2026-10-06 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3c9d2e41f70'
down_revision: Union[str, None] = '7e17279d29e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('extracted_fields', sa.Column('unit', sa.String(), nullable=True))
    # The ORM model declares these nullable; the initial migration made them NOT NULL.
    op.alter_column('extractions', 'model_version', existing_type=sa.String(), nullable=True)
    op.alter_column('extractions', 'prompt_version', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE extractions SET prompt_version = 'unknown' WHERE prompt_version IS NULL")
    op.execute("UPDATE extractions SET model_version = 'unknown' WHERE model_version IS NULL")
    op.alter_column('extractions', 'prompt_version', existing_type=sa.String(), nullable=False)
    op.alter_column('extractions', 'model_version', existing_type=sa.String(), nullable=False)
    op.drop_column('extracted_fields', 'unit')
