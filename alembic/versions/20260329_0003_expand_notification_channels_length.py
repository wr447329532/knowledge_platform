"""expand notification channels length

Revision ID: 20260329_0003
Revises: 20260329_0002
Create Date: 2026-03-29 23:40:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_0003"
down_revision = "20260329_0002"
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(col.get("name") == column for col in inspector.get_columns(table))


def _alter_channels_to_100(table_name: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} "
                "ALTER COLUMN channels TYPE VARCHAR(100)"
            )
        )
        return

    # SQLite and other dialects: use batch mode for compatibility.
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column(
            "channels",
            existing_type=sa.String(length=10),
            type_=sa.String(length=100),
            existing_nullable=False,
            existing_server_default=sa.text("'system'"),
            server_default=sa.text("'system'"),
        )


def _alter_channels_to_10(table_name: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} "
                "ALTER COLUMN channels TYPE VARCHAR(10)"
            )
        )
        return

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column(
            "channels",
            existing_type=sa.String(length=100),
            type_=sa.String(length=10),
            existing_nullable=False,
            existing_server_default=sa.text("'system'"),
            server_default=sa.text("'system'"),
        )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    targets = ("notification_templates", "notification_send_logs")
    for table_name in targets:
        if _table_exists(insp, table_name) and _column_exists(insp, table_name, "channels"):
            _alter_channels_to_100(table_name)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    targets = ("notification_templates", "notification_send_logs")
    for table_name in targets:
        if _table_exists(insp, table_name) and _column_exists(insp, table_name, "channels"):
            _alter_channels_to_10(table_name)
