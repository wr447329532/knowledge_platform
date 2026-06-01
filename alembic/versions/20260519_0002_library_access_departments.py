"""library access departments for specified-department visibility

Revision ID: 20260519_0002
Revises: 20260519_0001
Create Date: 2026-05-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260519_0002"
down_revision = "20260519_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_access_departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("library_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["library_id"], ["libraries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("library_id", "department_id", name="uq_library_access_department"),
    )
    op.create_index(
        "ix_library_access_departments_library_id",
        "library_access_departments",
        ["library_id"],
        unique=False,
    )
    op.create_index(
        "ix_library_access_departments_department_id",
        "library_access_departments",
        ["department_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_library_access_departments_department_id", table_name="library_access_departments")
    op.drop_index("ix_library_access_departments_library_id", table_name="library_access_departments")
    op.drop_table("library_access_departments")
