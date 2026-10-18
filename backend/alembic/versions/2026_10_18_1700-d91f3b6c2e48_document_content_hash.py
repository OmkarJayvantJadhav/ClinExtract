"""Add documents.content_hash for duplicate upload detection

Revision ID: d91f3b6c2e48
Revises: c4d81a7e9b02
Create Date: 2026-10-18 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd91f3b6c2e48'
down_revision: Union[str, None] = 'c4d81a7e9b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_documents_content_hash', 'documents', ['content_hash'])


def downgrade() -> None:
    op.drop_index('ix_documents_content_hash', table_name='documents')
    op.drop_column('documents', 'content_hash')
