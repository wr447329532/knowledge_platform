"""user supervised departments for division_leader role

Revision ID: 20260519_0001
Revises: 20260423_0005
Create Date: 2026-05-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260519_0001"
down_revision = "20260423_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_supervised_departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "department_id", name="uq_user_supervised_department"),
    )
    op.create_index(
        "ix_user_supervised_departments_user_id",
        "user_supervised_departments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_supervised_departments_department_id",
        "user_supervised_departments",
        ["department_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_supervised_departments_department_id", table_name="user_supervised_departments")
    op.drop_index("ix_user_supervised_departments_user_id", table_name="user_supervised_departments")
    op.drop_table("user_supervised_departments")
