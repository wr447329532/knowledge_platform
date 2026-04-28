"""add missing composite indexes

Revision ID: 20260423_0005
Revises: 20260423_0004
Create Date: 2026-04-23 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260423_0005"
down_revision = "20260423_0004"
branch_labels = None
depends_on = None


def _index_exists(inspector: sa.Inspector, table: str, index_name: str) -> bool:
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # notifications: 高频查询「某用户的未读通知」
    if not _index_exists(insp, "notifications", "ix_notifications_user_id_is_read"):
        op.create_index(
            "ix_notifications_user_id_is_read",
            "notifications",
            ["user_id", "is_read"],
            unique=False,
        )

    # audit_logs: 按操作类型 + 时间范围过滤审计日志
    if not _index_exists(insp, "audit_logs", "ix_audit_logs_action_created_at"):
        op.create_index(
            "ix_audit_logs_action_created_at",
            "audit_logs",
            ["action", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if _index_exists(insp, "audit_logs", "ix_audit_logs_action_created_at"):
        op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    if _index_exists(insp, "notifications", "ix_notifications_user_id_is_read"):
        op.drop_index("ix_notifications_user_id_is_read", table_name="notifications")
