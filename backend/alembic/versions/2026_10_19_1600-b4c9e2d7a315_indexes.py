"""Indexes for the audit log and the foreign keys queried on every document view

Revision ID: b4c9e2d7a315
Revises: a8d3e5f61c27
Create Date: 2026-10-19 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4c9e2d7a315'
down_revision: Union[str, None] = 'a8d3e5f61c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_logs_user_id_created_at', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index(op.f('ix_extractions_document_id'), 'extractions', ['document_id'])
    op.create_index(op.f('ix_extracted_fields_extraction_id'), 'extracted_fields', ['extraction_id'])
    op.create_index(op.f('ix_field_corrections_extracted_field_id'), 'field_corrections', ['extracted_field_id'])
    op.create_index(op.f('ix_reviews_document_id'), 'reviews', ['document_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_reviews_document_id'), table_name='reviews')
    op.drop_index(op.f('ix_field_corrections_extracted_field_id'), table_name='field_corrections')
    op.drop_index(op.f('ix_extracted_fields_extraction_id'), table_name='extracted_fields')
    op.drop_index(op.f('ix_extractions_document_id'), table_name='extractions')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource', table_name='audit_logs')
