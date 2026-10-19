"""add provenance-bearing scheme documents and text chunks"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c35b18d90a42"
down_revision: Union[str, Sequence[str], None] = "b71f5c0a2d91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheme_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheme_id", sa.Integer(), sa.ForeignKey("schemes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scheme_id", "content_sha256", name="uq_scheme_document_content"),
    )
    op.create_index("ix_scheme_documents_scheme_id", "scheme_documents", ["scheme_id"])
    op.create_table(
        "scheme_document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("scheme_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),
    )
    op.create_index("ix_scheme_document_chunks_document_id", "scheme_document_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_table("scheme_document_chunks")
    op.drop_table("scheme_documents")
