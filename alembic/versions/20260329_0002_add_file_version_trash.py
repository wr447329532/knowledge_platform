"""add file_version_trash table

Revision ID: 20260329_0002
Revises: 20260321_0001
Create Date: 2026-03-29 11:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_0002"
down_revision = "20260321_0001"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _table_exists(insp, "file_version_trash"):
        op.create_table(
            "file_version_trash",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("file_entry_id", sa.Integer(), sa.ForeignKey("file_entries.id", ondelete="CASCADE"), nullable=False),
            sa.Column("library_id", sa.Integer(), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("storage_path", sa.String(length=2048), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("content_hash", sa.String(length=128), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=False),
        )

    # refresh inspector after potential table creation
    insp = sa.inspect(bind)
    if _table_exists(insp, "file_version_trash"):
        if not _index_exists(insp, "file_version_trash", "ix_file_version_trash_file_entry_id"):
            op.create_index(
                "ix_file_version_trash_file_entry_id",
                "file_version_trash",
                ["file_entry_id"],
                unique=False,
            )
        if not _index_exists(insp, "file_version_trash", "ix_file_version_trash_library_id"):
            op.create_index(
                "ix_file_version_trash_library_id",
                "file_version_trash",
                ["library_id"],
                unique=False,
            )
        if not _index_exists(insp, "file_version_trash", "ix_file_version_trash_deleted_at"):
            op.create_index(
                "ix_file_version_trash_deleted_at",
                "file_version_trash",
                ["deleted_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _table_exists(insp, "file_version_trash"):
        return

    if _index_exists(insp, "file_version_trash", "ix_file_version_trash_deleted_at"):
        op.drop_index("ix_file_version_trash_deleted_at", table_name="file_version_trash")
    if _index_exists(insp, "file_version_trash", "ix_file_version_trash_library_id"):
        op.drop_index("ix_file_version_trash_library_id", table_name="file_version_trash")
    if _index_exists(insp, "file_version_trash", "ix_file_version_trash_file_entry_id"):
        op.drop_index("ix_file_version_trash_file_entry_id", table_name="file_version_trash")
    op.drop_table("file_version_trash")
