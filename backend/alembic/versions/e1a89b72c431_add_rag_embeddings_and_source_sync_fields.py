"""add embedding to chunks and sync metadata to documents and sources

Revision ID: e1a89b72c431
Revises: d93812ca7b6a
Create Date: 2026-10-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "e1a89b72c431"
down_revision: Union[str, Sequence[str], None] = "d93812ca7b6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SchemeDocumentChunk: embedding JSON vector
    op.add_column("scheme_document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))

    # SchemeDocument: status, error_message, metadata_json, document_type, version
    op.add_column(
        "scheme_documents",
        sa.Column("ingestion_status", sa.String(length=30), nullable=False, server_default="completed")
    )
    op.add_column("scheme_documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("scheme_documents", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.add_column(
        "scheme_documents",
        sa.Column("document_type", sa.String(length=50), nullable=True, server_default="official_document")
    )
    op.add_column(
        "scheme_documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )

    # SchemeSource: sync_interval_hours, status, error_details
    op.add_column(
        "scheme_sources",
        sa.Column("sync_interval_hours", sa.Integer(), nullable=False, server_default="24")
    )
    op.add_column(
        "scheme_sources",
        sa.Column("status", sa.String(length=30), nullable=False, server_default="healthy")
    )
    op.add_column("scheme_sources", sa.Column("error_details", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scheme_sources", "error_details")
    op.drop_column("scheme_sources", "status")
    op.drop_column("scheme_sources", "sync_interval_hours")

    op.drop_column("scheme_documents", "version")
    op.drop_column("scheme_documents", "document_type")
    op.drop_column("scheme_documents", "metadata_json")
    op.drop_column("scheme_documents", "error_message")
    op.drop_column("scheme_documents", "ingestion_status")

    op.drop_column("scheme_document_chunks", "embedding")
