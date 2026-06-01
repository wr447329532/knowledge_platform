"""file comments and mentions

Revision ID: 20260520_0001
Revises: 20260519_0002
Create Date: 2026-05-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260520_0001"
down_revision = "20260519_0002"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _table_exists("file_comments"):
        op.create_table(
            "file_comments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("file_entry_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["file_entry_id"], ["file_entries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["file_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_file_comments_file_entry_id", "file_comments", ["file_entry_id"])
        op.create_index("ix_file_comments_user_id", "file_comments", ["user_id"])
        op.create_index("ix_file_comments_parent_id", "file_comments", ["parent_id"])
        op.create_index("ix_file_comments_created_at", "file_comments", ["created_at"])

    if not _table_exists("file_comment_mentions"):
        op.create_table(
            "file_comment_mentions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("comment_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["comment_id"], ["file_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("comment_id", "user_id", name="uq_file_comment_mention"),
        )
        op.create_index("ix_file_comment_mentions_comment_id", "file_comment_mentions", ["comment_id"])
        op.create_index("ix_file_comment_mentions_user_id", "file_comment_mentions", ["user_id"])

    if _table_exists("notifications"):
        if not _column_exists("notifications", "resource_type"):
            op.add_column("notifications", sa.Column("resource_type", sa.String(length=32), nullable=True))
        if not _column_exists("notifications", "resource_id"):
            op.add_column("notifications", sa.Column("resource_id", sa.Integer(), nullable=True))
        if not _column_exists("notifications", "extra_json"):
            op.add_column("notifications", sa.Column("extra_json", sa.Text(), nullable=True))


def downgrade() -> None:
    if _table_exists("notifications"):
        if _column_exists("notifications", "extra_json"):
            op.drop_column("notifications", "extra_json")
        if _column_exists("notifications", "resource_id"):
            op.drop_column("notifications", "resource_id")
        if _column_exists("notifications", "resource_type"):
            op.drop_column("notifications", "resource_type")
    if _table_exists("file_comment_mentions"):
        op.drop_index("ix_file_comment_mentions_user_id", table_name="file_comment_mentions")
        op.drop_index("ix_file_comment_mentions_comment_id", table_name="file_comment_mentions")
        op.drop_table("file_comment_mentions")
    if _table_exists("file_comments"):
        op.drop_index("ix_file_comments_created_at", table_name="file_comments")
        op.drop_index("ix_file_comments_parent_id", table_name="file_comments")
        op.drop_index("ix_file_comments_user_id", table_name="file_comments")
        op.drop_index("ix_file_comments_file_entry_id", table_name="file_comments")
        op.drop_table("file_comments")
