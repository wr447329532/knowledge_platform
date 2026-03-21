"""db hardening indexes and constraints

Revision ID: 20260321_0001
Revises:
Create Date: 2026-03-21 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_0001"
down_revision = None
branch_labels = None
depends_on = None


def _index_exists(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def _uq_exists(inspector: sa.Inspector, table: str, uq_name: str) -> bool:
    return any(uq.get("name") == uq_name for uq in inspector.get_unique_constraints(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    # audit_logs: optimize time-ordered and user-time queries
    if not _index_exists(insp, "audit_logs", "ix_audit_logs_created_at"):
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    if not _index_exists(insp, "audit_logs", "ix_audit_logs_user_id_created_at"):
        op.create_index(
            "ix_audit_logs_user_id_created_at",
            "audit_logs",
            ["user_id", "created_at"],
            unique=False,
        )

    # file_entries: optimize library active/deleted path queries
    if not _index_exists(insp, "file_entries", "ix_file_entries_library_deleted_path"):
        op.create_index(
            "ix_file_entries_library_deleted_path",
            "file_entries",
            ["library_id", "deleted_at", "path"],
            unique=False,
        )

    # file_versions: optimize latest versions fetch
    if not _index_exists(insp, "file_versions", "ix_file_versions_entry_uploaded_at"):
        op.create_index(
            "ix_file_versions_entry_uploaded_at",
            "file_versions",
            ["file_entry_id", "uploaded_at"],
            unique=False,
        )

    # libraries: optimize owner/department + deleted filters
    if not _index_exists(insp, "libraries", "ix_libraries_owner_deleted"):
        op.create_index("ix_libraries_owner_deleted", "libraries", ["owner_id", "deleted_at"], unique=False)
    if not _index_exists(insp, "libraries", "ix_libraries_dept_deleted"):
        op.create_index(
            "ix_libraries_dept_deleted",
            "libraries",
            ["department_id", "deleted_at"],
            unique=False,
        )

    # file_versions uniqueness safety:
    # enforce one row per (file_entry_id, version_no) on non-sqlite engines.
    if dialect != "sqlite" and not _uq_exists(insp, "file_versions", "uq_file_versions_entry_version"):
        op.create_unique_constraint(
            "uq_file_versions_entry_version",
            "file_versions",
            ["file_entry_id", "version_no"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    dialect = bind.dialect.name

    if dialect != "sqlite" and _uq_exists(insp, "file_versions", "uq_file_versions_entry_version"):
        op.drop_constraint("uq_file_versions_entry_version", "file_versions", type_="unique")

    if _index_exists(insp, "libraries", "ix_libraries_dept_deleted"):
        op.drop_index("ix_libraries_dept_deleted", table_name="libraries")
    if _index_exists(insp, "libraries", "ix_libraries_owner_deleted"):
        op.drop_index("ix_libraries_owner_deleted", table_name="libraries")
    if _index_exists(insp, "file_versions", "ix_file_versions_entry_uploaded_at"):
        op.drop_index("ix_file_versions_entry_uploaded_at", table_name="file_versions")
    if _index_exists(insp, "file_entries", "ix_file_entries_library_deleted_path"):
        op.drop_index("ix_file_entries_library_deleted_path", table_name="file_entries")
    if _index_exists(insp, "audit_logs", "ix_audit_logs_user_id_created_at"):
        op.drop_index("ix_audit_logs_user_id_created_at", table_name="audit_logs")
    if _index_exists(insp, "audit_logs", "ix_audit_logs_created_at"):
        op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
