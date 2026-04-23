"""library parent_id for nested libraries (2nd/3rd level)

Revision ID: 20260423_0004
Revises: 20260329_0003
Create Date: 2026-04-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260423_0004"
down_revision = "20260329_0003"
branch_labels = None
depends_on = None


def _column_exists(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(col.get("name") == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not _column_exists(insp, "libraries", "parent_id"):
        # SQLite batch 中 Column 内联的 ForeignKey 会生成未命名约束，触发
        # "Constraint must have a name"。先加整型列，再创建具名外键（与 batch 文档一致）。
        with op.batch_alter_table("libraries") as batch:
            batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_libraries_parent_id_libraries",
                "libraries",
                ["parent_id"],
                ["id"],
                ondelete="CASCADE",
            )
        op.create_index(
            "ix_libraries_parent_id",
            "libraries",
            ["parent_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if _column_exists(insp, "libraries", "parent_id"):
        try:
            op.drop_index("ix_libraries_parent_id", table_name="libraries")
        except Exception:
            pass
        with op.batch_alter_table("libraries") as batch:
            batch.drop_constraint("fk_libraries_parent_id_libraries", type_="foreignkey")
            batch.drop_column("parent_id")
